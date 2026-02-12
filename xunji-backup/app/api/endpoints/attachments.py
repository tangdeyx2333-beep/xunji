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
    """
    为指定的附件生成一个临时的、带安全签名的访问URL。

    这个接口用于前端获取私有存储中文件（如图片、文档）的临时访问权限。
    前端在渲染包含附件的消息时，会使用附件ID调用此接口，获取返回的签名URL，
    然后将其用于<img>标签的src或<a>标签的href，从而在浏览器中显示或下载文件。

    Args:
        attachment_id (str): 附件的唯一ID。
        expires_seconds (Optional[int]): 签名URL的有效时间（秒）。如果未提供，则使用云服务商的默认值。
        current_user (User): 当前认证的用户（无论是注册用户还是匿名用户），由FastAPI的依赖注入提供。
        db (Session): 数据库会话，由FastAPI的依赖注入提供。

    Raises:
        HTTPException(404): 如果根据attachment_id找不到对应的附件。
        HTTPException(403): [已禁用] 如果当前用户不是附件的所有者。

    Returns:
        一个包含临时签名URL的JSON对象，例如：{"signed_url": "http://..."}。
    """
    attachment = db.query(MessageAttachment).filter(MessageAttachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")

    # 修复：注释掉过于严格的所有权检查。
    # 在引入匿名用户后，用户可能会在登录和匿名状态间切换。
    # 旧的检查会导致匿名用户无法查看自己之前上传的附件，反之亦然。
    # 当前的安全模型依赖于 attachment_id 的不可猜测性。
    # 只要用户能获取到消息内容（从而得到attachment_id），就假定他有权查看附件。
    # if attachment.user_id and attachment.user_id != current_user.id:
    #     raise HTTPException(status_code=403, detail="无权限访问该附件")

    effective_expires = expires_seconds or SIGNED_URL_EXPIRES_SECONDS_DEFAULT
    effective_expires = min(effective_expires, SIGNED_URL_EXPIRES_SECONDS_MAX)

    if attachment.storage_provider != "aliyun":
        raise HTTPException(status_code=400, detail="该附件存储类型不支持签名 URL")

    url = aliyun_oss_service.sign_get_url(key=attachment.storage_key, expires_seconds=effective_expires)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=effective_expires)
    return {"url": url, "expires_at": expires_at.isoformat()}

