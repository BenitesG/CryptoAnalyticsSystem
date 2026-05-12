from fastapi import FastAPI
from pydantic import BaseModel
from bs4 import BeautifulSoup
import requests
import re
import unicodedata
from typing import Any

app = FastAPI()

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


def safe_int(value: str) -> int:
    try:
        return int(parse_brazilian_float(value))
    except Exception:
        return 0


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

# NOTE: helper imports and the `parse_brazilian_float` function above remain unchanged.

class StockFundamentals(BaseModel):
    ticker: str
    p_l: float
    p_vp: float
    dy: float
    roe: float
    debt_ebitda: float
    cagr_5y: float
    net_margin: float

class BrickFiiFundamentals(BaseModel):
    ticker: str
    p_vp: float
    dy: float
    vacancy: float
    properties_count: int
    segment: str

class PaperFiiFundamentals(BaseModel):
    ticker: str
    p_vp: float
    dy: float
    cash_available: float
    segment: str 

@app.get("/fundamentals/{asset_type}/{ticker}")
async def get_fundamentals(asset_type: str, ticker: str):
    category = "acoes" if asset_type == "stock" else "fundos-imobiliarios"
    url = f"https://statusinvest.com.br/{category}/{ticker.lower()}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        html = response.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")
        page_text = soup.get_text(" ", strip=True)
        raw_data = extract_kv_from_soup(soup)

        # 2. TARGETED MAPPING
        if asset_type == "stock":
            def get_first_raw(keys: list[str]) -> str | None:
                for k in keys:
                    v = raw_data.get(normalize_label(k))
                    if v and not is_missing_value(v):
                        return v

                # Fallback by partial key match for noisy labels
                for existing_key, existing_value in raw_data.items():
                    if is_missing_value(existing_value):
                        continue
                    if any(normalize_label(k) in existing_key for k in keys):
                        return existing_value

                for existing_key, existing_value in raw_data.items():
                    if is_missing_value(existing_value):
                        continue
                    if any(normalize_label(k).replace(".", "") in existing_key.replace(".", "") for k in keys):
                        return existing_value
                return None

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
                value = parse_optional_brazilian_float(get_first_raw(aliases))
                if value is not None:
                    result[key] = value

            sector = get_first_raw(["SETOR"])
            if sector:
                result["sector"] = sector

            return result

        elif asset_type == "fii":
            # Detect Brick vs Paper using unique labels
            segment_label = raw_data.get(normalize_label("SEGMENTO"), "")
            is_paper_by_segment = "PAPEIS" in normalize_label(segment_label) or "CRI" in normalize_label(segment_label)
            is_brick = (
                any(normalize_label(k) in raw_data for k in ["VACÂNCIA FÍSICA", "Nº DE IMÓVEIS", "NÚMERO DE IMÓVEIS", "Nº IMÓVEIS"]) 
                or not is_paper_by_segment
            )

            def get_first_raw(keys: list[str]) -> str | None:
                for k in keys:
                    v = raw_data.get(normalize_label(k))
                    if v and not is_missing_value(v):
                        return v

                for existing_key, existing_value in raw_data.items():
                    if is_missing_value(existing_value):
                        continue
                    if any(normalize_label(k) in existing_key for k in keys):
                        return existing_value
                return None

            result: dict[str, Any] = {"ticker": ticker.upper()}
            pvp = parse_optional_brazilian_float(get_first_raw(["P/VP", "P/VP (MRQ)"]))
            dy = parse_optional_brazilian_float(get_first_raw(["D.Y", "YIELD", "DIVIDEND YIELD"]))
            segment = get_first_raw(["SEGMENTO", "SETOR"])

            # First-wave high-value FII fields.
            liquidez_media_diaria = parse_optional_brazilian_float(get_first_raw(["LIQ. MÉD. DIÁRIA", "LIQUIDEZ MEDIA DIARIA", "LIQUIDEZ DIARIA"]))
            valor_patrimonial_cota = parse_optional_brazilian_float(get_first_raw(["VALOR PATRIM. P/COTA", "VALOR PATRIMONIAL COTA", "VP/COTA"]))
            patrimonio_liquido = parse_optional_brazilian_float(get_first_raw(["PATRIMÔNIO", "PATRIMONIO LIQUIDO", "PATRIMONIO"]))
            numero_cotistas = parse_optional_brazilian_float(get_first_raw(["Nº DE COTISTAS", "NO DE COTISTAS", "NUMERO DE COTISTAS"]))
            ultimo_rendimento = parse_optional_brazilian_float(get_first_raw(["ÚLTIMO RENDIMENTO", "ULTIMO RENDIMENTO"]))
            data_pagamento = get_first_raw(["DATA PAGAMENTO", "DATA DE PAGAMENTO"])

            if pvp is not None:
                result["p_vp"] = pvp
            if dy is not None:
                result["dy"] = dy
            if segment:
                result["segment"] = segment

            tipo_fii = normalize_fii_type(segment)
            if tipo_fii:
                result["tipo_fii"] = tipo_fii

            if liquidez_media_diaria is not None and liquidez_media_diaria != 0.0:
                result["liquidez_media_diaria"] = liquidez_media_diaria
            if valor_patrimonial_cota is not None and valor_patrimonial_cota != 0.0:
                result["valor_patrimonial_cota"] = valor_patrimonial_cota
            if patrimonio_liquido is not None and patrimonio_liquido != 0.0:
                result["patrimonio_liquido"] = patrimonio_liquido
            if numero_cotistas is not None and int(numero_cotistas) != 0:
                result["numero_cotistas"] = int(numero_cotistas)
            if ultimo_rendimento is not None and ultimo_rendimento != 0.0:
                result["ultimo_rendimento"] = ultimo_rendimento
            if data_pagamento:
                result["data_pagamento"] = data_pagamento

            if is_brick:
                vacancy_raw = get_first_raw(["VACÂNCIA FÍSICA", "VACÂNCIA"]) or find_regex_group(
                    page_text,
                    [
                        r"VAC[ÂA]NCIA(?:\s+F[ÍI]SICA)?\s*([0-9.,]+%?)",
                        r"VACANCY\s*([0-9.,]+%?)"
                    ]
                )
                properties_raw = get_first_raw(["Nº DE IMÓVEIS", "NÚMERO DE IMÓVEIS", "Nº IMÓVEIS"]) or find_regex_group(
                    page_text,
                    [r"N[ºO°]?\s*DE\s*IM[ÓO]VEIS\s*([0-9.,]+)"]
                )
                tenants_raw = get_first_raw(["Nº DE INQUILINOS", "NUMERO DE INQUILINOS", "N INQUILINOS"]) or find_regex_group(
                    page_text,
                    [r"N[ºO°]?\s*DE\s*INQUILINOS\s*([0-9.,]+)"]
                )
                largest_tenant_raw = get_first_raw(["MAIOR INQUILINO (%)", "MAIOR INQUILINO"]) or find_regex_group(
                    page_text,
                    [r"MAIOR\s+INQUILINO(?:\s*\(%\))?\s*([0-9.,]+%?)"]
                )
                avg_contract_term = get_first_raw(["PRAZO MÉDIO DOS CONTRATOS", "PRAZO MÉDIO"]) or find_regex_group(
                    page_text,
                    [r"PRAZO\s+M[ÉE]DIO(?:\s+DOS\s+CONTRATOS)?\s*([0-9.,]+\s*(?:ANOS?|MESES?))"]
                )
                contract_type = get_first_raw(["TIPO DE CONTRATO", "TIPO CONTRATO"]) or find_regex_group(
                    page_text,
                    [r"TIPO\s+DE\s+CONTRATO\s*(T[ÍI]PICO|AT[ÍI]PICO|MISTO)"]
                )

                vacancy = parse_optional_brazilian_float(vacancy_raw)
                largest_tenant = parse_optional_brazilian_float(largest_tenant_raw)

                inadimplencia_raw = get_first_raw(["INADIMPLÊNCIA", "INADIMPLENCIA"]) or find_regex_group(
                    page_text,
                    [r"INADIMPL[ÊE]NCIA\s*([0-9.,]+%?)"]
                )
                inadimplencia = parse_optional_brazilian_float(inadimplencia_raw)

                if vacancy is not None and vacancy != 0.0:
                    result["vacancy"] = vacancy
                if properties_raw:
                    pc = safe_int(properties_raw)
                    if pc != 0:
                        result["properties_count"] = pc
                if tenants_raw:
                    tn = safe_int(tenants_raw)
                    if tn != 0:
                        result["tenants_count"] = tn
                if largest_tenant is not None and largest_tenant != 0.0:
                    result["largest_tenant_pct"] = largest_tenant
                if avg_contract_term:
                    result["avg_contract_term"] = avg_contract_term
                if contract_type:
                    result["contract_type"] = contract_type
                if inadimplencia is not None and inadimplencia != 0.0:
                    result["inadimplencia"] = inadimplencia

                return result
            else:
                cash_available = parse_optional_brazilian_float(get_first_raw(["VALOR EM CAIXA", "CAIXA"]))
                cdi_ipca = get_first_raw(["% CDI/IPCA", "CDI/IPCA", "CDI", "IPCA"]) or find_regex_group(
                    page_text,
                    [
                        r"CDI\s*/\s*IPCA\s*([0-9.,]+%?)",
                        r"IPCA\s*\+\s*([0-9.,]+%?)",
                        r"CDI\s*\+\s*([0-9.,]+%?)"
                    ]
                )
                inadimplencia_raw = get_first_raw(["INADIMPLÊNCIA", "INADIMPLENCIA"]) or find_regex_group(
                    page_text,
                    [r"INADIMPL[ÊE]NCIA\s*([0-9.,]+%?)"]
                )
                inadimplencia = parse_optional_brazilian_float(inadimplencia_raw)
                cri_ratings = get_first_raw(["RATING DOS CRIS", "RATING", "RATING CRI", "RATING CRIS"]) or find_regex_group(
                    page_text,
                    [
                        r"RATING(?:\s+DOS\s+CRIS?)?\s*([A-Z]{1,3}[+\-]?)",
                        r"CRI\s+RATING\s*([A-Z]{1,3}[+\-]?)"
                    ]
                )
                dividend_payout_raw = get_first_raw(["PAYOUT", "DIVIDEND PAYOUT"]) or find_regex_group(
                    page_text,
                    [r"PAYOUT\s*([0-9.,]+%?)"]
                )
                dividend_payout = parse_optional_brazilian_float(dividend_payout_raw)

                if cdi_ipca:
                    result["%_cdi_ipca"] = cdi_ipca
                if inadimplencia is not None and inadimplencia != 0.0:
                    result["inadimplencia"] = inadimplencia
                if cri_ratings:
                    result["cri_ratings"] = cri_ratings
                if cash_available is not None and cash_available != 0.0:
                    result["cash_available"] = cash_available
                if dividend_payout is not None and dividend_payout != 0.0:
                    result["dividend_payout"] = dividend_payout

                return result

    except Exception as e:
        return {"error": f"Internal Scraper Error: {str(e)}"}