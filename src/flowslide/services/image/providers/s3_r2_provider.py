"""
S3 / Cloudflare R2 storage provider for images using boto3
"""
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..models import ImageInfo, ImageUploadRequest, ImageOperationResult, ImageProcessingOptions, ImageProvider
from .base import LocalStorageProvider, provider_registry

logger = logging.getLogger(__name__)


class S3R2StorageProvider(LocalStorageProvider):
    """S3-compatible storage provider (supports Cloudflare R2 via endpoint_override)

    Expects environment variables or config keys:
    - access_key, secret_key, endpoint, bucket, region (region optional)
    """

    def __init__(self, config: Dict[str, Any]):
        # Use USER_UPLOAD to represent cloud/user uploaded storage distinct from local FS
        super().__init__(ImageProvider.USER_UPLOAD, config)
        self.access_key = config.get("access_key") or os.getenv("R2_ACCESS_KEY_ID")
        self.secret_key = config.get("secret_key") or os.getenv("R2_SECRET_ACCESS_KEY")
        self.endpoint = config.get("endpoint") or os.getenv("R2_ENDPOINT")
        self.bucket = config.get("bucket") or os.getenv("R2_BUCKET_NAME")
        self.region = config.get("region") or os.getenv("R2_REGION")

        # Create boto3 client lazily
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client

        session = boto3.session.Session()
        params = {
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
        }
        if self.region:
            params["region_name"] = self.region
        if self.endpoint:
            params["endpoint_url"] = self.endpoint

        self._client = session.client("s3", **params)
        return self._client

    async def create_presigned_upload(self, request: ImageUploadRequest) -> Dict[str, Any]:
        """Create a presigned URL for PUT upload. Returns dict with url and fields.

        The client should PUT the file bytes to the returned URL.
        """
        try:
            client = self._get_client()
            object_key = request.object_key if hasattr(request, "object_key") and request.object_key else f"images/{uuid.uuid4().hex}_{int(time.time())}.jpg"

            # Generate presigned URL for put_object
            url = client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": object_key, "ContentType": request.content_type or "application/octet-stream"},
                ExpiresIn=3600,
            )

            return {
                "success": True,
                "upload_type": "s3_presigned_put",
                "provider": "s3",
                "bucket": self.bucket,
                "object_key": object_key,
                "url": url,
                "method": "PUT",
                "expires_in": 3600,
            }

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to create presigned upload: {e}")
            return {"success": False, "message": str(e)}

    async def upload(self, request: ImageUploadRequest, file_data: bytes) -> ImageOperationResult:
        """Server-side upload (put object)"""
        try:
            client = self._get_client()
            object_key = request.object_key if hasattr(request, "object_key") and request.object_key else f"images/{uuid.uuid4().hex}_{int(time.time())}.jpg"

            client.put_object(Bucket=self.bucket, Key=object_key, Body=file_data, ContentType=request.content_type or "application/octet-stream")

            image_info = ImageInfo(
                image_id=object_key,
                filename=Path(object_key).name,
                local_path=None,
                provider=self.provider,
                title=request.title if hasattr(request, "title") else None,
                description="",
                metadata=None,
                source_type=None,
                tags=None,
            )

            return ImageOperationResult(success=True, message="Uploaded", image_info=image_info)

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to upload to S3/R2: {e}")
            return ImageOperationResult(success=False, message=str(e))

    async def get_image(self, image_id: str) -> Optional[ImageInfo]:
        """Return ImageInfo for object key (image_id)"""
        try:
            # We don't fetch the object content here, only metadata
            client = self._get_client()
            # Head object to ensure it exists
            client.head_object(Bucket=self.bucket, Key=image_id)

            image_info = ImageInfo(
                image_id=image_id,
                filename=Path(image_id).name,
                local_path=None,
                provider=self.provider,
                title=None,
                description="",
                metadata=None,
                source_type=None,
                tags=None,
            )
            return image_info
        except Exception:
            return None

    async def delete_image(self, image_id: str) -> bool:
        try:
            client = self._get_client()
            client.delete_object(Bucket=self.bucket, Key=image_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete image {image_id} from S3/R2: {e}")
            return False


# Register provider factory for use by ImageService initialize
def register_s3_provider_if_configured(config: Dict[str, Any]):
    # if env/config has bucket and endpoint
    if (config.get("access_key") or os.getenv("R2_ACCESS_KEY_ID")) and (
        config.get("secret_key") or os.getenv("R2_SECRET_ACCESS_KEY")
    ) and (config.get("bucket") or os.getenv("R2_BUCKET_NAME")):
        provider = S3R2StorageProvider(config)
        provider_registry.register(provider)
        logger.debug("S3/R2 storage provider registered")


# The ImageService will import this module conditionally; expose registration helper
__all__ = ["S3R2StorageProvider", "register_s3_provider_if_configured"]
