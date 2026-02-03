from typing import Any, Dict, Optional

from app.core.config import OBJECT_STORAGE_PROVIDER
from app.services.aliyun_oss_service import aliyun_oss_service
from app.services.oss_service import oss_service as cos_service


class ObjectStorage:
    def upload_bytes(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
        filename: str,
        content: bytes,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        if OBJECT_STORAGE_PROVIDER == "aliyun":
            result = aliyun_oss_service.upload_bytes(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                filename=filename,
                content=content,
                content_type=content_type,
            )
            result["storage_provider"] = "aliyun"
            return result
        if OBJECT_STORAGE_PROVIDER == "cos":
            result = cos_service.upload_bytes(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                filename=filename,
                content=content,
                content_type=content_type,
            )
            result["storage_provider"] = "cos"
            return result
        raise RuntimeError("OBJECT_STORAGE_PROVIDER is disabled")

    def sign_get_url(self, *, key: str, expires_seconds: int) -> str:
        if OBJECT_STORAGE_PROVIDER == "aliyun":
            return aliyun_oss_service.sign_get_url(key=key, expires_seconds=expires_seconds)
        if OBJECT_STORAGE_PROVIDER == "cos":
            raise RuntimeError("cos signed url not implemented")
        raise RuntimeError("OBJECT_STORAGE_PROVIDER is disabled")


object_storage = ObjectStorage()

