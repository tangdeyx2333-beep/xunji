from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import SIGNED_URL_EXPIRES_SECONDS_DEFAULT, SIGNED_URL_EXPIRES_SECONDS_MAX
from app.db.session import get_db
from app.models.sql_models import MessageAttachment, User
from app.services.aliyun_oss_service import aliyun_oss_service

router = APIRouter()


@router.get("/attachments/{attachment_id}/signed-url")
async def get_attachment_signed_url(
    attachment_id: str,
    expires_seconds: Optional[int] = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attachment = db.query(MessageAttachment).filter(MessageAttachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    if attachment.user_id and attachment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该附件")

    effective_expires = expires_seconds or SIGNED_URL_EXPIRES_SECONDS_DEFAULT
    effective_expires = min(effective_expires, SIGNED_URL_EXPIRES_SECONDS_MAX)

    if attachment.storage_provider != "aliyun":
        raise HTTPException(status_code=400, detail="该附件存储类型不支持签名 URL")

    url = aliyun_oss_service.sign_get_url(key=attachment.storage_key, expires_seconds=effective_expires)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=effective_expires)
    return {"url": url, "expires_at": expires_at.isoformat()}

