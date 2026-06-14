import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from bs4 import BeautifulSoup
import requests
import logging
import unicodedata
from typing import Any, List
import numpy as np
import re

app = FastAPI()
logger = logging.getLogger(__name__)

# --- Models ---
class PriceHistoryRequest(BaseModel):
    coin_name: str
    prices: List[float] 

class AnalyticsResponse(BaseModel):
    trend: str 
    percentage_change: float
    volatility: float
    historical_prices: List[float]
    action_signal: str 

# --- Endpoints ---
@app.post("/analyze")
async def analyze_prices(data: PriceHistoryRequest) -> AnalyticsResponse:
    if not data.prices or len(data.prices) < 2:
        return AnalyticsResponse(trend="STABLE", percentage_change=0.0, volatility=0.0, historical_prices=[], action_signal="HOLD")

    first_price = data.prices[0]
    last_price = data.prices[-1]
    change = ((last_price - first_price) / first_price) * 100 if first_price != 0 else 0.0
    
    prices_array = np.array(data.prices)
    volatility = float(np.std(prices_array))
    average_price = float(np.mean(prices_array))
    
    trend = "UP" if change > 1.0 else "DOWN" if change < -1.0 else "STABLE"
    signal = "HOLD"

    if average_price != 0:
        ratio = last_price / average_price
        if trend == "UP" and ratio < 1.05: signal = "BUY"
        elif trend == "DOWN" and ratio < 0.95: signal = "STRONG BUY" if volatility < average_price * 0.05 else "HOLD"
        elif trend == "STABLE" and volatility < average_price * 0.02: signal = "BUY"

    return AnalyticsResponse(
        trend=trend, percentage_change=round(change, 2), 
        volatility=round(volatility, 2), historical_prices=data.prices, action_signal=signal 
    )

# ==========================================
# FUNDAMENTUS ENGINE (THREAD-SAFE PARSER)
# ==========================================

def parse_brazilian_number(value: str) -> float | None:
    if not value or value.strip() in {"-", "--", "N/A", "", "0,00%", "?"}: return None
    clean_val = value.replace("%", "").strip()
    if "," in clean_val and "." in clean_val: clean_val = clean_val.replace(".", "").replace(",", ".")
    elif "," in clean_val: clean_val = clean_val.replace(",", ".")
    elif "." in clean_val: clean_val = clean_val.replace(".", "")
    try: return float(clean_val)
    except ValueError: return None


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).upper()


def fix_mojibake(value: str | None) -> str:
    if not value:
        return ""
    clean = value.strip()
    if "Ã" in clean or "Â" in clean:
        try:
            repaired = clean.encode("latin1").decode("utf-8")
            return repaired.strip()
        except (UnicodeEncodeError, UnicodeDecodeError):
            return clean
    return clean


def get_first_value(data: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", "-", "--", "N/A"):
            return value
    return default


def classify_fii_type(ticker: str, raw_data: dict[str, Any]) -> str:
    ticker_norm = ticker.upper().strip()

    # Known edge cases where providers frequently label the segment ambiguously.
    paper_overrides = {"MXRF11", "KNCR11", "SNCI11", "CPTS11", "RBRR11", "KNSC11"}
    fof_overrides = {"BCFF11", "RBRF11", "XPSF11", "HFOF11", "HGFF11"}

    if ticker_norm in paper_overrides:
        return "papel"
    if ticker_norm in fof_overrides:
        return "fof"

    nome = raw_data.get("NOME", "")
    empresa = raw_data.get("EMPRESA", "")
    segmento = raw_data.get("SEGMENTO", "")
    text_to_analyze = normalize_text(f"{nome} {empresa} {segmento}")

    fof_keywords = ["FOF", "FUNDO DE FUNDOS", "FUNDOS DE FUNDOS", "COTAS DE FUNDOS"]
    paper_keywords = [
        "PAPEL", "PAPEIS", "RECEBIVEIS", "CRI", "CRIS", "CERTIFICADOS",
        "TITULOS", "VAL. MOB", "VAL MOB", "VALORES MOBILIARIOS", "TVM"
    ]
    hybrid_keywords = ["MISTO", "HIBRIDO", "HIBRIDA"]

    if any(keyword in text_to_analyze for keyword in fof_keywords):
        return "fof"
    if any(keyword in text_to_analyze for keyword in paper_keywords):
        return "papel"
    if any(keyword in text_to_analyze for keyword in hybrid_keywords):
        return "hibrido"

    properties_count = parse_brazilian_number(raw_data.get("QTD IMÓVEIS", ""))
    vacancy = parse_brazilian_number(raw_data.get("VACÂNCIA MÉDIA", ""))
    if properties_count == 0 and vacancy is None:
        return "papel"

    return "tijolo"

def fetch_fundamentus_data(ticker_symbol: str) -> dict:
    url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker_symbol.upper()}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "Accept": "text/html"
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    detected_encoding = response.apparent_encoding or response.encoding or "utf-8"
    html = response.content.decode(detected_encoding, errors="replace")
    
    if "Nenhum papel encontrado" in html:
        raise ValueError("Asset not found on Fundamentus.")

    soup = BeautifulSoup(html, "lxml")
    data = {}
    for label_td in soup.select("td.label"):
        label = fix_mojibake(label_td.get_text(strip=True)).replace("?", "").upper()
        value_td = label_td.find_next_sibling("td", class_="data")
        if label and value_td:
            data[label] = fix_mojibake(value_td.get_text(strip=True))
    return data


def build_fundamentals_payload(asset_type: str, ticker: str, raw_data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"ticker": ticker.upper()}

    if asset_type == "stock":
        result["sector"] = raw_data.get("SETOR", "N/A")
        result["p_l"] = parse_brazilian_number(raw_data.get("P/L", ""))
        result["p_vp"] = parse_brazilian_number(raw_data.get("P/VP", ""))
        result["dy"] = parse_brazilian_number(raw_data.get("DIV. YIELD", ""))
        result["roe"] = parse_brazilian_number(raw_data.get("ROE", ""))
        result["net_margin"] = parse_brazilian_number(
            get_first_value(raw_data, ["MARG. LÍQUIDA", "MARGEM LÍQUIDA"], "")
        )
        result["debt_ebitda"] = parse_brazilian_number(
            get_first_value(raw_data, ["DÍV. LÍQUIDA / EBITDA", "DÍV LIQ / EBITDA", "DÍV LÍQ / PATRIM"], "")
        )
        result["cagr_5y"] = parse_brazilian_number(
            get_first_value(raw_data, ["CRES. LUCRO (5A)", "CRES. REC (5A)"], "")
        )
        result["market_cap"] = parse_brazilian_number(raw_data.get("VALOR DE MERCADO", ""))
        result["ev_ebit"] = parse_brazilian_number(raw_data.get("EV / EBIT", ""))
        result["ev_ebitda"] = parse_brazilian_number(raw_data.get("EV / EBITDA", ""))
        result["cagr_revenue"] = parse_brazilian_number(raw_data.get("CRES. REC (5A)", ""))
        result["cagr_profit"] = None
        return result

    tipo_fii = classify_fii_type(ticker, raw_data)

    result["segment"] = raw_data.get("SEGMENTO", "N/A")
    result["tipo_fii"] = tipo_fii

    result["p_vp"] = parse_brazilian_number(raw_data.get("P/VP", ""))
    result["dy"] = parse_brazilian_number(raw_data.get("DIV. YIELD", ""))
    result["numero_cotistas"] = parse_brazilian_number(raw_data.get("QTD COTISTAS", ""))
    result["properties_count"] = parse_brazilian_number(raw_data.get("QTD IMÓVEIS", ""))
    result["vacancy"] = parse_brazilian_number(raw_data.get("VACÂNCIA MÉDIA", ""))

    result["tenant_count"] = parse_brazilian_number(
        get_first_value(raw_data, ["QTD INQUILINOS", "QUANTIDADE DE INQUILINOS"], "")
    )
    result["largest_tenant_pct"] = parse_brazilian_number(
        get_first_value(raw_data, ["MAIOR INQUILINO", "MAIOR INQUILINO (%)", "CONCENTRAÇÃO MAIOR INQUILINO"], "")
    )
    result["avg_contract_term"] = get_first_value(
        raw_data,
        ["PRAZO MÉDIO DOS CONTRATOS", "PRAZO MÉDIO CONTRATOS", "PRAZO MÉDIO"],
        None
    )
    result["contract_type"] = get_first_value(
        raw_data,
        ["TIPO DE CONTRATO", "TIPO CONTRATO", "CONTRATOS"],
        None
    )

    result["inadimplencia"] = parse_brazilian_number(
        get_first_value(raw_data, ["INADIMPLÊNCIA", "INADIMPLENCIA"], "")
    )
    result["%_cdi_ipca"] = get_first_value(
        raw_data,
        ["% CDI/IPCA", "% CDI", "% IPCA", "CDI/IPCA"],
        None
    )
    result["cri_ratings"] = get_first_value(raw_data, ["RATING CRI", "RATING DOS CRIS", "RATINGS"], None)
    result["cash_available"] = parse_brazilian_number(
        get_first_value(raw_data, ["CAIXA DISPONÍVEL", "CAIXA", "DISPONIBILIDADES"], "")
    )
    result["liquidity"] = parse_brazilian_number(raw_data.get("VOL $ MÉD (2M)", ""))
    result["net_worth"] = parse_brazilian_number(raw_data.get("PATRIMÔNIO LÍQ", "") or raw_data.get("PATRIM. LÍQ", ""))
    result["last_dividend"] = parse_brazilian_number(raw_data.get("ÚLTIMO RENDIMENTO", ""))

    result["dividend_payout"] = parse_brazilian_number(
        get_first_value(raw_data, ["DIVIDEND PAYOUT", "PAYOUT", "PAYOUT DE DIVIDENDOS"], "")
    )

    if result.get("dividend_payout") is None:
        distributed = parse_brazilian_number(
            get_first_value(raw_data, ["REND. DISTRIBUÍDO", "REND. DISTRIBUIDO"], "")
        )
        ffo_value = parse_brazilian_number(raw_data.get("FFO", ""))
        if distributed is not None and ffo_value and ffo_value > 0:
            result["dividend_payout"] = round((distributed / ffo_value) * 100.0, 2)

    return result

@app.get("/fundamentals/{asset_type}/{ticker}")
async def get_fundamentals(asset_type: str, ticker: str):
    if asset_type not in {"stock", "fii"}:
        raise HTTPException(status_code=400, detail="Unsupported asset type.")
    
    try:
        raw_data = await asyncio.to_thread(fetch_fundamentus_data, ticker)
    except ValueError:
        raise HTTPException(status_code=404, detail="Asset not found.")
    except Exception as e:
        logger.error(f"Fundamentus fetch failed for {ticker}: {e}")
        raise HTTPException(status_code=502, detail="Upstream provider failed.")

    has_setor = "SETOR" in raw_data and raw_data["SETOR"] != ""
    has_segmento = "SEGMENTO" in raw_data and raw_data["SEGMENTO"] != ""

    if asset_type == "fii" and has_setor and not has_segmento:
        raise HTTPException(status_code=404, detail="Requested FII, but is Stock. Trigger fallback.")
    if asset_type == "stock" and has_segmento and not has_setor:
        raise HTTPException(status_code=404, detail="Requested Stock, but is FII. Trigger fallback.")

    try:
        return build_fundamentals_payload(asset_type, ticker, raw_data)
    except Exception as ex:
        logger.exception("Error building fundamentals payload for %s", ticker)
        raise HTTPException(status_code=500, detail=f"Internal payload builder error: {ex}")


@app.get("/fundamentals-debug/{ticker}")
async def get_fundamentals_debug(ticker: str, asset_type: str = "fii"):
    if asset_type not in {"stock", "fii"}:
        raise HTTPException(status_code=400, detail="Unsupported asset type.")

    try:
        raw_data = await asyncio.to_thread(fetch_fundamentus_data, ticker)
    except ValueError:
        raise HTTPException(status_code=404, detail="Asset not found.")
    except Exception as e:
        logger.error(f"Fundamentus fetch failed for {ticker}: {e}")
        raise HTTPException(status_code=502, detail="Upstream provider failed.")

    has_setor = "SETOR" in raw_data and raw_data["SETOR"] != ""
    has_segmento = "SEGMENTO" in raw_data and raw_data["SEGMENTO"] != ""
    inferred_asset_kind = "fii" if has_segmento and not has_setor else "stock" if has_setor and not has_segmento else "unknown"

    parsed = build_fundamentals_payload(asset_type, ticker, raw_data)

    return {
        "ticker": ticker.upper(),
        "asset_type_requested": asset_type,
        "asset_type_inferred": inferred_asset_kind,
        "parsed": parsed,
        "raw_labels": raw_data,
        "raw_label_count": len(raw_data),
        "raw_label_keys": sorted(raw_data.keys())
    }