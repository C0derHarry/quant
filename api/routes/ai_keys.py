"""User-scoped AI API key storage + provider catalog.

DB schema (apply once via Supabase SQL editor):

    create table user_ai_keys (
      user_id    uuid primary key references auth.users(id) on delete cascade,
      provider   text not null check (provider in ('google','anthropic','openai')),
      api_key    text not null,
      model      text not null,
      updated_at timestamptz not null default now()
    );
    alter table user_ai_keys enable row level security;
    create policy "users own their key" on user_ai_keys
      for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_current_user, supabase_client, AuthUser
from core.llm import PROVIDERS, validate_provider_model

router = APIRouter()


class SaveKeyRequest(BaseModel):
    provider: str
    model:    str
    api_key:  str


@router.get("/providers")
def list_providers():
    """Public catalog of supported providers and models."""
    return PROVIDERS


@router.get("")
def get_my_key(auth: AuthUser = Depends(get_current_user)):
    """Return the user's saved {provider, model, key_last4} or null."""
    sb  = supabase_client(auth)
    res = (sb.table("user_ai_keys")
             .select("provider, model, api_key")
             .eq("user_id", auth.user_id)
             .limit(1)
             .execute())
    if not res.data:
        return None
    row = res.data[0]
    key = row.get("api_key", "")
    return {
        "provider":  row["provider"],
        "model":     row["model"],
        "key_last4": key[-4:] if len(key) >= 4 else key,
    }


@router.put("")
def save_my_key(body: SaveKeyRequest, auth: AuthUser = Depends(get_current_user)):
    try:
        validate_provider_model(body.provider, body.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not body.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    sb  = supabase_client(auth)
    row = {
        "user_id":  auth.user_id,
        "provider": body.provider,
        "model":    body.model,
        "api_key":  body.api_key.strip(),
    }
    res = sb.table("user_ai_keys").upsert(row, on_conflict="user_id").execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to save API key")
    return {"ok": True}


@router.delete("")
def delete_my_key(auth: AuthUser = Depends(get_current_user)):
    sb = supabase_client(auth)
    sb.table("user_ai_keys").delete().eq("user_id", auth.user_id).execute()
    return {"ok": True}
