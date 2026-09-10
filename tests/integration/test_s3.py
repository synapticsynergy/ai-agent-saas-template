"""S3 behaviour against LocalStack.

Covers the tenant key prefixing that keeps one organization's objects out of
another's listing, and the not-found mapping the service layer relies on.
"""

from __future__ import annotations

import uuid

import pytest
from app.auth.permissions import Principal
from app.errors import NotFound
from app.persistence import s3


@pytest.fixture(autouse=True)
def _bucket() -> None:
    """Create the bucket if the LocalStack init script has not."""
    from app.config import settings

    client = s3.get_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        client.create_bucket(
            Bucket=settings.s3_bucket,
            CreateBucketConfiguration={"LocationConstraint": settings.aws_region},
        )


class TestObjectStorage:
    def test_an_object_round_trips(self, member: Principal) -> None:
        key = f"itineraries/{uuid.uuid4()}.json"
        body = b'{"title": "Integration evening"}'

        s3.put_object(member, key, body, "application/json")
        assert s3.get_object(member, key) == body

    def test_a_missing_object_raises_not_found(self, member: Principal) -> None:
        with pytest.raises(NotFound):
            s3.get_object(member, f"itineraries/{uuid.uuid4()}.json")

    def test_the_health_probe_sees_the_bucket(self) -> None:
        assert s3.check_storage() is True


class TestTenantPrefixing:
    def test_keys_are_rooted_at_the_organization(self, member: Principal) -> None:
        key = s3.tenant_key(member, "itineraries", "plan.json")
        assert key == f"organizations/{member.organization_id}/itineraries/plan.json"

    def test_another_organization_cannot_read_the_object(
        self, member: Principal, other_org: Principal
    ) -> None:
        """The prefix is derived from the principal, so the key simply differs."""
        key = f"itineraries/{uuid.uuid4()}.json"
        s3.put_object(member, key, b"secret", "application/json")

        with pytest.raises(NotFound):
            s3.get_object(other_org, key)

    def test_a_traversal_attempt_in_the_key_cannot_escape_the_prefix(
        self, member: Principal
    ) -> None:
        key = s3.tenant_key(member, "../../other-org/plan.json")
        assert key.startswith(f"organizations/{member.organization_id}/")
