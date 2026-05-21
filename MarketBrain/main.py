import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from bs4 import BeautifulSoup
import requests
import re
import unicodedata
import logging
from typing import Any, List
import numpy as np

app = FastAPI()
logger = logging.getLogger(__name__)

# C# Response model:
class PriceHistoryRequest(BaseModel):
    coin_name: str
    prices: List[float] 

# Analysis response
class AnalyticsResponse(BaseModel):
    trend: str 
    percentage_change: float
    volatility: float
    historical_prices: List[float]
    action_signal: str 

# Endpoint route
@app.post("/analyze")
async def analyze_prices(data: PriceHistoryRequest) -> AnalyticsResponse:
    if not data.prices or len(data.prices) < 2:
        return AnalyticsResponse(trend="STABLE", percentage_change=0.0, volatility=0.0, historical_prices=[], action_signal="HOLD")

    first_price = data.prices[0]
    last_price = data.prices[-1]

    if first_price == 0 or not np.isfinite(first_price) or not np.isfinite(last_price):
        change = 0.0
    else:
        change = ((last_price - first_price) / first_price) * 100
    
    prices_array = np.array(data.prices)
    volatility = float(np.std(prices_array))
    average_price = float(np.mean(prices_array))
    
    if change > 1.0:
        trend = "UP"
    elif change < -1.0:
        trend = "DOWN"
    else:
        trend = "STABLE"

    signal = "HOLD"

    if average_price != 0 and np.isfinite(average_price) and np.isfinite(last_price) and np.isfinite(volatility):
        price_to_avg_ratio = last_price / average_price
        if trend == "UP":
            if price_to_avg_ratio < 1.05: 
                signal = "BUY"
            else: 
                signal = "HOLD"
                
        elif trend == "DOWN":
            if price_to_avg_ratio < 0.95: 
                signal = "STRONG BUY" if volatility < average_price * 0.05 else "HOLD" 
            else:
                signal = "SELL" 
                
        elif trend == "STABLE":
            if volatility < average_price * 0.02: 
                signal = "BUY"

    return AnalyticsResponse(
        trend=trend, 
        percentage_change=round(change, 2), 
        volatility=round(volatility, 2),
        historical_prices=data.prices,
        action_signal=signal 
    )

# ==========================================
# HELPER FUNCTIONS (At top, outside the routes)
# ==========================================
def parse_brazilian_float(value: str) -> float:
    parsed = parse_optional_brazilian_float(value)
    return parsed if parsed is not None else 0.0


def parse_optional_brazilian_float(value: str | None) -> float | None:
    if not value or is_missing_value(value):
        return None

    # Keep only numeric separators/sign and digits so values like "R$ 9.136.895,50" parse correctly.
    clean_val = re.sub(r"[^0-9,.-]", "", value)
    if not clean_val or is_missing_value(clean_val):
        return None

    if "," in clean_val and "." in clean_val:
        clean_val = clean_val.replace(".", "").replace(",", ".")
    elif "," in clean_val:
        clean_val = clean_val.replace(",", ".")

    try:
        return float(clean_val.strip())
    except ValueError:
        return None


def parse_optional_brazilian_int(value: str | None) -> int | None:
    normalized_value = value
    if normalized_value:
        clean_val = re.sub(r"[^0-9,.-]", "", normalized_value)
        if "," not in clean_val and "." in clean_val:
            dot_groups = clean_val.split(".")
            if all(group.isdigit() for group in dot_groups) and all(len(group) == 3 for group in dot_groups[1:]):
                normalized_value = clean_val.replace(".", "")

    parsed = parse_optional_brazilian_float(normalized_value)
    if parsed is None or not parsed.is_integer():
        return None
    return int(parsed)


def normalize_label(label: str) -> str:
    if not label:
        return ""
    no_accents = "".join(
        c for c in unicodedata.normalize("NFKD", label)
        if not unicodedata.combining(c)
    )
    normalized = re.sub(r"\s+", " ", no_accents.upper()).strip()
    return normalized


def clean_text_value(value: str) -> str:
    if not value:
        return ""
    clean = re.sub(r"\s+", " ", value).strip()
    clean = clean.replace("arrow_forward", "").strip()
    # Ignore template placeholders coming from embedded scripts
    if re.fullmatch(r"\{[^}]+\}", clean):
        return ""
    return clean


def is_missing_value(value: str) -> bool:
    if not value:
        return True
    stripped = value.strip()
    return stripped in {"-", "--", "N/A", "NA", "null", "None"}


def is_valid_rating(value: str | None) -> bool:
    if not value:
        return False
    v = value.strip().upper()
    if v in {"DE", "DO", "DA", "DOS", "DAS"}:
        return False
    return re.fullmatch(r"[A-Z]{1,3}[+\-]?", v) is not None


def is_valid_quality_text(value: str | None) -> bool:
    if not value:
        return False
    v = value.strip()
    if v.lower() in {"de", "do", "da", "dos", "das"}:
        return False
    if len(v) >= 3:
        return True
    if len(v) == 2 and v.upper() in {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
        "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
        "RS", "RO", "RR", "SC", "SP", "SE", "TO",
    }:
        return True
    return False


def extract_kv_from_soup(soup: BeautifulSoup) -> dict[str, str]:
    data: dict[str, str] = {}

    def put(label: str, value: str) -> None:
        # StatusInvest labels sometimes include long help text; keep only core title.
        short_label = re.split(r"\bHELP_OUTLINE\b", label, maxsplit=1)[0].strip()
        key = normalize_label(short_label)
        val = clean_text_value(value)
        if not key:
            return

        current = data.get(key, "")
        if is_missing_value(current) and not is_missing_value(val):
            data[key] = val
            return

        if key not in data:
            data[key] = val

    # Primary indicator cards used by StatusInvest (title + value)
    for title in soup.select("h3.title, span.title, span.name, span.label"):
        label = title.get_text(" ", strip=True)
        container = title.find_parent("div")
        value_tag = None
        if container:
            value_tag = container.select_one("strong.value, span.value, strong.counter, span.counter")
        if not value_tag:
            value_tag = title.find_next(["strong", "span"], class_=["value", "counter"])
        if value_tag:
            put(label, value_tag.get_text(" ", strip=True))

    # table rows: th + td
    for row in soup.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            put(th.get_text(" ", strip=True), td.get_text(" ", strip=True))

    # dt/dd
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            put(dt.get_text(" ", strip=True), dd.get_text(" ", strip=True))

    # Known segment links
    seg_anchor = soup.select_one('a[href*="/fundos-imobiliarios/setor/"]')
    if seg_anchor:
        put("SEGMENTO", seg_anchor.get_text(" ", strip=True))
    sector_anchor = soup.select_one('a[href*="/acoes/setor/"]')
    if sector_anchor:
        put("SETOR", sector_anchor.get_text(" ", strip=True))

    return data


def normalize_fii_type(segment: str | None) -> str | None:
    if not segment:
        return None

    seg = normalize_label(segment)
    if "PAPEIS" in seg or "CRI" in seg:
        return "papel"
    if "MISTO" in seg or "FOF" in seg or "FUNDO DE FUNDOS" in seg:
        return "hibrido"
    return "tijolo"


def find_regex_group(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = clean_text_value(match.group(1))
            if value and not is_missing_value(value):
                return value
    return None

def get_first_raw(raw_data: dict[str, str], keys: list[str], include_dot_insensitive: bool = False) -> str | None:
    normalized_keys = [normalize_label(k) for k in keys]

    for normalized_key in normalized_keys:
        value = raw_data.get(normalized_key)
        if value and not is_missing_value(value):
            return value

    for existing_key, existing_value in raw_data.items():
        if is_missing_value(existing_value):
            continue
        if any(normalized_key in existing_key for normalized_key in normalized_keys):
            return existing_value

    if include_dot_insensitive:
        for existing_key, existing_value in raw_data.items():
            if is_missing_value(existing_value):
                continue
            if any(normalized_key.replace(".", "") in existing_key.replace(".", "") for normalized_key in normalized_keys):
                return existing_value
    return None


def ensure_fundamentals_found(result: dict[str, Any]) -> None:
    """Raise 404 when no fundamentals were extracted and only ticker is present."""
    if result and len(result) == 1 and "ticker" in result:
        logger.debug("No recognizable fundamentals extracted for ticker %s", result["ticker"])
        raise HTTPException(status_code=404, detail="Fundamentals not found for ticker.")

@app.get("/fundamentals/{asset_type}/{ticker}")
async def get_fundamentals(asset_type: str, ticker: str):
    if asset_type not in {"stock", "fii"}:
        raise HTTPException(status_code=400, detail="Unsupported asset type.")
    category = "acoes" if asset_type == "stock" else "fundos-imobiliarios"
    url = f"https://statusinvest.com.br/{category}/{ticker.lower()}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.Timeout as error:
        logger.warning("Timed out fetching fundamentals for %s/%s: %s", asset_type, ticker, error)
        raise HTTPException(status_code=504, detail="Upstream provider request timed out.") from error
    except requests.RequestException as error:
        logger.warning("Failed upstream request for %s/%s: %s", asset_type, ticker, error)
        raise HTTPException(status_code=502, detail="Failed to fetch fundamentals from upstream provider.") from error

    try:
        html = response.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")
        page_text = soup.get_text(" ", strip=True)
        raw_data = extract_kv_from_soup(soup)

        # 2. TARGETED MAPPING
        if asset_type == "stock":
            result: dict[str, Any] = {"ticker": ticker.upper()}

            stock_metrics = {
                "p_l": ["P/L", "P/L (TTM)"],
                "p_vp": ["P/VP", "P/VP (MRQ)"],
                "dy": ["D.Y", "YIELD", "DIVIDEND YIELD"],
                "roe": ["ROE"],
                "debt_ebitda": ["DÍV. LÍQUIDA/EBITDA", "DÍVIDA LÍQ./EBITDA", "DIV. LIQUIDA/EBITDA"],
                "cagr_5y": ["CAGR LUCROS 5 ANOS", "CAGR 5 ANOS"],
                "net_margin": ["M. LÍQUIDA", "MARGEM LÍQUIDA", "M. LIQUIDA"]
            }

            for key, aliases in stock_metrics.items():
                value = parse_optional_brazilian_float(get_first_raw(raw_data, aliases, include_dot_insensitive=True))
                if value is not None:
                    result[key] = value

            sector = get_first_raw(raw_data, ["SETOR"])
            if sector:
                result["sector"] = sector

            ensure_fundamentals_found(result)
            return result

        elif asset_type == "fii":
            # Detect Brick vs Paper using unique labels
            segment_label = raw_data.get(normalize_label("SEGMENTO"), "")
            is_paper_by_segment = "PAPEIS" in normalize_label(segment_label) or "CRI" in normalize_label(segment_label)
            is_brick = (
                any(normalize_label(k) in raw_data for k in ["VACÂNCIA FÍSICA", "Nº DE IMÓVEIS", "NÚMERO DE IMÓVEIS", "Nº IMÓVEIS"]) 
                or not is_paper_by_segment
            )

            result: dict[str, Any] = {"ticker": ticker.upper()}
            pvp = parse_optional_brazilian_float(get_first_raw(raw_data, ["P/VP", "P/VP (MRQ)"]))
            dy = parse_optional_brazilian_float(get_first_raw(raw_data, ["D.Y", "YIELD", "DIVIDEND YIELD"]))
            segment = get_first_raw(raw_data, ["SEGMENTO", "SETOR"])

            localizacao = get_first_raw(raw_data, ["LOCALIZAÇÃO", "LOCALIZACAO", "LOCALIZAÇÃO DOS IMÓVEIS", "LOCALIZACAO DOS IMOVEIS"])
            qualidade_imoveis = get_first_raw(raw_data, ["QUALIDADE DOS IMÓVEIS", "QUALIDADE DOS IMOVEIS", "QUALIDADE DO IMÓVEL", "QUALIDADE DO IMOVEL", "PADRÃO DOS IMÓVEIS", "PADRAO DOS IMOVEIS"])
            qualidade_cris = get_first_raw(raw_data, ["QUALIDADE DOS CRIS", "QUALIDADE CRI", "QUALIDADE DOS CRI"])

            # First-wave high-value FII fields.
            liquidez_media_diaria = parse_optional_brazilian_float(get_first_raw(raw_data, ["LIQ. MÉD. DIÁRIA", "LIQUIDEZ MEDIA DIARIA", "LIQUIDEZ DIARIA"]))
            valor_patrimonial_cota = parse_optional_brazilian_float(get_first_raw(raw_data, ["VALOR PATRIM. P/COTA", "VALOR PATRIMONIAL COTA", "VP/COTA"]))
            patrimonio_liquido = parse_optional_brazilian_float(get_first_raw(raw_data, ["PATRIMÔNIO", "PATRIMONIO LIQUIDO", "PATRIMONIO"]))
            numero_cotistas = parse_optional_brazilian_int(get_first_raw(raw_data, ["Nº DE COTISTAS", "NO DE COTISTAS", "NUMERO DE COTISTAS"]))
            ultimo_rendimento = parse_optional_brazilian_float(get_first_raw(raw_data, ["ÚLTIMO RENDIMENTO", "ULTIMO RENDIMENTO"]))
            data_pagamento = get_first_raw(raw_data, ["DATA PAGAMENTO", "DATA DE PAGAMENTO"])

            if pvp is not None:
                result["p_vp"] = pvp
            if dy is not None:
                result["dy"] = dy
            if segment:
                result["segment"] = segment

            tipo_fii = normalize_fii_type(segment)
            if tipo_fii:
                result["tipo_fii"] = tipo_fii

            if liquidez_media_diaria is not None:
                result["liquidez_media_diaria"] = liquidez_media_diaria
            if valor_patrimonial_cota is not None:
                result["valor_patrimonial_cota"] = valor_patrimonial_cota
            if patrimonio_liquido is not None:
                result["patrimonio_liquido"] = patrimonio_liquido
            if numero_cotistas is not None:
                result["numero_cotistas"] = numero_cotistas
            if ultimo_rendimento is not None:
                result["ultimo_rendimento"] = ultimo_rendimento
            if data_pagamento:
                result["data_pagamento"] = data_pagamento
            if is_valid_quality_text(localizacao):
                result["localizacao"] = localizacao
            if is_valid_quality_text(qualidade_imoveis):
                result["qualidade_imoveis"] = qualidade_imoveis
            if is_valid_quality_text(qualidade_cris):
                result["qualidade_cris"] = qualidade_cris

            if is_brick:
                vacancy_raw = get_first_raw(raw_data, ["VACÂNCIA FÍSICA", "VACÂNCIA FINANCEIRA", "VACÂNCIA"]) or find_regex_group(
                    page_text,
                    [
                        r"VAC[ÂA]NCIA(?:\s+F[ÍI]SICA)?\s*([0-9.,]+%?)",
                        r"VACANCY\s*([0-9.,]+%?)"
                    ]
                )
                properties_raw = get_first_raw(raw_data, ["Nº DE IMÓVEIS", "NÚMERO DE IMÓVEIS", "Nº IMÓVEIS"]) or find_regex_group(
                    page_text,
                    [r"N[ºO°]?\s*DE\s*IM[ÓO]VEIS\s*([0-9.,]+)"]
                )
                tenants_raw = get_first_raw(raw_data, ["Nº DE INQUILINOS", "NUMERO DE INQUILINOS", "N INQUILINOS"]) or find_regex_group(
                    page_text,
                    [r"N[ºO°]?\s*DE\s*INQUILINOS\s*([0-9.,]+)"]
                )
                largest_tenant_raw = get_first_raw(raw_data, ["MAIOR INQUILINO (%)", "MAIOR INQUILINO"]) or find_regex_group(
                    page_text,
                    [r"MAIOR\s+INQUILINO(?:\s*\(%\))?\s*([0-9.,]+%?)"]
                )
                avg_contract_term = get_first_raw(raw_data, ["PRAZO MÉDIO DOS CONTRATOS", "PRAZO MÉDIO"]) or find_regex_group(
                    page_text,
                    [r"PRAZO\s+M[ÉE]DIO(?:\s+DOS\s+CONTRATOS)?\s*([0-9.,]+\s*(?:ANOS?|MESES?))"]
                )
                contract_type = get_first_raw(raw_data, ["TIPO DE CONTRATO", "TIPO CONTRATO"]) or find_regex_group(
                    page_text,
                    [r"TIPO\s+DE\s+CONTRATO\s*(T[ÍI]PICO|AT[ÍI]PICO|MISTO)"]
                )

                vacancy = parse_optional_brazilian_float(vacancy_raw)
                largest_tenant = parse_optional_brazilian_float(largest_tenant_raw)

                inadimplencia_raw = get_first_raw(raw_data, ["INADIMPLÊNCIA", "INADIMPLENCIA"]) or find_regex_group(
                    page_text,
                    [
                        r"INADIMPL[ÊE]NCIA(?:\s+(?:DE\s+)?ALUGUEL)?\s*([0-9.,]+%?)",
                        r"DEFAULT\s*([0-9.,]+%?)"
                    ]
                )
                inadimplencia = parse_optional_brazilian_float(inadimplencia_raw)

                if vacancy is not None:
                    result["vacancy"] = vacancy
                if properties_raw:
                    pc = parse_optional_brazilian_int(properties_raw)
                    if pc is not None:
                        result["properties_count"] = pc
                if tenants_raw:
                    tn = parse_optional_brazilian_int(tenants_raw)
                    if tn is not None:
                        result["tenants_count"] = tn
                if largest_tenant is not None:
                    result["largest_tenant_pct"] = largest_tenant
                if avg_contract_term:
                    result["avg_contract_term"] = avg_contract_term
                if contract_type:
                    result["contract_type"] = contract_type
                if inadimplencia is not None:
                    result["inadimplencia"] = inadimplencia

                ensure_fundamentals_found(result)
                return result
            else:
                cash_available = parse_optional_brazilian_float(get_first_raw(raw_data, ["VALOR EM CAIXA", "CAIXA", "DISPONIBILIDADE"])) or parse_optional_brazilian_float(find_regex_group(
                    page_text,
                    [r"(?:VALOR\s+)?EM\s+CAIXA\s*(?:R\$)?\s*([0-9.,]+)", r"CAIXA\s+([0-9.,]+)"]
                ))
                cdi_ipca = get_first_raw(raw_data, ["% CDI/IPCA", "CDI/IPCA", "CDI", "IPCA", "INDEXADOR"]) or find_regex_group(
                    page_text,
                    [
                        r"CDI\s*/\s*IPCA\s*([0-9.,]+%?)",
                        r"IPCA\s*\+\s*([0-9.,]+%?)",
                        r"CDI\s*\+\s*([0-9.,]+%?)",
                        r"(?:% DO )CDI\s*([0-9.,]+%?)"
                    ]
                )
                inadimplencia_raw = get_first_raw(raw_data, ["INADIMPLÊNCIA", "INADIMPLENCIA"]) or find_regex_group(
                    page_text,
                    [
                        r"INADIMPL[ÊE]NCIA\s*([0-9.,]+%?)",
                        r"DEFAULT\s*([0-9.,]+%?)"
                    ]
                )
                inadimplencia = parse_optional_brazilian_float(inadimplencia_raw)
                cri_ratings = get_first_raw(raw_data, ["RATING DOS CRIS", "RATING", "RATING CRI", "RATING CRIS"]) or find_regex_group(
                    page_text,
                    [
                        r"RATING(?:\s+(?:MÉDIO|M[ÉE]DIO))?(?:\s+DOS\s+CRIS?)?\s*([A-Z]{1,3}[+\-]?)",
                        r"CRI\s+RATING\s*([A-Z]{1,3}[+\-]?)",
                        r"([A-Z]{1,3}[+\-]?)\s+(?:RATING|CRI)"
                    ]
                )
                dividend_payout_raw = get_first_raw(raw_data, ["PAYOUT", "DIVIDEND PAYOUT"]) or find_regex_group(
                    page_text,
                    [
                        r"PAYOUT\s*([0-9.,]+%?)",
                        r"(?:DIVIDEND|DISTRIBUIÇÃO)\s+PAYOUT\s*([0-9.,]+%?)"
                    ]
                )
                dividend_payout = parse_optional_brazilian_float(dividend_payout_raw)

                if cdi_ipca:
                    result["%_cdi_ipca"] = cdi_ipca
                if inadimplencia is not None and inadimplencia > 0:
                    result["inadimplencia"] = inadimplencia
                if cri_ratings and is_valid_rating(cri_ratings):
                    result["cri_ratings"] = cri_ratings
                if cash_available is not None and cash_available > 0:
                    result["cash_available"] = cash_available
                if dividend_payout is not None and dividend_payout > 0:
                    result["dividend_payout"] = dividend_payout

                ensure_fundamentals_found(result)
                return result

    except HTTPException:
        # Re-raise HTTPException to preserve intended API errors.
        raise
    except Exception:
        logger.exception("Internal scraper error while parsing fundamentals for %s/%s", asset_type, ticker)
        raise HTTPException(status_code=500, detail="Internal scraper error.")
