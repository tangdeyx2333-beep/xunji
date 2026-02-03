import base64
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.core import config
from app.models.sql_models import MessageAttachment, gen_uuid
from app.services.object_storage import object_storage


def save_chat_attachments(
    *,
    db: Session,
    files: List[Dict[str, Any]],
    user_id: str,
    conversation_id: str,
    message_id: str,
) -> List[Dict[str, Any]]:
    saved: List[Dict[str, Any]] = []
    if not files:
        return saved

    for f in files:
        b64 = f.get("base64") or ""
        if not b64:
            continue
        try:
            content_bytes = base64.b64decode(b64)
        except Exception:
            continue

        try:
            uploaded = object_storage.upload_bytes(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                filename=f.get("name") or "attachment",
                content=content_bytes,
                content_type=f.get("mime"),
            )
        except Exception:
            continue

        att = MessageAttachment(
            id=gen_uuid(),
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=user_id,
            filename=uploaded["filename"],
            mime=uploaded.get("content_type") or "",
            size=uploaded.get("size") or 0,
            storage_provider=uploaded.get("storage_provider") or config.OBJECT_STORAGE_PROVIDER,
            storage_key=uploaded["key"],
            url="",
        )
        db.add(att)
        saved.append(
            {
                "id": att.id,
                "filename": att.filename,
                "mime": att.mime,
                "size": att.size,
                "storage_provider": att.storage_provider,
                "storage_key": att.storage_key,
            }
        )

    if saved:
        db.commit()

    return saved

