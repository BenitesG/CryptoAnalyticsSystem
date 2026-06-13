import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os

# --- API CONSTANTS ---
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
        try:
            status_code, data = fetch_fundamentals("fii", ticker)
            if data:
                return "fii", data, None
        except FundamentalsFetchError:
            pass
            
        try:
            status_code, data = fetch_fundamentals("stock", ticker)
            if data:
                return "stock", data, None
            return None, None, status_code
        except FundamentalsFetchError as exc:
            return None, None, exc.status_code
    else:
        try:
            status_code, data = fetch_fundamentals("stock", ticker)
            if data:
                return "stock", data, None
            return None, None, status_code
        except FundamentalsFetchError as exc:
            return None, None, exc.status_code


def _labelize_key(key: str) -> str:
    label_map = {
        "p_l": "P/L",
        "p_vp": "P/VP",
        "dy": "Dividend Yield",
        "roe": "ROE",
        "debt_ebitda": "Dív. Líquida / Patrimônio",
        "cagr_5y": "CAGR Lucro (5A)",
        "net_margin": "Margem Líquida",
        "market_cap": "Valor de Mercado",
        "ev_ebit": "EV / EBIT",
        "ev_ebitda": "EV / EBITDA",
        "cagr_revenue": "CAGR Receita (5A)",
        "liquidity": "Liquidez Média Diária",
        "net_worth": "Patrimônio Líquido",
        "last_dividend": "Último Rendimento",
        "vacancy": "Vacância Física",
        "properties_count": "Qtd. Imóveis",
        "numero_cotistas": "Número de Cotistas"
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


def _format_large_number(value) -> str:
    """Formats large financial numbers into readable Millions (M) or Billions (B)."""
    if value is None: return "N/A"
    try:
        val = float(value)
        if val >= 1_000_000_000:
            return f"R$ {val / 1_000_000_000:.2f}B"
        if val >= 1_000_000:
            return f"R$ {val / 1_000_000:.2f}M"
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except ValueError:
        return str(value)


def _format_value(value, key: str | None = None) -> str:
    if value is None:
        return ""
    if key in {"market_cap", "net_worth", "liquidity"}:
        return _format_large_number(value)
    if key in {"dy", "roe", "net_margin", "vacancy", "cagr_revenue", "cagr_5y"}:
        if isinstance(value, (int, float)):
            return f"{value:.2f}%"
    if key in {"properties_count", "numero_cotistas"}:
        if isinstance(value, (int, float)):
            return f"{value:,.0f}".replace(",", ".")
    if key == "last_dividend":
        return f"R$ {value:.2f}"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, int):
        return f"{value:,.0f}".replace(",", ".")
    return str(value)


def _render_metric_rows(metrics: list[tuple[str, str]]):
    if not metrics:
        return
    cols = st.columns(len(metrics))
    for idx, (label, value) in enumerate(metrics):
        with cols[idx]:
            st.metric(label, value)

def render_fundamentals_ui(asset_type: str, data: dict):
    """Renders fundamentals grid - only shows non-empty/non-zero fields."""
    st.markdown("##### 🏢 Indicadores Fundamentalistas")
    
    if asset_type == "stock":
        sector = data.get('sector')
        if sector:
            st.caption(f"**Setor:** {sector}")
        
        # Section 1: Valuation Metrics
        val_metrics = []
        for k in ["p_l", "p_vp", "ev_ebit", "ev_ebitda", "market_cap"]:
            if val := data.get(k):
                val_metrics.append((_labelize_key(k), _format_value(val, k)))
        
        if val_metrics:
            st.markdown("<p style='font-size:13px; color:#808495; margin-bottom:2px;'>VALUATION</p>", unsafe_allow_html=True)
            _render_metric_rows(val_metrics)
            st.divider()

        # Section 2: Profitability & Margins
        prof_metrics = []
        for k in ["dy", "roe", "net_margin"]:
            if val := data.get(k):
                prof_metrics.append((_labelize_key(k), _format_value(val, k)))
        
        if prof_metrics:
            st.markdown("<p style='font-size:13px; color:#808495; margin-bottom:2px;'>RENTABILIDADE E MARGENS</p>", unsafe_allow_html=True)
            _render_metric_rows(prof_metrics)
            st.divider()

        # Section 3: Debt & Growth
        debt_metrics = []
        for k in ["debt_ebitda", "cagr_revenue"]:
            if val := data.get(k):
                debt_metrics.append((_labelize_key(k), _format_value(val, k)))
        
        if debt_metrics:
            st.markdown("<p style='font-size:13px; color:#808495; margin-bottom:2px;'>ENDIVIDAMENTO E CRESCIMENTO</p>", unsafe_allow_html=True)
            _render_metric_rows(debt_metrics)
        
    elif asset_type == "fii":
        fii_type_raw = data.get('tipo_fii', 'N/A').lower()
        fii_type_pt = "Tijolo" if "tijolo" in fii_type_raw else "Papel" if "papel" in fii_type_raw else "FOF (Fundo de Fundos)" if "fof" in fii_type_raw else "Híbrido"
        
        segment = data.get('segment', '')
        caption_text = f"**Tipo:** {fii_type_pt}"
        if segment:
            caption_text = f"**Segmento:** {segment} | " + caption_text
        st.caption(caption_text)
        
        # Row 1: Price and Dividends
        row1 = []
        for k in ["p_vp", "dy", "last_dividend"]:
            if val := data.get(k):
                row1.append((_labelize_key(k), _format_value(val, k)))
        if row1:
            _render_metric_rows(row1)
            st.divider()
        
        # Row 2: Liquidity and Size
        row2 = []
        for k in ["liquidity", "net_worth", "numero_cotistas"]:
            if val := data.get(k):
                row2.append((_labelize_key(k), _format_value(val, k)))
        if row2:
            st.markdown("<p style='font-size:13px; color:#808495; margin-bottom:2px;'>LIQUIDEZ E TAMANHO</p>", unsafe_allow_html=True)
            _render_metric_rows(row2)

        # Row 3: Physical Properties (Brick FIIs only)
        if "tijolo" in fii_type_raw:
            st.divider()
            row3 = []
            for k in ["vacancy", "properties_count"]:
                if val := data.get(k):
                    row3.append((_labelize_key(k), _format_value(val, k)))
            if row3:
                st.markdown("<p style='font-size:13px; color:#808495; margin-bottom:2px;'>PORTFÓLIO FÍSICO</p>", unsafe_allow_html=True)
                _render_metric_rows(row3)

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
                                
                                # Render C# Database Cache Timestamp
                                last_updated = fund_data.get("last_updated_at")
                                if last_updated:
                                    try:
                                        dt = pd.to_datetime(last_updated)
                                        formatted_date = dt.strftime("%d/%m/%Y at %H:%M:%S")
                                        st.caption(f"🕒 Database Cache Updated: {formatted_date} (UTC)")
                                    except Exception:
                                        pass
                                        
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