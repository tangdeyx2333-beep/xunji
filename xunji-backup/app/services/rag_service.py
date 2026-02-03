import os
import uuid
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pypdf import PdfReader
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

try:
    from langchain_chroma import Chroma
except Exception:  # pragma: no cover
    from langchain_community.vectorstores import Chroma

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", os.getenv("KMP_DUPLICATE_LIB_OK", "TRUE"))
load_dotenv(override=True)


CHUNK_SIZE_CHARS = int(os.getenv("RAG_CHUNK_SIZE_CHARS", "2000"))
CHUNK_OVERLAP_CHARS = int(os.getenv("RAG_CHUNK_OVERLAP_CHARS", "200"))
RAG_COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "zhiwei_knowledge_base")
RAG_EMBEDDING_PROVIDER = os.getenv("RAG_EMBEDDING_PROVIDER", "ollama").lower()
RAG_RESET_ON_SCHEMA_ERROR = os.getenv("RAG_RESET_ON_SCHEMA_ERROR", "false").lower() == "true"


class RagService:
    """RAG service based on Chroma vector store.

    This implementation avoids heavy optional dependencies (sentence-transformers/torch)
    by using a lightweight text splitter and pypdf for PDF extraction.
    """

    def __init__(self) -> None:
        """Initialize embeddings and vector store."""
        if RAG_EMBEDDING_PROVIDER == "dashscope":
            try:
                from langchain_community.embeddings import DashScopeEmbeddings

                self.embeddings = DashScopeEmbeddings(
                    model=str(os.getenv("QWEN_EMBEDDING_MODEL")),
                    dashscope_api_key=os.getenv("QWEN_API_KEY"),
                )
            except Exception:
                self.embeddings = OllamaEmbeddings(
                    model=str(os.getenv("EMBEDDING_MODEL") or "nomic-embed-text"),
                    base_url=str(os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"),
                )
        else:
            self.embeddings = OllamaEmbeddings(
                model=str(os.getenv("EMBEDDING_MODEL") or "nomic-embed-text"),
                base_url=str(os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"),
            )
        self._vector_store = None

    @property
    def vector_store(self) -> Any:
        return self._get_vector_store()
    def _get_vector_store(self) -> Any:
        """Lazily initialize Chroma vector store.

        Returns:
            Initialized Chroma vector store.

        Raises:
            RuntimeError: If initialization fails and reset is disabled.
        """
        if self._vector_store is not None:
            return self._vector_store

        persist_directory = os.getenv("PERSIST_DIRECTORY")
        try:
            self._vector_store = Chroma(
                collection_name=RAG_COLLECTION_NAME,
                embedding_function=self.embeddings,
                persist_directory=persist_directory,
            )
            return self._vector_store
        except KeyError as exc:
            if not RAG_RESET_ON_SCHEMA_ERROR:
                raise RuntimeError(
                    "Chroma 数据目录可能与当前版本不兼容；请更换/清空 PERSIST_DIRECTORY 或开启 RAG_RESET_ON_SCHEMA_ERROR=true"
                ) from exc
            if persist_directory:
                import shutil

                shutil.rmtree(persist_directory, ignore_errors=True)
            self._vector_store = Chroma(
                collection_name=RAG_COLLECTION_NAME,
                embedding_function=self.embeddings,
                persist_directory=persist_directory,
            )
            return self._vector_store

    def _split_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks.

        Args:
            text: Raw text.

        Returns:
            List of chunk strings.
        """
        if not text:
            return []
        if CHUNK_SIZE_CHARS <= 0:
            return [text]

        chunks: List[str] = []
        start = 0
        length = len(text)
        while start < length:
            end = min(start + CHUNK_SIZE_CHARS, length)
            chunks.append(text[start:end])
            if end == length:
                break
            start = max(end - CHUNK_OVERLAP_CHARS, 0)
        return chunks

    def _read_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file.

        Args:
            file_path: PDF path.

        Returns:
            Extracted text.
        """
        reader = PdfReader(file_path)
        texts: List[str] = []
        for page in reader.pages:
            texts.append(page.extract_text() or "")
        return "\n".join(texts)

    def _read_text_file(self, file_path: str) -> str:
        """Read a UTF-8 text-like file.

        Args:
            file_path: File path.

        Returns:
            File content.
        """
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def load_and_split_file(self, tmp_file_path: str, suffix: str) -> List[Document]:
        """Load and split a file into Document chunks without persisting.

        Args:
            tmp_file_path: Temporary file path.
            suffix: File suffix, like '.pdf', '.txt', '.md'.

        Returns:
            A list of Documents.

        Raises:
            ValueError: If suffix is not supported.
        """
        suffix = suffix.lower()
        if suffix == ".pdf":
            raw_text = self._read_pdf(tmp_file_path)
        elif suffix in {".txt", ".md"}:
            raw_text = self._read_text_file(tmp_file_path)
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")

        docs: List[Document] = []
        for chunk in self._split_text(raw_text):
            docs.append(Document(page_content=chunk, metadata={}))
        return docs

    def process_uploaded_file(self, file_obj: Any, filename: str) -> str:
        """Process an uploaded file and store into vector DB.

        Args:
            file_obj: FastAPI UploadFile-like object.
            filename: Original filename.

        Returns:
            file_id for later retrieval.
        """
        file_id = str(uuid.uuid4())
        suffix = os.path.splitext(filename)[1].lower()

        import tempfile
        import shutil

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            shutil.copyfileobj(file_obj.file, tmp_file)
            tmp_path = tmp_file.name

        try:
            split_docs = self.load_and_split_file(tmp_path, suffix)
            for doc in split_docs:
                doc.metadata["file_id"] = file_id
                doc.metadata["filename"] = filename
            if split_docs:
                self._get_vector_store().add_documents(split_docs)
            return file_id
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    def search(self, query: str, filters: Optional[dict] = None, k: int = 4) -> List[Document]:
        """Similarity search in the vector store.

        Args:
            query: Query text.
            filters: Optional Chroma filters.
            k: Top-k.

        Returns:
            Matching documents.
        """
        return self._get_vector_store().similarity_search(query, k=k, filter=filters)

    def get_db_stats(self) -> Dict[str, Any]:
        """Get basic vector DB stats for debugging."""
        try:
            vs = self._get_vector_store()
            count = vs._collection.count()
            peek_data = vs._collection.peek(limit=3)
            return {
                "total_count": count,
                "sample_ids": peek_data.get("ids"),
                "sample_metadatas": peek_data.get("metadatas"),
                "sample_contents": [(c[:50] + "...") for c in (peek_data.get("documents") or [])],
            }
        except Exception as exc:
            return {"error": f"获取数据库状态失败: {str(exc)}"}

    def delete_docs(self, file_ids: List[str]) -> None:
        if not file_ids:
            return
        vs = self._get_vector_store()
        try:
            vs._collection.delete(where={"file_id": {"$in": file_ids}})
        except Exception:
            for file_id in file_ids:
                try:
                    vs._collection.delete(where={"file_id": file_id})
                except Exception:
                    continue
        if hasattr(vs, "persist"):
            try:
                vs.persist()
            except Exception:
                pass

    def delete_doc(self, file_id: str) -> None:
        if not file_id:
            return
        self.delete_docs([file_id])

    def simple_search(self, query: str, k: int = 3, file_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Simple search wrapper returning JSON-friendly results."""
        filters: Dict[str, Any] = {}
        if file_ids:
            if len(file_ids) == 1:
                filters = {"file_id": file_ids[0]}
            else:
                filters = {"file_id": {"$in": file_ids}}

        docs = self._get_vector_store().similarity_search(query, k=k, filter=filters or None)
        results: List[Dict[str, Any]] = []
        for doc in docs:
            results.append({"content": doc.page_content, "metadata": doc.metadata, "file_id": doc.metadata.get("file_id")})
        return results


rag_service = RagService()
