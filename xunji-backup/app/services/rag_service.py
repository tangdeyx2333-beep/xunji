import os
import shutil
import uuid
import tempfile

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings

# 定义数据持久化的路径 (在当前项目根目录下生成 chroma_db 文件夹)
PERSIST_DIRECTORY = "./chroma_db"
load_dotenv(override=True)

class RagService:
    def __init__(self):
        # model_name = os.getenv("QWEN_EMBEDDING_MODEL")
        # api_key = os.getenv("QWEN_API_KEY")
        # print(f"DEBUG: 正在使用的 Embedding 模型: {model_name}")
        # print(f"DEBUG: API Key 前5位: {str(api_key)[:5] if api_key else 'None'}")
        # 1. 初始化嵌入模型 (Embedding Model)
        # 必须和存入时用的模型一致
        # self.embeddings = OpenAIEmbeddings(
        #     api_key=os.getenv("OPENAI_API_KEY")
        # )
        # 如果是用 Ollama:
        self.embeddingsOllama = OllamaEmbeddings(
            model=str(os.getenv("EMBEDDING_MODEL")),
            base_url=str(os.getenv("OLLAMA_BASE_URL"))
        )
        # 千问embedding
        self.embeddings = DashScopeEmbeddings(
            model=str(os.getenv("QWEN_EMBEDDING_MODEL")),
            dashscope_api_key=os.getenv("QWEN_API_KEY")
        )

        # 2. 初始化/加载 向量数据库
        # 核心：只要指定了 persist_directory，它就会自动读取该目录下的数据
        # 如果目录不存在，它会自动创建；如果存在，就自动加载。
        self.vector_store = Chroma(
            collection_name="zhiwei_knowledge_base",  # 集合名字
            embedding_function=self.embeddings,  # 嵌入函数
            persist_directory=os.getenv("PERSIST_DIRECTORY")  # ★持久化路径★
        )
        # ★ 新增：初始化拆分器 ★
        # RecursiveCharacterTextSplitter: 优先按段落(\n\n)、句子(。)、逗号(，)切分
        # from_tiktoken_encoder: 确保切分后的长度符合 token 限制，而不是字符数限制
        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=500,  # 每个块约 500 token
            chunk_overlap=50,  # 重叠 50 token，防止断章取义
            encoding_name="cl100k_base"  # OpenAI 的编码标准
        )

    def process_uploaded_file(self, file_obj, filename: str, ) -> str:
        """
        接收上传的文件对象，处理并存入向量库
        返回: file_id (用于后续检索过滤)
        """
        # 1. 生成唯一的文件ID (用于 metadata 过滤)
        file_id = str(uuid.uuid4())

        # 2. 将上传的文件保存为临时文件 (因为 Loader 通常需要文件路径)
        # 获取文件后缀
        suffix = os.path.splitext(filename)[1].lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            # 将 FastAPI 的 UploadFile 内容写入临时文件
            shutil.copyfileobj(file_obj.file, tmp_file)
            tmp_file_path = tmp_file.name

        try:
            # 3. 根据文件类型选择加载器
            documents = []
            if suffix == ".pdf":
                loader = PyPDFLoader(tmp_file_path)
                documents = loader.load()
            elif suffix == ".txt" or suffix == ".md":
                loader = TextLoader(tmp_file_path, encoding="utf-8")
                documents = loader.load()
            else:
                raise ValueError(f"不支持的文件格式: {suffix}")

            # 4. ★ 核心步骤：拆分文档 ★
            split_docs = self.text_splitter.split_documents(documents)

            # 5. 为每个切片添加 Metadata (关键！为了支持你之前的 filters 逻辑)
            for doc in split_docs:
                doc.metadata["file_id"] = file_id
                doc.metadata["filename"] = filename
                # 你可以在这里加 user_id，如果你的 request 里传了的话

            # 6. 存入 Chroma
            if split_docs:
                self.vector_store.add_documents(split_docs)
                print(f"文件 {filename} 处理完成，共切分为 {len(split_docs)} 块。ID: {file_id}")

            return file_id
        except Exception as e:
            print(f"处理文件 {filename} 时出错: {e}")
            raise e
        finally:
            # 7. 清理临时文件
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)

    def add_documents(self, documents):
        """
        上传文档时调用
        documents: List[Document] (由 LangChain 的 Loader 加载并切割后的)
        """
        # 添加文档，Chroma 会自动写入磁盘
        self.vector_store.add_documents(documents)
        # 旧版本需要手动调用 .persist()，新版本(0.4+)会自动保存，不需要手动写了
        print(f"成功存入 {len(documents)} 个切片到 {PERSIST_DIRECTORY}")

    def search(self, query: str, filters: dict = None, k: int = 4):
        """
        检索
        filters: 比如 {"file_id": "123"} 或 {"user_id": "abc"}
        """
        results = self.vector_store.similarity_search(
            query,
            k=k,
            filter=filters  # 这里就是你要的元数据过滤
        )
        return results

    # app/services/rag_service.py (追加以下内容)

    def get_db_stats(self):
        """
        [调试专用] 查看数据库状态
        返回: 总数量，以及前 3 条数据的样本
        """
        # 1. 获取总数量
        # 注意: chroma 的 vector_store 对象里有个 _collection 属性可以直接操作底层
        try:
            # LangChain 0.1+ 写法
            count = self.vector_store._collection.count()

            # 2. 获取前 3 条样本 (peek)
            # 包括 ids, metadatas, documents (也就是 page_content)
            peek_data = self.vector_store._collection.peek(limit=3)

            return {
                "total_count": count,
                "sample_ids": peek_data["ids"],
                "sample_metadatas": peek_data["metadatas"],
                "sample_contents": [c[:50] + "..." for c in peek_data["documents"]]  # 只显示前50个字
            }
        except Exception as e:
            return {"error": f"获取数据库状态失败: {str(e)}"}

    def simple_search(self, query: str, k: int = 3, file_ids: list[str] = None) -> list[dict]:
        """
        纯检索接口：输入问题，返回最相似的文本块
        """
        filters = {}
        if file_ids:
            # ChromaDB 的 filter 语法:
            # 如果是多个ID: {"file_id": {"$in": ["id1", "id2"]}}
            # 如果是单个ID: {"file_id": "id1"}
            if len(file_ids) == 1:
                filters = {"file_id": file_ids[0]}
            else:
                filters = {"file_id": {"$in": file_ids}}

        # 执行相似度搜索
        docs = self.vector_store.similarity_search(query, k=k, filter=filters or None)

        # 格式化返回结果
        results = []
        for doc in docs:
            results.append({
                "content": doc.page_content,  # 文本内容
                "metadata": doc.metadata,  # 元数据 (文件名、页码等)
                "file_id": doc.metadata.get("file_id")
            })
        return results

# 单例模式
rag_service = RagService()
