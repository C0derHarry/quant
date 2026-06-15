import os
from dataclasses import dataclass
from fastapi import Header, HTTPException, Depends
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


def get_subscription(auth: AuthUser) -> dict:
    """Return the user's subscription row, defaulting to free if no row exists."""
    try:
        sb  = supabase_client(auth)
        res = (sb.table("user_subscriptions")
                 .select("tier, status, current_period_end")
                 .eq("user_id", auth.user_id)
                 .limit(1)
                 .execute())
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return {"tier": "free", "status": "active", "current_period_end": None}


def require_premium(auth: AuthUser = Depends(get_current_user)) -> AuthUser:
    """FastAPI dependency that raises 402 for non-premium users."""
    sub = get_subscription(auth)
    if sub.get("tier") != "premium":
        raise HTTPException(status_code=402, detail="Premium subscription required")
    return auth
