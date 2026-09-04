from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID, uuid4

import requests

from app.config import Settings


class StorageConfigurationError(RuntimeError):
    pass


class StorageUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    object_path: str
    public_url: str


class StorageService:
    def upload_generated_image(
        self,
        *,
        business_id: UUID,
        post_id: UUID,
        image_bytes: bytes,
        mime_type: str,
    ) -> StoredObject:
        raise NotImplementedError

    def upload_business_asset(
        self,
        *,
        business_id: UUID,
        image_bytes: bytes,
        mime_type: str,
        extension: str,
    ) -> StoredObject:
        raise NotImplementedError

    def delete_object(self, *, bucket: str, object_path: str) -> None:
        raise NotImplementedError


class SupabaseStorageService(StorageService):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        if not settings.supabase_url:
            raise StorageConfigurationError("SUPABASE_URL is required for generated post media storage.")
        if not settings.supabase_service_role_key:
            raise StorageConfigurationError("SUPABASE_SERVICE_ROLE_KEY is required for generated post media storage.")

    def upload_generated_image(
        self,
        *,
        business_id: UUID,
        post_id: UUID,
        image_bytes: bytes,
        mime_type: str,
    ) -> StoredObject:
        extension = _extension_for_mime_type(mime_type)
        object_path = str(
            PurePosixPath(
                "businesses",
                str(business_id),
                "posts",
                str(post_id),
                f"image-{uuid4()}{extension}",
            )
        )
        return self._upload(
            bucket=self._settings.supabase_post_media_bucket,
            object_path=object_path,
            image_bytes=image_bytes,
            mime_type=mime_type,
        )

    def upload_business_asset(
        self,
        *,
        business_id: UUID,
        image_bytes: bytes,
        mime_type: str,
        extension: str,
    ) -> StoredObject:
        safe_extension = extension if extension.startswith(".") else f".{extension}"
        object_path = str(
            PurePosixPath(
                "businesses",
                str(business_id),
                "assets",
                f"logo-{uuid4()}{safe_extension.lower()}",
            )
        )
        return self._upload(
            bucket=self._settings.supabase_business_assets_bucket,
            object_path=object_path,
            image_bytes=image_bytes,
            mime_type=mime_type,
        )

    def delete_object(self, *, bucket: str, object_path: str) -> None:
        url = f"{self._settings.supabase_url}/storage/v1/object/{bucket}/{object_path}"
        try:
            requests.delete(
                url,
                headers=self._headers(),
                timeout=self._settings.supabase_request_timeout_seconds,
            )
        except requests.RequestException:
            return

    def _upload(
        self,
        *,
        bucket: str,
        object_path: str,
        image_bytes: bytes,
        mime_type: str,
    ) -> StoredObject:
        url = f"{self._settings.supabase_url}/storage/v1/object/{bucket}/{object_path}"
        headers = {
            **self._headers(),
            "Content-Type": mime_type,
            "x-upsert": "false",
        }
        try:
            response = requests.post(
                url,
                headers=headers,
                data=image_bytes,
                timeout=self._settings.supabase_request_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise StorageUnavailableError("Supabase Storage is unavailable.") from exc
        if not response.ok:
            raise StorageUnavailableError(f"Supabase Storage upload failed with status {response.status_code}.")
        return StoredObject(
            bucket=bucket,
            object_path=object_path,
            public_url=f"{self._settings.supabase_url}/storage/v1/object/public/{bucket}/{object_path}",
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.supabase_service_role_key}",
            "apikey": self._settings.supabase_service_role_key,
        }


def _extension_for_mime_type(mime_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime_type.lower(), ".png")
