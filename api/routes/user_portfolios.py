from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..deps import get_current_user, supabase_client, AuthUser

router = APIRouter()


class SavePortfolioRequest(BaseModel):
    name:            str
    tickers:         list[str]
    weights:         dict[str, float]
    capital:         float | None = None
    portfolio_type:  str | None = None
    optimize_result: dict[str, Any] | None = None


@router.get("")
def list_portfolios(auth: AuthUser = Depends(get_current_user)):
    sb = supabase_client(auth)
    res = (sb.table("portfolios")
             .select("id, name, tickers, weights, capital, portfolio_type, invested_at, created_at")
             .order("created_at", desc=True)
             .execute())
    return res.data


@router.post("")
def save_portfolio(body: SavePortfolioRequest, auth: AuthUser = Depends(get_current_user)):
    sb = supabase_client(auth)
    row = {
        "user_id":        auth.user_id,
        "name":           body.name,
        "tickers":        body.tickers,
        "weights":        body.weights,
        "capital":        body.capital,
        "portfolio_type": body.portfolio_type,
        "optimize_result": body.optimize_result,
    }
    res = sb.table("portfolios").insert(row).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to save portfolio")
    return res.data[0]


@router.get("/{portfolio_id}")
def get_portfolio(portfolio_id: str, auth: AuthUser = Depends(get_current_user)):
    sb = supabase_client(auth)
    port = sb.table("portfolios").select("*").eq("id", portfolio_id).single().execute()
    if not port.data:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    bt = (sb.table("backtest_results")
            .select("result, created_at")
            .eq("portfolio_id", portfolio_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute())
    return {
        **port.data,
        "backtest_result": bt.data[0]["result"] if bt.data else None,
    }


@router.delete("/{portfolio_id}")
def delete_portfolio(portfolio_id: str, auth: AuthUser = Depends(get_current_user)):
    sb = supabase_client(auth)
    sb.table("portfolios").delete().eq("id", portfolio_id).execute()
    return {"ok": True}


@router.post("/{portfolio_id}/backtest")
def save_backtest(portfolio_id: str, body: dict[str, Any], auth: AuthUser = Depends(get_current_user)):
    sb = supabase_client(auth)
    res = sb.table("backtest_results").insert({
        "portfolio_id": portfolio_id,
        "user_id":      auth.user_id,
        "result":       body,
    }).execute()
    return res.data[0] if res.data else {"ok": True}
