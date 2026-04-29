import os
from dataclasses import dataclass
from fastapi import Header, HTTPException
from supabase import create_client, Client

SUPABASE_URL      = os.getenv("SUPABASE_PROJECT_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_PUBLIC_KEY", "")


@dataclass
class AuthUser:
    user_id: str
    token:   str


def get_current_user(authorization: str = Header(default=None)) -> AuthUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ")
    # Validate the token by asking Supabase's auth server directly.
    # This avoids all JWT algorithm / secret-format issues with local verification.
    try:
        sb   = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        resp = sb.auth.get_user(token)
        if not resp.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return AuthUser(user_id=resp.user.id, token=token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Auth error: {exc}")


def supabase_client(auth: AuthUser) -> Client:
    sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    sb.postgrest.auth(auth.token)
    return sb
