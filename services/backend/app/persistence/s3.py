"""S3 object storage adapter.

Keys are tenant-prefixed so a bucket-level listing cannot cross organizations
even if a future caller gets a prefix wrong. Locally this talks to LocalStack
via ``AWS_ENDPOINT_URL``; in cloud environments that variable must be empty and
the SDK resolves real AWS endpoints (enforced in ``app.config``).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.auth.permissions import Principal
from app.config import settings
from app.errors import NotFound, ProviderError

if TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3.client import S3Client


@lru_cache
def get_client() -> S3Client:
    client: S3Client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        endpoint_url=settings.aws_endpoint,
        config=Config(retries={"max_attempts": 3, "mode": "standard"}),
    )
    return client


def tenant_key(principal: Principal, *parts: str) -> str:
    """Build an object key rooted at the caller's organization."""
    suffix = "/".join(p.strip("/") for p in parts if p)
    return f"organizations/{principal.organization_id}/{suffix}"


def put_object(principal: Principal, key: str, body: bytes, content_type: str) -> str:
    full_key = tenant_key(principal, key)
    try:
        get_client().put_object(
            Bucket=settings.s3_bucket,
            Key=full_key,
            Body=body,
            ContentType=content_type,
        )
    except ClientError as exc:
        raise ProviderError(f"Failed to store object: {exc}") from exc
    return full_key


def get_object(principal: Principal, key: str) -> bytes:
    full_key = tenant_key(principal, key)
    try:
        response = get_client().get_object(Bucket=settings.s3_bucket, Key=full_key)
        return response["Body"].read()
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
            raise NotFound(f"Object {key} was not found.") from exc
        raise ProviderError(f"Failed to read object: {exc}") from exc


def check_storage() -> bool:
    """Connectivity probe for the health endpoint."""
    try:
        get_client().head_bucket(Bucket=settings.s3_bucket)
        return True
    except Exception:
        return False
