"""User subscription tier and entitlement management.

DB schema (apply once via Supabase SQL editor):

    -- Subscription tiers (written by Razorpay webhook via service role in Phase 2)
    create table user_subscriptions (
      user_id            uuid primary key references auth.users(id) on delete cascade,
      tier               text not null default 'free' check (tier in ('free','premium')),
      status             text not null default 'active'
                           check (status in ('active','trialing','past_due','canceled')),
      provider           text,
      provider_sub_id    text,
      current_period_end timestamptz,
      updated_at         timestamptz not null default now()
    );
    alter table user_subscriptions enable row level security;
    create policy "users read own sub" on user_subscriptions
      for select using (auth.uid() = user_id);

    -- One-time feature trials (Phase 2 consumption logic)
    create table user_feature_trials (
      id          uuid primary key default gen_random_uuid(),
      user_id     uuid not null references auth.users(id) on delete cascade,
      feature_key text not null,
      used_at     timestamptz not null default now(),
      unique (user_id, feature_key)
    );
    alter table user_feature_trials enable row level security;
    create policy "users own trials" on user_feature_trials
      for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

    -- Daily rolling counters for rate-limited free features
    create table user_usage_counters (
      user_id     uuid not null references auth.users(id) on delete cascade,
      counter_key text not null,
      window_date date not null default current_date,
      count       int  not null default 0,
      primary key (user_id, counter_key, window_date)
    );
    alter table user_usage_counters enable row level security;
    create policy "users own counters" on user_usage_counters
      for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
"""

from fastapi import APIRouter, Depends
from ..deps import get_current_user, supabase_client, get_subscription, AuthUser

router = APIRouter()

# Feature key → whether premium tier is required (True = premium only)
FEATURE_TIERS: dict[str, bool] = {
    "market_overview":      False,
    "sector_detail":        False,
    "value_screen":         False,
    "basic_fundamentals":   False,
    "models_page":          False,
    "news_hub_basic":       False,
    "earnings":             True,
    "volatility":           True,
    "ml_signals":           True,
    "technical_analysis":   True,
    "ai_overview":          True,
    "portfolio_optimize":   True,
    "backtesting":          True,
    "news_impact":          True,
    "unlimited_portfolios": True,
    "alerts":               True,
    "export":               True,
    "newsletter":           True,
    "historical_charts":    True,
    "sector_comparison":    True,
    "advanced_screeners":   True,
}


@router.get("/me")
def get_my_subscription(auth: AuthUser = Depends(get_current_user)):
    return get_subscription(auth)


@router.get("/entitlements")
def get_entitlements(auth: AuthUser = Depends(get_current_user)):
    sub  = get_subscription(auth)
    tier = sub["tier"]
    return {key: (not premium_only or tier == "premium")
            for key, premium_only in FEATURE_TIERS.items()}


@router.get("/trials")
def get_trials(auth: AuthUser = Depends(get_current_user)):
    sb  = supabase_client(auth)
    res = (sb.table("user_feature_trials")
             .select("feature_key")
             .eq("user_id", auth.user_id)
             .execute())
    used = {row["feature_key"] for row in (res.data or [])}
    trial_features = [
        "portfolio_analysis",
        "rebalance_suggestion",
        "allocation_suggestion",
        "ai_portfolio_review",
        "intrinsic_value_report",
    ]
    return {key: key in used for key in trial_features}
