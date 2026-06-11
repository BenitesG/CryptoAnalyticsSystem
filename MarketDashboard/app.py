import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os

# --- API CONSTANTS ---
# Inside Docker it will use the environment variable. Locally, we keep the default.
API_URL = os.getenv("API_URL", "http://localhost:5091")

# --- Fundamentals Functions ---
class FundamentalsFetchError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code

@st.cache_data(ttl=300)
def _fetch_fundamentals_cached(asset_type: str, ticker: str):
    response = requests.get(f"{API_URL}/fundamentals/{asset_type}/{ticker}", timeout=15)
    response.raise_for_status()
    return response.json()

def fetch_fundamentals(asset_type: str, ticker: str):
    """Fetch fundamentals from the C# API proxy endpoint."""
    try:
        data = _fetch_fundamentals_cached(asset_type, ticker)
        return 200, data
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response else None
        if status_code == 404:
            return status_code, None
        raise FundamentalsFetchError(
            "⚠️ Fundamentals service is currently unavailable.",
            status_code=status_code
        ) from exc
    except requests.RequestException as exc:
        raise FundamentalsFetchError(
            "⚠️ Error connecting to the fundamentals service. Please try again later.",
        ) from exc

def fetch_fundamentals_with_fallback(ticker: str):
    """Heuristic: Try FII if it ends with 11, otherwise stock. Fall back on any error."""
    
    if ticker.endswith("11"):
        # 1. Try FII first (MXRF11, HGLG11, etc)
        try:
            status_code, data = fetch_fundamentals("fii", ticker)
            if data:
                return "fii", data, None
        except FundamentalsFetchError:
            pass # Ignore and fallback to stock if FII fetch fails (either 404 or connection error)
            
        # 2. Fallback to Stock (TAEE11, SANB11, etc)
        try:
            status_code, data = fetch_fundamentals("stock", ticker)
            if data:
                return "stock", data, None
            return None, None, status_code
        except FundamentalsFetchError as exc:
            return None, None, exc.status_code
            
    else:
        # If it does not end with 11, it is a stock
        try:
            status_code, data = fetch_fundamentals("stock", ticker)
            if data:
                return "stock", data, None
            return None, None, status_code
        except FundamentalsFetchError as exc:
            return None, None, exc.status_code


def _labelize_key(key: str) -> str:
    label_map = {
        "p_l": "P/E Ratio",
        "p_vp": "P/B Ratio",
        "dy": "Dividend Yield",
        "roe": "ROE",
        "debt_ebitda": "Net Debt/EBITDA",
        "cagr_5y": "5Y Profit CAGR",
        "net_margin": "Net Margin",
        "last_updated_at": "Last Updated",
        "liquidez_media_diaria": "Avg Daily Liquidity",
        "valor_patrimonial_cota": "Book Value per Share",
        "patrimonio_liquido": "Net Worth",
        "numero_cotistas": "Shareholders",
        "ultimo_rendimento": "Last Yield",
        "data_pagamento": "Payment Date",
        "vacancy": "Vacancy",
        "properties_count": "Properties Count",
        "tenants_count": "Tenants Count",
        "tenant_count": "Tenants Count",
        "largest_tenant_pct": "Largest Tenant (%)",
        "avg_contract_term": "Avg Contract Term",
        "contract_type": "Contract Type",
        "inadimplencia": "Default Rate",
        "%_cdi_ipca": "CDI/IPCA Indexer",
        "cri_ratings": "CRI Rating",
        "cash_available": "Available Cash",
        "tipo_fii": "REIT Type",
        "segment": "Segment",
        "sector": "Sector",
        "localizacao": "Location",
        "qualidade_imoveis": "Properties Quality",
        "qualidade_cris": "CRIs Quality",
    }
    return label_map.get(key, key.replace("_", " ").title())


def _is_meaningful(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in {"", "-", "--", "N/A"}
    if isinstance(value, (int, float)):
        return value != 0
    return True


def _format_value(value, key: str | None = None) -> str:
    if value is None:
        return ""
    if key in {"dy", "roe", "net_margin", "vacancy", "largest_tenant_pct", "inadimplencia", "dividend_payout", "cagr_5y"}:
        if isinstance(value, (int, float)):
            return f"{value:.2f}%"
    if key in {"properties_count", "tenant_count", "tenants_count"}:
        if isinstance(value, (int, float)):
            return f"{value:.0f}"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _render_metric_rows(metrics: list[tuple[str, str]]):
    if not metrics:
        return
    cols = st.columns(min(3, len(metrics)))
    for idx, (label, value) in enumerate(metrics):
        with cols[idx % len(cols)]:
            st.metric(label, value)

def render_fundamentals_ui(asset_type: str, data: dict):
    """Renders fundamentals grid - only shows non-empty/non-zero fields."""
    st.markdown("##### 🏢 Fundamentals")
    
    if asset_type == "stock":
        sector = data.get('sector')
        if sector:
            st.caption(f"**Sector:** {sector}")
        
        metrics: list[tuple[str, str]] = []
        p_l = data.get("p_l")
        if p_l is not None and p_l != 0:
            metrics.append(("P/E Ratio", _format_value(p_l, "p_l")))
        p_vp = data.get("p_vp")
        if p_vp is not None and p_vp != 0:
            metrics.append(("P/B Ratio", _format_value(p_vp, "p_vp")))
        dy = data.get('dy')
        if dy is not None and dy > 0:
            metrics.append(("Dividend Yield", _format_value(dy, "dy")))
        roe = data.get("roe")
        if roe is not None and roe != 0:
            metrics.append(("ROE", _format_value(roe, "roe")))
        debt_ebitda = data.get("debt_ebitda")
        if debt_ebitda is not None and debt_ebitda != 0:
            metrics.append(("Net Debt/EBITDA", _format_value(debt_ebitda, "debt_ebitda")))
        cagr = data.get('cagr_5y')
        if cagr is not None and cagr != 0:
            metrics.append(("5Y Profit CAGR", _format_value(cagr, "cagr_5y")))
        net_margin = data.get("net_margin")
        if net_margin is not None and net_margin != 0:
            metrics.append(("Net Margin", _format_value(net_margin, "net_margin")))
        
        _render_metric_rows(metrics)

        displayed_keys = {"sector", "p_l", "p_vp", "dy", "roe", "debt_ebitda", "cagr_5y", "net_margin"}
        stock_priority = [
            "liquidez_media_diaria", "valor_patrimonial_cota", "patrimonio_liquido",
            "numero_cotistas", "ultimo_rendimento", "data_pagamento"
        ]
        extras = [
            (k, v)
            for k in stock_priority
            if k in data and _is_meaningful(data.get(k))
            for v in [data.get(k)]
        ] + [
            (k, v)
            for k, v in data.items()
            if k not in displayed_keys and k != "ticker" and k not in stock_priority and _is_meaningful(v)
        ]
        if extras:
            st.divider()
            _render_metric_rows([(_labelize_key(key), _format_value(value, key)) for key, value in extras])
        
    elif asset_type == "fii":
        fii_type_raw = data.get('tipo_fii', 'N/A').lower()
        fii_type_pt = "Brick" if "tijolo" in fii_type_raw else "Paper" if "papel" in fii_type_raw else "FOF" if "fof" in fii_type_raw else "Hybrid"
        
        segment = data.get('segment', '')
        caption_text = f"**Type:** {fii_type_pt}"
        if segment:
            caption_text = f"**Segment:** {segment} | " + caption_text
        st.caption(caption_text)
        
        # Common FII Metrics
        common_metrics: list[tuple[str, str]] = []
        pvp = data.get("p_vp")
        if pvp is not None and pvp != 0:
            common_metrics.append(("P/B Ratio", _format_value(pvp, "p_vp")))
        dy = data.get('dy')
        if dy is not None and dy > 0:
            common_metrics.append(("Dividend Yield", _format_value(dy, "dy")))
        payout = data.get("dividend_payout")
        if payout is not None and payout > 0:
            common_metrics.append(("Dividend Payout", _format_value(payout, "dividend_payout")))

        _render_metric_rows(common_metrics)
        
        # Specific Brick FII Metrics
        if "tijolo" in fii_type_raw:
            st.divider()
            brick_metrics: list[tuple[str, str]] = []
            vacancy = data.get('vacancy')
            if vacancy is not None and vacancy > 0:
                brick_metrics.append(("Vacancy", _format_value(vacancy, "vacancy")))
            properties_count = data.get("properties_count")
            if properties_count is not None and properties_count > 0:
                brick_metrics.append(("Properties Count", _format_value(properties_count, "properties_count")))
            tenant_count = data.get("tenant_count")
            if tenant_count is not None and tenant_count > 0:
                brick_metrics.append(("Tenants Count", _format_value(tenant_count, "tenant_count")))
            largest = data.get('largest_tenant_pct')
            if largest is not None and largest > 0:
                brick_metrics.append(("Largest Tenant Concentration", _format_value(largest, "largest_tenant_pct")))
            term = data.get("avg_contract_term")
            if term:
                brick_metrics.append(("Contract Term", _format_value(term, "avg_contract_term")))
            contract_type = data.get("contract_type")
            if contract_type:
                brick_metrics.append(("Contract Type", _format_value(contract_type, "contract_type")))
            
            _render_metric_rows(brick_metrics)

            brick_metrics2: list[tuple[str, str]] = []
            localizacao = data.get("localizacao")
            if localizacao:
                brick_metrics2.append(("Location", localizacao))
            qualidade_imoveis = data.get("qualidade_imoveis")
            if qualidade_imoveis:
                brick_metrics2.append(("Properties Quality", qualidade_imoveis))
            
            if brick_metrics2:
                st.divider()
                _render_metric_rows(brick_metrics2)
            
        # Specific Paper FII Metrics
        elif "papel" in fii_type_raw:
            st.divider()
            paper_metrics: list[tuple[str, str]] = []
            cdi = data.get("%_cdi_ipca")
            if cdi:
                paper_metrics.append(("Indexer", _format_value(cdi, "%_cdi_ipca")))
            inad = data.get('inadimplencia')
            if inad is not None and inad > 0:
                paper_metrics.append(("Default Rate", _format_value(inad, "inadimplencia")))
            qualidade_cris = data.get("qualidade_cris")
            if qualidade_cris:
                paper_metrics.append(("CRIs Quality", qualidade_cris))
            cri_ratings = data.get("cri_ratings")
            if cri_ratings and not qualidade_cris:
                paper_metrics.append(("CRIs Quality", cri_ratings))
            cash_available = data.get("cash_available")
            if cash_available is not None and cash_available > 0:
                paper_metrics.append(("Available Cash", _format_value(cash_available, "cash_available")))
            
            _render_metric_rows(paper_metrics)

        displayed_keys = {
            "tipo_fii", "segment", "p_vp", "dy", "vacancy", "largest_tenant_pct", "avg_contract_term",
            "localizacao", "qualidade_imoveis", "%_cdi_ipca", "inadimplencia", "qualidade_cris", "cri_ratings",
            "dividend_payout", "properties_count"
        }
        fii_priority = [
            "numero_cotistas", "tenant_count", "tenants_count", "contract_type", "cash_available"
        ]
        extras = [
            (k, v)
            for k in fii_priority
            if k in data and _is_meaningful(data.get(k)) and k not in displayed_keys
            for v in [data.get(k)]
        ] + [
            (k, v)
            for k, v in data.items()
            if k not in displayed_keys and k != "ticker" and k not in fii_priority and _is_meaningful(v)
        ]
        if extras:
            st.divider()
            _render_metric_rows([(_labelize_key(key), _format_value(value, key)) for key, value in extras])

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Market Analytics", layout="wide")
st.title("📊 Market Analytics Dashboard")
st.markdown("Welcome to the Market Analytics Dashboard! Analyze and compare price trends of Cryptocurrencies and Stocks listed on B3.")

st.info("""
**Disclaimer:** The 'Action Signal' provided by this dashboard is based on a simple mathematical algorithm (Moving Averages and Volatility) for educational purposes only. 
**It does not constitute financial advice.** Always do your own research before investing.
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Configurations")
    market_type = st.radio("Select a Market:", ["Cryptocurrency", "Stocks/REITs (B3)"])
    st.markdown("*(To compare assets, separate them by commas. Ex: petr4, vale3)*")
    
    placeholder = "ex: bitcoin, ethereum" if market_type == "Cryptocurrency" else "ex: petr4, mxrf11"
    assets_input = st.text_input("Enter Tickers or Asset Names", placeholder=placeholder).lower()
    
    btn_search = st.button("🔍 Analyze Market")

# --- MAIN CONTENT ---
if btn_search:
    raw_list = [x.strip() for x in assets_input.split(",") if x.strip()]
    asset_list = list(dict.fromkeys(raw_list)) 
    
    if not asset_list: 
        st.error("⚠️ Please enter at least one asset name!")
        st.stop() 
        
    with st.spinner(f"Analyzing {len(asset_list)} asset(s)..."):
        currency_symbol = "$" if market_type == "Cryptocurrency" else "R$ "
        asset_type_url = "crypto" if market_type == "Cryptocurrency" else "stock"
        df_master = pd.DataFrame()
        st.subheader("📝 Analysis Summary")

        for asset in asset_list:
            url_api_csharp = f"{API_URL}/price/{asset_type_url}/{asset}/history" 
            
            try:
                response = requests.get(url_api_csharp)
                
                if response.status_code == 200:
                    complete_data = response.json()
                    analysis = complete_data["last_7_days"]
                    historical_prices = analysis.get("prices", [])
                    
                    current_price = historical_prices[-1] if historical_prices else analysis.get('average', 0.0)
                    fmt = "{:,.6f}" if analysis.get('average', 0) < 1 else "{:,.2f}"
                    
                    with st.expander(f"🟢 {asset.upper()} | Current Price: {currency_symbol}{fmt.format(current_price)}", expanded=True):
                        
                        if historical_prices:
                            col1, col2, col3, col4, col5 = st.columns(5)
                            col1.metric("Average Price", f"{currency_symbol}{fmt.format(analysis['average'])}")
                            col2.metric("7-Day High", f"{currency_symbol}{fmt.format(analysis['max'])}")
                            
                            col3.metric("Trend", analysis['trend'], f"{analysis['percentage_change']}%")
                            col4.metric("Volatility (Risk)", fmt.format(analysis['volatility']))
                            
                            signal = str(analysis.get("action_signal", "HOLD")).upper()
                            color_hex = "#00FFAA" if signal in ["BUY", "STRONG BUY"] else "#FF4B4B" if signal == "SELL" else "#808495"
                            col5.markdown(f"<div><p style='font-size: 14px; margin-bottom: 0px; color: #FAFAFA;'>Action Signal</p><h2 style='color: {color_hex}; margin-top: 0px; padding: 0px;'>{signal}</h2></div>", unsafe_allow_html=True)
                        else:
                            st.info("⚠️ Historical chart data is unavailable today. Displaying Fundamentals and Current Price only.")

                        if market_type == "Stocks/REITs (B3)":
                            st.divider()
                            a_type, fund_data, fund_status = fetch_fundamentals_with_fallback(asset)
                            if fund_data and a_type:
                                render_fundamentals_ui(a_type, fund_data)
                            elif fund_status == 404:
                                st.warning("⚠️ Fundamental data not found for this asset.")
                            else:
                                st.error("⚠️ Fundamentals service is currently unavailable. Please try again later.")

                    if historical_prices:
                        df_temp = pd.DataFrame({
                            "Timeline (Data Points)": range(len(historical_prices)),
                            "Price": historical_prices,
                            "Asset": asset.upper()
                        })
                        df_master = pd.concat([df_master, df_temp], ignore_index=True)
                        
                else:
                    st.error(f"❌ '{asset.upper()}' not found in the {market_type} database.")
                    
            except Exception as e:
                st.error(f"⚠️ Connection error for {asset.upper()}. Please check if the C# API is running! Details: {e}")

        # --- Comparative Price Curve ---
        if not df_master.empty:
            st.markdown("---") 
            st.subheader("📈 Comparative Price Curve")
            
            fig = px.line(df_master, x="Timeline (Data Points)", y="Price", color="Asset")
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

            csv_file = df_master.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Consolidated Report (CSV)",
                data=csv_file,
                file_name="consolidated_market_report.csv",
                mime="text/csv",
            )