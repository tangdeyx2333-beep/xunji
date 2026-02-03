import asyncio
import base64
import os
import tempfile
from datetime import datetime
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from langchain_community.tools import TavilySearchResults
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.orm import Session

from app.models.sql_models import AiInstruction, FileRecord, Message, TreeNode
from app.schemas.chat import ChatRequest, SearchQuery
from app.services.model_manager import model_manager
from app.services.rag_service import rag_service

load_dotenv()


MAX_DIRECT_READ_SIZE_BYTES = 5 * 1024 * 1024
MAX_HISTORY_MESSAGES = 10
RAG_TOP_K = 4


class ChatService:
    """Chat orchestration service.

    This service handles:
    - Tree-based conversation history reconstruction.
    - Optional internet search context.
    - Optional RAG context (from knowledge base file_ids).
    - Optional inline attachments for a single chat turn:
      - image/video: forwarded as multimodal content for supported models (e.g. Kimi).
      - documents: small files are inlined as text, large files are searched via temporary RAG.
    """

    def __init__(self) -> None:
        """Initialize the chat service."""
        self.search_model = ChatGoogleGenerativeAI(model=os.getenv("GOOGLE_SEARCH_MODEL"))

    def get_model(self, model_name: str) -> Any:
        """Get a LangChain chat model instance.

        Args:
            model_name: Model name as selected by the user.

        Returns:
            A LangChain chat model instance.
        """
        return model_manager.get_model(model_name)

    def is_multimodal_supported(self, model_name: str) -> bool:
        """Check whether a model supports multimodal input.

        Args:
            model_name: Model name.

        Returns:
            True if the model supports multimodal input, otherwise False.
        """
        return model_manager.is_multimodal_supported(model_name)

    def get_search_query_chain(self) -> Any:
        """Build a search-query generator chain.

        Returns:
            A LangChain runnable that outputs SearchQuery.
        """
        prompt = ChatPromptTemplate.from_template(
            "你是一个搜索专家。请根据用户问题提取或生成1个最相关的搜索关键词。\n用户问题: {question}"
        )
        return prompt | self.search_model.with_structured_output(SearchQuery)

    def get_internet_info(self, question: str) -> str:
        """Fetch internet information using Tavily search.

        Args:
            question: User question.

        Returns:
            Search results as a string.
        """
        search_tool = TavilySearchResults(max_results=3)
        try:
            query_gen_chain = self.get_search_query_chain()
            search_query_obj = query_gen_chain.invoke({"question": question})
            query = (
                search_query_obj.queries[0]
                if hasattr(search_query_obj, "queries") and search_query_obj.queries
                else str(search_query_obj)
            )
            results = search_tool.invoke({"query": query})
            return str(results)
        except Exception:
            results = search_tool.invoke({"query": question})
            return str(results)

    def get_history_from_tree(self, db: Session, current_node_id: str, limit: int = MAX_HISTORY_MESSAGES) -> List[Any]:
        """Reconstruct conversation history from the TreeNode chain.

        Args:
            db: SQLAlchemy session.
            current_node_id: Current leaf node id (user node id).
            limit: Max number of historical messages.

        Returns:
            A list of LangChain message objects (HumanMessage/AIMessage).
        """
        if not current_node_id:
            return []

        curr_node = db.query(TreeNode).filter(TreeNode.id == current_node_id).first()
        if not curr_node:
            return []

        history_messages: List[Message] = []
        curr_id = curr_node.parent_id
        count = 0

        while curr_id and count < limit:
            node = db.query(TreeNode).filter(TreeNode.id == curr_id).first()
            if not node:
                break

            msg = db.query(Message).filter(Message.id == node.message_id).first()
            if msg:
                history_messages.append(msg)

            curr_id = node.parent_id
            count += 1

        history_messages.reverse()

        history: List[Any] = []
        for msg in history_messages:
            content = (msg.content or "").strip()
            if not content:
                if msg.role == "user":
                    content = "（用户发送了空消息）"
                else:
                    content = "（空消息）"
            if msg.role == "user":
                history.append(HumanMessage(content=content))
            elif msg.role in {"ai", "assistant"}:
                history.append(AIMessage(content=content))

        return history

    def _decode_base64(self, base64_str: str) -> bytes:
        """Decode a base64 string into bytes.

        Args:
            base64_str: Base64-encoded payload.

        Returns:
            Decoded bytes.

        Raises:
            ValueError: If decoding fails.
        """
        try:
            return base64.b64decode(base64_str)
        except Exception as exc:
            raise ValueError("Invalid base64 payload") from exc

    def _attachment_size_bytes(self, base64_str: str, declared_size: Optional[int]) -> int:
        """Estimate attachment size in bytes.

        Args:
            base64_str: Base64-encoded content.
            declared_size: Optional size from client (bytes).

        Returns:
            Size in bytes.
        """
        if isinstance(declared_size, int) and declared_size >= 0:
            return declared_size
        return int(len(base64_str) * 0.75)

    def _with_current_time(self, user_text: str) -> str:
        now_str = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        return f"{user_text}\n\n当前时间：{now_str}"

    def _get_user_instructions(self, db: Session, user_id: str) -> str:
        """Get user's AI instructions from database.
        
        Args:
            db: SQLAlchemy session.
            user_id: User ID.
            
        Returns:
            Formatted instructions string or empty string if no instructions.
        """
        instructions = (
            db.query(AiInstruction)
            .filter(AiInstruction.user_id == user_id)
            .filter(AiInstruction.is_deleted == False)
            .order_by(AiInstruction.sort_order.asc(), AiInstruction.created_at.asc())
            .all()
        )
        
        if not instructions:
            return ""
        
        instruction_texts = [f"{i+1}. {inst.content}" for i, inst in enumerate(instructions)]
        return "额外指令：\n" + "\n".join(instruction_texts)

    def _build_kimi_multimodal_parts(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build Kimi multimodal parts list for HumanMessage(content=list).

        Args:
            files: Attachment list from request.files.

        Returns:
            List of content parts compatible with Kimi/OpenAI-style multimodal input.
        """
        parts: List[Dict[str, Any]] = []
        for f in files:
            f_type = f.get("type")
            b64 = f.get("base64")
            mime = f.get("mime") or ("image/jpeg" if f_type == "image" else "video/mp4")
            if not b64:
                continue
            if f_type == "image":
                parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
            elif f_type == "video":
                parts.append({"type": "video_url", "video_url": {"url": f"data:{mime};base64,{b64}"}})
        return parts

    def _read_small_document_as_text(self, filename: str, file_bytes: bytes) -> str:
        """Read a small document into plain text for inlining.

        Args:
            filename: Original filename.
            file_bytes: Raw bytes.

        Returns:
            Extracted text.
        """
        suffix = os.path.splitext(filename)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            split_docs = rag_service.load_and_split_file(tmp_path, suffix)
            return "\n\n".join([d.page_content for d in split_docs])
        except Exception:
            try:
                return file_bytes.decode("utf-8", errors="replace")
            except Exception:
                return "[无法读取该文件内容]"
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    def _rag_search_large_document(self, filename: str, file_bytes: bytes, query: str) -> str:
        """Run temporary RAG for a large document.

        Args:
            filename: Original filename.
            file_bytes: Raw bytes.
            query: User query.

        Returns:
            Relevant snippets joined as a string.
        """
        temp_file_id = f"temp-{os.urandom(8).hex()}"
        suffix = os.path.splitext(filename)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            split_docs = rag_service.load_and_split_file(tmp_path, suffix)
            for doc in split_docs:
                doc.metadata["file_id"] = temp_file_id
                doc.metadata["filename"] = filename
            if split_docs:
                rag_service.vector_store.add_documents(split_docs)
            docs = rag_service.vector_store.similarity_search(
                query=query,
                k=RAG_TOP_K,
                filter={"file_id": temp_file_id},
            )
            return "\n\n---\n".join([d.page_content for d in docs]) if docs else ""
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            try:
                rag_service.vector_store._collection.delete(where={"file_id": temp_file_id})
            except Exception:
                pass

    async def astream_chat_with_model(
        self,
        request: ChatRequest,
        db: Session,
        current_node_id: Optional[str] = None,
    ) -> AsyncIterable[str]:
        """Stream chat completion tokens.

        Args:
            request: Chat request payload.
            db: SQLAlchemy session.
            current_node_id: Current user node id for history reconstruction.

        Yields:
            Text chunks of the assistant response.
        """
        model = self.get_model(request.model_name)

        chat_history = (
            self.get_history_from_tree(db, current_node_id, limit=MAX_HISTORY_MESSAGES)
            if current_node_id
            else []
        )

        has_multimodal = any(f.get("type") in {"image", "video"} for f in (request.files or []))

        inline_text_blocks: List[str] = []
        temp_rag_blocks: List[str] = []
        for f in request.files or []:
            f_type = f.get("type")
            name = f.get("name") or "attachment"
            b64 = f.get("base64") or ""

            if f_type in {"image", "video"}:
                continue

            size_bytes = self._attachment_size_bytes(b64, f.get("size"))
            file_bytes = self._decode_base64(b64)

            if size_bytes > MAX_DIRECT_READ_SIZE_BYTES:
                temp_rag_blocks.append(self._rag_search_large_document(name, file_bytes, request.message))
            else:
                inline_text_blocks.append(self._read_small_document_as_text(name, file_bytes))

        async def run_search_task() -> str:
            if request.enable_search:
                return await asyncio.to_thread(self.get_internet_info, request.message)
            return ""

        async def run_rag_task() -> str:
            if request.enable_rag or (request.file_ids and len(request.file_ids) > 0):
                file_ids = request.file_ids
                if not file_ids:
                    f_records = db.query(FileRecord).filter(FileRecord.user_id == request.user_id).all()
                    file_ids = [f.id for f in f_records]
                if not file_ids:
                    return ""
                docs = await asyncio.to_thread(
                    rag_service.search,
                    query=request.message,
                    filters={"file_id": {"$in": file_ids}},
                    k=RAG_TOP_K,
                )
                if docs:
                    return "\n\n---\n".join([doc.page_content for doc in docs])
            return ""

        search_result, rag_result = await asyncio.gather(run_search_task(), run_rag_task())

        context_parts: List[str] = []
        if search_result:
            context_parts.append(f"【联网搜索结果】:\n{search_result}")
        if rag_result:
            context_parts.append(f"【本地知识库内容】:\n{rag_result}")
        if inline_text_blocks:
            context_parts.append("【上传附件内容】:\n" + "\n\n---\n".join(inline_text_blocks))
        if temp_rag_blocks:
            merged = "\n\n---\n".join([b for b in temp_rag_blocks if b])
            if merged:
                context_parts.append(f"【大文件检索结果】:\n{merged}")

        final_context = "\n\n".join(context_parts) if context_parts else "（无参考上下文，请直接回答）"

        if has_multimodal:
            if not self.is_multimodal_supported(request.model_name):
                yield f"❌ 当前模型 ({request.model_name}) 不支持图片/视频理解，请切换到 Kimi。"
                return

            extra_instructions = self._get_user_instructions(db, request.user_id)
            sys_msg_content = (
                "你是一个名为'知微'的AI助手。\n"
                "请结合以下参考信息回答用户的问题。\n\n"
                f"参考信息:\n{final_context}\n"
            )
            if extra_instructions:
                sys_msg_content += f"\n\n{extra_instructions}\n"
            messages: List[Any] = [SystemMessage(content=sys_msg_content)]
            messages.extend(chat_history)
            parts = self._build_kimi_multimodal_parts(request.files or [])
            user_text = (request.message or "").strip()
            if not user_text:
                user_text = "（用户发送了附件）"
            parts.append({"type": "text", "text": self._with_current_time(user_text)})
            messages.append(HumanMessage(content=parts))

            async for chunk in model.astream(messages):
                yield getattr(chunk, "content", str(chunk))
            return

        extra_instructions = self._get_user_instructions(db, request.user_id)
        qa_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一个名为'知微'的AI助手。
{extra_instructions}
""",
                ),
                ("placeholder", "{chat_history}"),
                ("human", """
                请结合以下参考信息回答用户的问题。

参考信息:
{context}
用户问题
"{message}"
"""
                 ),
            ]
        )

        chain = qa_prompt | model | StrOutputParser()
        user_text = (request.message or "").strip() or "（用户发送了空消息）"
        async for chunk in chain.astream({"context": final_context, "chat_history": chat_history, "message": self._with_current_time(user_text), "extra_instructions": extra_instructions}):
            yield chunk


chat_service = ChatService()
