"""Optional DynamoDB adapter.

Postgres is the default store. DynamoDB is here for access patterns that
genuinely suit it — high-volume, single-key lookups such as per-session agent
scratch state — and stays disabled unless ``DYNAMODB_ENABLED=1``.

Keeping it optional and small is deliberate: an unused generic data-access
wrapper is worse than no wrapper at all.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError

from app.auth.permissions import Principal
from app.config import settings
from app.errors import ProviderError

if TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_dynamodb.service_resource import Table


class DynamoDisabled(ProviderError):
    code = "dynamodb_disabled"


@lru_cache
def get_table() -> Table:
    if not settings.dynamodb_enabled:
        raise DynamoDisabled(
            "DynamoDB is disabled. Set DYNAMODB_ENABLED=1 and DYNAMODB_TABLE to use it."
        )
    resource = boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.aws_endpoint,
    )
    table: Table = resource.Table(settings.dynamodb_table)
    return table


def _pk(principal: Principal) -> str:
    return f"ORG#{principal.organization_id}"


def put_item(principal: Principal, sort_key: str, attributes: dict[str, Any]) -> None:
    try:
        get_table().put_item(Item={"pk": _pk(principal), "sk": sort_key, **attributes})
    except ClientError as exc:
        raise ProviderError(f"DynamoDB write failed: {exc}") from exc


def get_item(principal: Principal, sort_key: str) -> dict[str, Any] | None:
    try:
        response = get_table().get_item(Key={"pk": _pk(principal), "sk": sort_key})
    except ClientError as exc:
        raise ProviderError(f"DynamoDB read failed: {exc}") from exc
    return response.get("Item")
