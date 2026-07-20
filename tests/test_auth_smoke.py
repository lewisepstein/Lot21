import pytest


@pytest.mark.asyncio
async def test_logout_with_malformed_token_returns_401(client):
    # A garbage bearer token passes HTTPBearer, then blacklist_token()'s jwt.decode raises.
    # Buggy code catches jwt.JWTError (undefined in PyJWT) -> AttributeError -> 500.
    r = await client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user_returns_401(client):
    # Empty/unknown user in the throwaway DB -> 401 (deterministic).
    r = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "passwd": "whatever12"},
    )
    assert r.status_code == 401
