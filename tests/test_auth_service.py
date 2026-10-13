from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from ipsakti.auth.password import hash_password
from ipsakti.auth.rbac import assign_role, bootstrap
from ipsakti.auth.revocation import denylist
from ipsakti.auth.service import (
    authenticate,
    get_principal,
    issue_token_pair,
    refresh_token_pair,
    revoke_refresh_token,
)
from ipsakti.auth.tokens import TokenType, decode_token
from ipsakti.core.errors import AuthenticationError
from ipsakti.db.enums import RoleName, UserStatus
from ipsakti.db.models.identity import Tenant, User
from sqlalchemy.orm import Session

PASSWORD = "s3cure-passphrase"


@pytest.fixture(autouse=True)
def _clean_denylist() -> Iterator[None]:
    denylist.clear()
    yield
    denylist.clear()




def test_denylist_consume_once_is_single_use() -> None:
    import time

    expires_at = time.time() + 60
    assert denylist.consume_once("single-use-jti", expires_at_epoch=expires_at) is True
    assert denylist.consume_once("single-use-jti", expires_at_epoch=expires_at) is False


def test_denylist_consume_once_rejects_expired_token() -> None:
    import time

    assert denylist.consume_once("expired-jti", expires_at_epoch=time.time() - 1) is False


def _user(
    session: Session,
    email: str,
    *,
    slug: str,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    bootstrap(session)
    tenant = session.query(Tenant).filter_by(slug=slug).one_or_none()
    if tenant is None:
        tenant = Tenant(name=slug, slug=slug)
        session.add(tenant)
        session.flush()
    user = User(
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password(PASSWORD),
        status=status,
    )
    session.add(user)
    session.flush()
    assign_role(session, user, RoleName.USER)
    session.commit()
    session.refresh(user)
    return user


def test_authenticate_success_sets_last_login(session: Session) -> None:
    _user(session, "alice@example.com", slug="t1")
    user = authenticate(session, "alice@example.com", PASSWORD)
    session.commit()
    assert user.email == "alice@example.com"
    assert user.last_login_at is not None


def test_authenticate_is_case_insensitive_on_email(session: Session) -> None:
    _user(session, "bob@example.com", slug="t2")
    user = authenticate(session, "  BOB@Example.COM ", PASSWORD)
    assert user.email == "bob@example.com"


def test_authenticate_wrong_password(session: Session) -> None:
    _user(session, "carol@example.com", slug="t3")
    with pytest.raises(AuthenticationError):
        authenticate(session, "carol@example.com", "wrong")


def test_authenticate_unknown_email(session: Session) -> None:
    bootstrap(session)
    session.commit()
    with pytest.raises(AuthenticationError):
        authenticate(session, "nobody@example.com", PASSWORD)


def test_authenticate_disabled_user(session: Session) -> None:
    _user(session, "dave@example.com", slug="t4", status=UserStatus.DISABLED)
    with pytest.raises(AuthenticationError):
        authenticate(session, "dave@example.com", PASSWORD)


def test_authenticate_ambiguous_email_rejected(session: Session) -> None:
    # Same email in two tenants, both active -> ambiguous, must not silently pick one.
    _user(session, "erin@example.com", slug="ta")
    _user(session, "erin@example.com", slug="tb")
    with pytest.raises(AuthenticationError):
        authenticate(session, "erin@example.com", PASSWORD)


def test_refresh_rotates_and_revokes_old(session: Session) -> None:
    user = _user(session, "frank@example.com", slug="t5")
    pair = issue_token_pair(user)
    old_claims = decode_token(pair.refresh_token, expected_type=TokenType.REFRESH)

    new_pair = refresh_token_pair(session, pair.refresh_token)
    assert new_pair.refresh_token != pair.refresh_token
    assert denylist.is_revoked(old_claims.jti) is True

    # The rotated (old) refresh token can no longer be reused.
    with pytest.raises(AuthenticationError):
        refresh_token_pair(session, pair.refresh_token)


def test_revoke_refresh_token_logout(session: Session) -> None:
    user = _user(session, "grace@example.com", slug="t6")
    pair = issue_token_pair(user)
    claims = decode_token(pair.refresh_token, expected_type=TokenType.REFRESH)
    revoke_refresh_token(pair.refresh_token)
    assert denylist.is_revoked(claims.jti) is True


def test_revoke_tolerates_garbage_token() -> None:
    revoke_refresh_token("not-a-jwt")  # must not raise


def test_get_principal_for_valid_user(session: Session) -> None:
    user = _user(session, "heidi@example.com", slug="t7")
    principal = get_principal(session, user.id)
    assert principal.user_id == user.id
    assert principal.tenant_id == user.tenant_id


def test_get_principal_missing_user(session: Session) -> None:
    bootstrap(session)
    session.commit()
    with pytest.raises(AuthenticationError):
        get_principal(session, uuid.uuid4())
