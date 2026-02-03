from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.services.model_manager import model_manager

class TitleGenerator:
    def __init__(self):
        # 使用轻量级模型生成标题，速度快
        # 也可以根据配置使用当前对话的模型
        self.model = model_manager.get_model("deepseek-chat") # 默认使用 smart model，或者可以指定更快的
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个专业的对话标题生成助手。请根据用户的提问和AI的回答，生成一个简洁的标题。"),
            ("user", "用户问题: {user_query}\nAI回答: {ai_response}\n\n请生成一个不超过10个字的标题，不要包含标点符号，直接输出标题文本。")
        ])
        
        self.chain = self.prompt | self.model | StrOutputParser()

    async def generate_title(self, user_query: str, ai_response: str) -> str:
        try:
            # 截断过长的输入，节省 token 并加快速度
            short_query = user_query[:200]
            short_response = ai_response[:200]
            
            title = await self.chain.ainvoke({
                "user_query": short_query,
                "ai_response": short_response
            })
            
            # 清理可能多余的引号或空白
            clean_title = title.strip().replace('"', '').replace('“', '').replace('”', '')
            if len(clean_title) > 15:
                clean_title = clean_title[:15]
                
            return clean_title
        except Exception as e:
            print(f"Title generation failed: {e}")
            return "新对话"

title_generator = TitleGenerator()
