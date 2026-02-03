import shutil
import uuid
from typing import List, Optional
from datetime import datetime

from dotenv import load_dotenv
from fsspec.implementations.http import file_size

from app.api.deps import get_current_user
from app.models.sql_models import FileRecord, User
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models.sql_models import FileRecord
from app.services.rag_service import rag_service
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, BackgroundTasks
from fastapi import FastAPI, BackgroundTasks, UploadFile

from app.db.session import get_db

import os

load_dotenv()

router = APIRouter()


# 定义返回结构
class UploadResponse(BaseModel):
    filename: str
    file_id: str
    message: str


# 定义文件响应 DTO
class FileDTO(BaseModel):
    id: str
    filename: str
    created_at: datetime
    file_size: int

    class Config:
        from_attributes = True


class ClearKnowledgeBaseRequest(BaseModel):
    confirm: bool = False


# --- 接口 1 文件上传接口 ---
def save_file(file, filename) -> tuple[str, int]:
    # 2. 获取并校验本地存储路径
    upload_dir = os.getenv("RAG_FILE_PATH")
    if not upload_dir:
        # 严格执行：如果环境变量未配置，不猜测路径，直接抛错
        raise HTTPException(status_code=500, detail="未配置环境变量 RAG_FILE_PATH")

    # 确保目录存在
    os.makedirs(upload_dir, exist_ok=True)

    # 生成本地完整存储路径 (建议使用 uuid 避免同名文件覆盖)
    # 若需保持原名，直接使用 filename，但需注意路径安全
    safe_filename = filename
    save_path = os.path.join(upload_dir, safe_filename)

    try:
        # todo 为啥 await file.seek(0)可以 file.seek(0)  不行
        file.file.seek(0)
        # 3. 将文件写入本地磁盘
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 获取真实文件大小 (字节)
        size = os.path.getsize(save_path)
        # 关键点：重置文件指针，否则后续 rag_service 读取时会从末尾开始导致内容为空
        return save_path, size
    except Exception as e:
        # 如果处理失败，且本地文件已创建，建议清理，防止产生垃圾文件
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...),
                      current_user: User = Depends(get_current_user),
                      background_tasks: BackgroundTasks = BackgroundTasks(),
                      db: Session = Depends(get_db),  # ★ 注入数据库会话
                      ):
    """
      上传文档接口
      支持 PDF, TXT, MD
      """
    # 1. 简单的格式校验
    allowed_extensions = [".pdf", ".txt", ".md"]
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="仅支持 PDF, TXT 或 MD 文件")

    try:
        # 2. 调用 Service 处理
        # 注意：这里直接传 file 对象给 service
        file_id = rag_service.process_uploaded_file(file, file.filename)

        split_filename_id = os.getenv("SPLIT_FILENAME_ID")
        if not split_filename_id:
            raise HTTPException(status_code=500, detail="未配置环境变量 SPLIT_FILENAME_ID")

        file_path, size = save_file(file, f"{file_id}{split_filename_id}{file.filename}")

        # 3. ★ 新增：将文件记录写入 SQL 数据库 ★
        new_file = FileRecord(
            id=file_id,  # 与 Chroma 里的 file_id 保持一致
            user_id=current_user.id,  # 单机版暂为空，多用户时填 user.id
            filename=file.filename,
            file_path=os.getenv("RAG_FILE_PATH"),  # 文件储存的位置
            file_size=size,  # 以后可以优化计算真实大小
        )
        db.add(new_file)
        db.commit()
        db.refresh(new_file)

        return UploadResponse(
            filename=file.filename,
            file_id=file_id,
            message="上传成功，知识库已构建索引"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 接口 2: 获取文件列表 (知识库管理) ---
# --- 修改后的查询接口 ---
@router.get("/files", response_model=List[FileDTO])
async def get_files(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)  # ★ 关键：注入当前用户
):
    """
    获取【当前登录用户】的文件列表
    """
    files = db.query(FileRecord) \
        .filter(FileRecord.is_deleted == False) \
        .filter(FileRecord.user_id == current_user.id) \
        .order_by(FileRecord.created_at.desc()) \
        .all()  # ★ 增加这行过滤条件

    return files

# --- 接口 3: 删除文件 (同时删数据库和 Chroma) ---
@router.delete("/files/{file_id}")
async def delete_file(
        file_id: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    删除文件：
    1. 标记数据库为删除
    2. (选做) 从 ChromaDB 中删除向量
    """
    file_record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")
    if file_record.user_id and file_record.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限删除该文件")

    # 1. 软删除 SQL
    file_record.is_deleted = True
    db.commit()

    rag_service.delete_doc(file_id)

    split_filename_id = os.getenv("SPLIT_FILENAME_ID")
    if split_filename_id:
        try:
            base_dir = file_record.file_path or os.getenv("RAG_FILE_PATH") or ""
            if base_dir:
                maybe_path = os.path.join(base_dir, f"{file_id}{split_filename_id}{file_record.filename}")
                if os.path.exists(maybe_path):
                    os.remove(maybe_path)
        except Exception:
            pass

    return {"message": "文件已移除"}


@router.post("/knowledge-base/clear")
async def clear_knowledge_base(
        payload: ClearKnowledgeBaseRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm=true 才会执行清空操作")

    files = (
        db.query(FileRecord)
        .filter(FileRecord.is_deleted == False)
        .filter(FileRecord.user_id == current_user.id)
        .all()
    )
    file_ids = [f.id for f in files]

    for f in files:
        f.is_deleted = True
    db.commit()

    rag_service.delete_docs(file_ids)

    split_filename_id = os.getenv("SPLIT_FILENAME_ID")
    if split_filename_id:
        for f in files:
            try:
                base_dir = f.file_path or os.getenv("RAG_FILE_PATH") or ""
                if not base_dir:
                    continue
                maybe_path = os.path.join(base_dir, f"{f.id}{split_filename_id}{f.filename}")
                if os.path.exists(maybe_path):
                    os.remove(maybe_path)
            except Exception:
                continue

    return {"message": "知识库已清空", "deleted_count": len(file_ids)}
