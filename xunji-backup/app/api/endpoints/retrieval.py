# app/api/endpoints/retrieval.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.rag_service import rag_service

router = APIRouter()


# --- 1. 定义请求体 ---
class SearchRequest(BaseModel):
    query: str
    top_k: int = 3
    file_ids: List[str] = []


# --- 2. 接口 A: 验证数据库状态 (看看存进去了没) ---
@router.get("/debug/db_status")
async def get_db_status():
    """
    调试接口：查看向量库里到底有多少条数据
    """
    return rag_service.get_db_stats()


# --- 3. 接口 B: 纯文本检索 (验证能不能查到) ---
@router.post("/retrieval/search")
async def search_vectors(request: SearchRequest, ):
    """
    测试接口：根据 query 找相似文档
    """
    print(f"正在检索: {request.query}, file_ids: {request.file_ids}")

    try:
        results = rag_service.simple_search(
            query=request.query,
            k=request.top_k,
            file_ids=request.file_ids
        )

        if not results:
            return {"message": "没有找到相关内容", "results": []}

        return {"message": "检索成功", "count": len(results), "results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))