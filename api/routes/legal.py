"""Legal disclaimer acceptance flow.

DB schema (apply once via Supabase SQL editor):

    create table user_disclaimer_acceptances (
      id          uuid primary key default gen_random_uuid(),
      user_id     uuid not null references auth.users(id) on delete cascade,
      version     text not null,
      accepted_at timestamptz not null default now(),
      unique (user_id, version)
    );
    alter table user_disclaimer_acceptances enable row level security;
    create policy "users own their acceptances" on user_disclaimer_acceptances
      for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
"""

from fastapi import APIRouter, Depends
from ..deps import get_current_user, supabase_client, AuthUser

router = APIRouter()

CURRENT_DISCLAIMER_VERSION = "2026-06-15"

DISCLAIMER_TEXT = (
    "QuantHub is an educational and analytical platform for Indian markets. "
    "By clicking 'I Agree' you acknowledge and accept all of the following:\n\n"
    "1. Educational purposes only. All content, scores, screens, and model outputs on "
    "QuantHub are provided solely for education and information. QuantHub does not provide "
    "investment advice and is not a SEBI-registered investment adviser or research analyst.\n\n"
    "2. Not investment advice or a recommendation. Nothing on this platform constitutes a "
    "recommendation, solicitation, or offer to buy, sell, or hold any security or financial "
    "instrument.\n\n"
    "3. Models are mathematical estimates. All valuations, 'fair values,' forecasts, signals, "
    "and model outputs are results of mathematical models based on assumptions that may be "
    "incorrect. They are estimates, not facts or guarantees.\n\n"
    "4. Public data may be inaccurate or delayed. Data is aggregated from third-party public "
    "sources (including NSE, BSE, Yahoo Finance, and others) and may contain errors, "
    "omissions, or delays. We do not warrant its accuracy or completeness.\n\n"
    "5. Past performance does not guarantee future results. Backtested or historical results "
    "shown are hypothetical and do not predict future returns. All investments carry risk, "
    "including the possible loss of principal.\n\n"
    "6. Do your own due diligence. You are solely responsible for your investment decisions "
    "and any resulting gains or losses. The platform is a research tool, not a substitute "
    "for your own analysis.\n\n"
    "7. Consult a qualified professional. Before making any investment decisions, consult a "
    "SEBI-registered investment adviser, research analyst, or other qualified financial "
    "professional who understands your individual financial situation and goals."
)


@router.get("/disclaimer")
def get_disclaimer():
    return {"version": CURRENT_DISCLAIMER_VERSION, "text": DISCLAIMER_TEXT}


@router.get("/disclaimer/status")
def get_disclaimer_status(auth: AuthUser = Depends(get_current_user)):
    sb  = supabase_client(auth)
    res = (sb.table("user_disclaimer_acceptances")
             .select("id")
             .eq("user_id", auth.user_id)
             .eq("version", CURRENT_DISCLAIMER_VERSION)
             .limit(1)
             .execute())
    return {"accepted": bool(res.data), "current_version": CURRENT_DISCLAIMER_VERSION}


@router.post("/disclaimer/accept")
def accept_disclaimer(auth: AuthUser = Depends(get_current_user)):
    sb = supabase_client(auth)
    sb.table("user_disclaimer_acceptances").upsert(
        {"user_id": auth.user_id, "version": CURRENT_DISCLAIMER_VERSION},
        on_conflict="user_id,version",
    ).execute()
    return {"ok": True}
