import asyncio
import os
from typing import List, Any, AsyncIterable
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from langchain_community.chat_models import ChatOllama
from langchain_tavily import TavilySearch
from langchain_community.tools import TavilySearchResults
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage  # ★ 关键导入
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.models.sql_models import Message, FileRecord, TreeNode
from app.services.rag_service import rag_service
from app.services.model_manager import model_manager
from app.schemas.chat import ChatRequest, SearchQuery

load_dotenv()


class ChatService:
    def __init__(self):
        # 初始化配置保持不变
        self.search_model = ChatGoogleGenerativeAI(model=os.getenv("GOOLE_SEARCH_MODEL"))

    # 1. 获取模型 (已委托给 ModelManager)
    def get_model(self, model_name: str):
        return model_manager.get_model(model_name)

    # 2. 搜索相关辅助方法 (保持不变)
    def get_search_query_chain(self):
        prompt = ChatPromptTemplate.from_template(
            "你是一个搜索专家。请根据用户问题提取或生成1个最相关的搜索关键词。\n用户问题: {question}"
        )
        return prompt | self.search_model.with_structured_output(SearchQuery)

    def execute_tavily_search(self, search_input: Any) -> str:
        search_tool = TavilySearchResults(max_results=3)
        try:
            query = search_input.queries[0] if hasattr(search_input, 'queries') and search_input.queries else str(
                search_input)
            results = search_tool.invoke({"query": query})
            return str(results)
        except Exception as e:
            return f"搜索执行出错: {e}"

    def get_internet_info(self, question: str) -> str:
        query_gen_chain = self.get_search_query_chain()
        try:
            search_query_obj = query_gen_chain.invoke({"question": question})
            context = self.execute_tavily_search(search_query_obj)
        except Exception:
            context = self.execute_tavily_search(question)
        return context

    # ★★★ 新增：通过树状结构获取历史记录 ★★★
    def get_history_from_tree(self, db: Session, current_node_id: str, limit: int = 10) -> List[Any]:
        if not current_node_id:
            return []
            
        history_messages = []
        
        # 1. 递归向上查找父节点
        # 注意：这里我们简单地用循环查找，避免递归深度过深
        curr_id = current_node_id
        count = 0
        
        # 我们需要先找到当前节点，但是当前节点是最新的用户消息
        # 提示词中通常不包含"当前正在回答的问题"作为历史，而是作为 input
        # 但是 LangChain 的 MessagesPlaceholder 也可以包含它。
        # 按照原本的逻辑，`chat_history` 是 *之前* 的对话。
        # 当前用户问题在 `message` 字段传入。
        # 所以我们需要从 current_node (用户节点) 的 *父节点* 开始找。
        
        # 先查当前节点，确认它的 parent_id
        curr_node = db.query(TreeNode).filter(TreeNode.id == curr_id).first()
        if not curr_node:
            return []
            
        curr_id = curr_node.parent_id
        
        while curr_id and count < limit:
            node = db.query(TreeNode).filter(TreeNode.id == curr_id).first()
            if not node:
                break
                
            # 获取对应的消息内容
            msg = db.query(Message).filter(Message.id == node.message_id).first()
            if msg:
                history_messages.append(msg)
                
            curr_id = node.parent_id
            count += 1
            
        # 2. 翻转顺序 (因为我们是从下往上查的，所以现在是 [新 -> 旧]，需要转为 [旧 -> 新])
        history_messages.reverse()
        
        # 3. 转换为 LangChain 对象
        history = []
        for msg in history_messages:
            if msg.role == "user":
                history.append(HumanMessage(content=msg.content))
            elif msg.role == "ai" or msg.role == "assistant":
                history.append(AIMessage(content=msg.content))
                
        return history

    # ★★★ 核心修改：带记忆的流式对话 ★★★
    async def astream_chat_with_model(self, request: ChatRequest, db: Session, current_node_id: str = None) -> AsyncIterable[str]:
        model = self.get_model(request.model_name)

        # 1. ★ 获取历史记录 ★
        # 使用树状结构获取
        if current_node_id:
             chat_history = self.get_history_from_tree(db, current_node_id, limit=10)
        else:
             # 兼容旧逻辑 (虽然可能用不到)
             chat_history = []


        # 2. 并发执行 Search/RAG (保持不变)
        async def run_search_task():
            if request.enable_search:
                return await asyncio.to_thread(self.get_internet_info, request.message)
            return ""

        async def run_rag_task():
            if request.enable_rag:
                file_ids = request.file_ids
                if not file_ids:
                    f_records = db.query(FileRecord).filter(FileRecord.user_id == request.user_id).all()
                    file_ids = [f.id for f in f_records]

                if not file_ids: return ""

                docs = await asyncio.to_thread(
                    rag_service.search,
                    query=request.message,
                    filters={"file_id": {"$in": file_ids}},
                )
                if docs:
                    return "\n\n---\n".join([doc.page_content for doc in docs])
            return ""

        search_result, rag_result = await asyncio.gather(run_search_task(), run_rag_task())

        # 3. 拼接 Context
        final_context_parts = []
        if search_result: final_context_parts.append(f"【联网搜索结果】:\n{search_result}")
        if rag_result: final_context_parts.append(f"【本地知识库内容】:\n{rag_result}")

        final_context = "\n\n".join(final_context_parts) if final_context_parts else "（无参考上下文，请直接回答）"

        # 4. ★ 构建带记忆的 Prompt ★
        # 使用 from_messages 结构，这样才能正确插入 HumanMessage/AIMessage 对象列表
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个名为'知微'的AI助手。
            请结合以下参考信息回答用户的问题。

            参考信息:
            {context}
            """),

            # ★ 关键：这里会展开我们传入的 chat_history 列表
            ("placeholder", "{chat_history}"),

            ("human", "{message}")
        ])

        full_chain = qa_prompt | model | StrOutputParser()

        # 5. ★ 传入 chat_history 进行流式输出 ★
        async for chunk in full_chain.astream({
            "context": final_context,
            "chat_history": chat_history,  # 注入刚刚查出来的历史
            "message": request.message
        }):
            yield chunk


chat_service = ChatService()