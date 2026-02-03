import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from langchain_community.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

load_dotenv()

class ModelManager:
    _instance = None
    
    # ★★★ 多模态配置 ★★★
    MULTIMODAL_CONFIG = {
        "supported_models": ["kimi", "moonshot", "gpt-4-vision", "gpt-4o", "gemini"], # 支持多模态的模型前缀
        "modalities": ["image", "video"]
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
            cls._instance.models = {}  # 缓存已初始化的模型
        return cls._instance

    def is_multimodal_supported(self, model_name: str) -> bool:
        """
        检查模型是否支持多模态
        """
        for prefix in self.MULTIMODAL_CONFIG["supported_models"]:
            if model_name.startswith(prefix):
                return True
        return False

    def get_model(self, model_name: str) -> Any:
        """
        工厂方法：根据模型名称获取对应的 LangChain ChatModel 实例
        """
        # 1. 如果模型已经在缓存中，直接返回
        # 注意：对于需要动态参数的模型（如 temperature），可能需要更复杂的缓存策略
        if model_name in self.models:
            return self.models[model_name]

        # 2. 创建新模型实例
        model = self._create_model(model_name)
        
        # 3. 存入缓存 (可选，取决于是否需要单例模型)
        self.models[model_name] = model
        
        return model

    def _create_model(self, model_name: str) -> Any:
        """
        内部方法：具体的模型实例化逻辑
        """
        if model_name.startswith("gpt"):
            return ChatOpenAI(model=model_name)
            
        elif model_name.startswith("deepseek"):
            return ChatOpenAI(
                model=model_name,
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_API_BASE"),
            )
            
        elif model_name.startswith("llm") or model_name.startswith("llama") or model_name.startswith("ollama"):
            # 兼容 ollama 的命名习惯
            # 解析实际模型名称：如果是 'ollama/llama3'，则提取 'llama3'
            real_model_name = model_name
            if "/" in model_name:
                real_model_name = model_name.split("/", 1)[1]
            
             # 从环境变量读取 base_url，如果没有则默认 http://localhost:11434
            return ChatOllama(model=real_model_name, base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
            
        elif model_name.startswith("gemini"):
            return ChatGoogleGenerativeAI(
                model=model_name, 
                api_key=os.getenv("GEMINI_API_KEY")
            )
            
        elif model_name.startswith("kimi") or model_name.startswith("moonshot"):
            # Kimi (Moonshot AI) 兼容 OpenAI 接口
            return ChatOpenAI(
                model=model_name,
                api_key=os.getenv("MOONSHOT_API_KEY"),
                base_url=os.getenv("MOONSHOT_BASE_URL"),
            )
            
        elif model_name.startswith("qwen"):
            # 通义千问 (DashScope) 兼容 OpenAI 接口
            return ChatOpenAI(
                model=model_name,
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url=os.getenv("DASHSCOPE_BASE_URL"),
            )

        else:
            # 默认兜底模型
            print(f"Warning: Unknown model '{model_name}', falling back to default.")
            return ChatOllama(model="llama3.2:1b", base_url="http://localhost:11434")

# 创建全局单例
model_manager = ModelManager()
