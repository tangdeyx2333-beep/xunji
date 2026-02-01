from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.session import get_db
from app.models.sql_models import ModelConfig, User
from app.api.deps import get_current_user
import uuid

router = APIRouter()

# --- Schema ---
class ModelConfigCreate(BaseModel):
    model_name: str
    display_name: str

class ModelConfigDTO(BaseModel):
    id: str
    model_name: str
    display_name: str
    
    class Config:
        from_attributes = True

# --- Endpoints ---

@router.get("/models", response_model=List[ModelConfigDTO])
async def get_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户可用的模型列表
    (这里简单起见，返回用户自定义的 + 系统预设的，或者只返回用户自定义的)
    """
    # 1. 查询用户自定义模型
    user_models = db.query(ModelConfig).filter(ModelConfig.user_id == current_user.id).all()
    
    # 2. 如果没有任何配置，可以返回默认列表 (可选)
    # 或者我们假设前端会混合默认列表和这个接口返回的列表
    # 这里我们只返回数据库里的
    return user_models

@router.post("/models", response_model=ModelConfigDTO)
async def create_model(
    model_in: ModelConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    添加新模型
    """
    # 检查是否已存在
    exists = db.query(ModelConfig).filter(
        ModelConfig.user_id == current_user.id,
        ModelConfig.model_name == model_in.model_name
    ).first()
    
    if exists:
        raise HTTPException(status_code=400, detail="模型已存在")
        
    new_model = ModelConfig(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        model_name=model_in.model_name,
        display_name=model_in.display_name
    )
    
    db.add(new_model)
    db.commit()
    db.refresh(new_model)
    return new_model

@router.delete("/models/{model_id}")
async def delete_model(
    model_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除模型
    """
    model = db.query(ModelConfig).filter(
        ModelConfig.id == model_id,
        ModelConfig.user_id == current_user.id
    ).first()
    
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
        
    db.delete(model)
    db.commit()
    return {"message": "删除成功"}
