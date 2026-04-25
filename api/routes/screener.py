from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.screeners import magic_formula_rank, qarp_screener
import pandas as pd

router = APIRouter()


class TickerList(BaseModel):
    tickers: list[str]


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    return df.fillna(0).to_dict(orient="records")


@router.post("/magic-formula")
def run_magic_formula(body: TickerList):
    try:
        df = magic_formula_rank(body.tickers)
        return {"results": _df_to_records(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qarp")
def run_qarp(body: TickerList):
    try:
        df = qarp_screener(body.tickers)
        return {"results": _df_to_records(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
