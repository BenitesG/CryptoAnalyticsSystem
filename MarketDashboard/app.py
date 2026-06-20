import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os

# --- INITIALIZE SESSION STATE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None

# --- API CONSTANTS ---
API_URL = os.getenv("API_URL", "http://localhost:5091")

# --- HIDE STREAMLIT INSTRUCTIONS & FIX EDGE DOUBLE EYE BUG ---
st.markdown(
    """
    <style>
    /* Hide Streamlit input instructions */
    div[data-testid="InputInstructions"] {
        display: none !important;
    }
    /* Hide Microsoft Edge native password reveal and clear buttons */
    input[type="password"]::-ms-reveal,
    input[type="password"]::-ms-clear {
        display: none !important;
        width: 0 !important;
        height: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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

# --- USER PORTFOLIO & AUTHENTICATION FUNCTIONS ---

def register_user(username: str, password: str) -> tuple[int, dict | None]:
    """Calls C# API to register a new user securely."""
    try:
        payload = {"username": username, "password": password}
        response = requests.post(f"{API_URL}/users/register", json=payload, timeout=10)
        if response.status_code == 201:
            return response.status_code, response.json()
        return response.status_code, response.json()
    except Exception as e:
        return 500, {"message": f"Connection error: {e}"}


def login_user(username: str, password: str) -> tuple[int, dict | None]:
    """Calls C# API to verify credentials and retrieve User ID."""
    try:
        payload = {"username": username, "password": password}
        response = requests.post(f"{API_URL}/users/login", json=payload, timeout=10)
        if response.status_code == 200:
            return response.status_code, response.json()
        return response.status_code, None
    except Exception as e:
        return 500, None


def add_asset_to_portfolio(user_id: str, ticker: str, quantity: float, avg_price: float) -> bool:
    """Calls C# API to add/update an asset in the user's database portfolio."""
    try:
        payload = {
            "userId": user_id,
            "ticker": ticker.upper().strip(),
            "quantity": quantity,
            "averagePrice": avg_price
        }
        response = requests.post(f"{API_URL}/portfolios/add", json=payload, timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def fetch_user_portfolio(user_id: str) -> list:
    """Retrieves the consolidated portfolio for a specific user from C# API."""
    try:
        response = requests.get(f"{API_URL}/portfolios/{user_id}", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []

# Helper to fetch current price from C# Gateway
def get_live_price(ticker: str) -> float:
    try:
        asset_type = "crypto" if ticker.lower() in ["bitcoin", "ethereum", "dogecoin"] else "stock"
        response = requests.get(f"{API_URL}/price/{asset_type}/{ticker}", timeout=5)
        if response.status_code == 200:
            return float(response.json().get("price", 0.0))
    except Exception:
        pass
    return 0.0

def _labelize_key(key: str) -> str:
    label_map = {
        "p_l": "P/E Ratio",
        "p_vp": "P/B Ratio",
        "dy": "Dividend Yield",
        "roe": "ROE",
        "debt_ebitda": "Dívida Líquida/EBITDA",
        "cagr_5y": "CAGR Lucro 5 Anos",
        "net_margin": "Margem Líquida",
        "liquidez_media_diaria": "Liquidez Média Diária",
        "valor_patrimonial_cota": "Valor Patrimonial Cota",
        "patrimonio_liquido": "Patrimônio Líquido",
        "numero_cotistas": "Número de Cotistas",
        "ultimo_rendimento": "Último Rendimento",
        "data_pagamento": "Data Pagamento",
        "vacancy": "Vacância",
        "properties_count": "Qtd. Imóveis",
        "tenants_count": "Qtd. Inquilinos",
        "tenant_count": "Qtd. Inquilinos",
        "largest_tenant_pct": "Maior Inquilino (%)",
        "avg_contract_term": "Prazo Médio Contratos",
        "contract_type": "Tipo Contrato",
        "inadimplencia": "Inadimplência",
        "%_cdi_ipca": "Indexador CDI/IPCA",
        "cri_ratings": "Rating CRI",
        "cash_available": "Caixa Disponível",
        "tipo_fii": "Tipo FII",
        "segment": "Segmento",
        "sector": "Setor",
        "localizacao": "Location",
        "qualidade_imoveis": "Qualidade Imóveis",
        "qualidade_cris": "Qualidade CRIs",
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
                paper_metrics.append(("Quality CRIs", qualidade_cris))
            cri_ratings = data.get("cri_ratings")
            if cri_ratings and not qualidade_cris:
                paper_metrics.append(("Quality CRIs", cri_ratings))
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

# --- SIDEBAR (AUTHENTICATION & CONFIGURATIONS) ---
menu_selection = "🔍 Market Analysis"  # Default view for non-logged in users

with st.sidebar:
    st.header("👤 Account")
    
    # 1. USER IS NOT LOGGED IN: Show Login / Register Forms
    if not st.session_state.logged_in:
        auth_mode = st.radio("Choose Action:", ["Login", "Register"])
        username_input = st.text_input("Username").strip()
        password_input = st.text_input("Password", type="password")
        
        if auth_mode == "Login":
            if st.button("🔓 Sign In"):
                if not username_input or not password_input:
                    st.error("⚠️ Username and password cannot be empty!")
                else:
                    status, user_data = login_user(username_input, password_input)
                    if status == 200 and user_data:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user_data["id"]
                        st.session_state.username = user_data["username"]
                        st.success(f"Welcome back, {user_data['username']}!")
                        st.rerun() # Refreshes the page to load the portfolio
                    else:
                        st.error("❌ Invalid username or password.")
        else:
            if st.button("📝 Register"):
                if not username_input or not password_input:
                    st.error("⚠️ Username and password cannot be empty!")
                else:
                    status, response = register_user(username_input, password_input)
                    if status == 201:
                        st.success("🎉 Account created! Please select 'Login' to sign in.")
                    elif status == 409:
                        st.error("⚠️ Username is already taken.")
                    else:
                        st.error("❌ Failed to create account.")
                        
    # 2. USER IS LOGGED IN: Show Welcome, Navigation Menu, and dynamic forms!
    else:
        # Pylance Fix: Safe string conversions
        raw_username = st.session_state.username if st.session_state.username else "user"
        st.markdown(f"Welcome, **{raw_username.upper()}**!")
        
        # NAVIGATION MENU (This manages the view in the main page)
        menu_selection = st.radio("Navigation:", ["💼 My Wallet", "🔍 Market Search"])
        
        # Only show the purchase form if the active view is "My Wallet"
        if menu_selection == "💼 My Wallet":
            st.markdown("---")
            st.subheader("📥 Add to Portfolio")
            with st.form("add_asset_form", clear_on_submit=True):
                ticker_buy = st.text_input("Ticker (ex: hglg11, bitcoin)").upper().strip()
                qty_buy = st.number_input("Quantity", min_value=0.01, step=1.0)
                price_buy = st.number_input("Average Price Paid", min_value=0.01, step=0.1)
                
                submit_buy = st.form_submit_button("🛒 Save Purchase")
                if submit_buy:
                    if not ticker_buy:
                        st.error("Please enter a Ticker!")
                    else:
                        user_id_str = str(st.session_state.user_id) if st.session_state.user_id else ""
                        success = add_asset_to_portfolio(
                            user_id_str, 
                            ticker_buy, 
                            qty_buy, 
                            price_buy
                        )
                        if success:
                            st.success(f"Saved {qty_buy} shares of {ticker_buy}!")
                            st.rerun() # Refresh to update portfolio tables/charts
                        else:
                            st.error("Failed to save transaction.")

        if st.button("🔒 Sign Out"):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.rerun()

    # 3. STANDARD MARKET SEARCH (Only visible if searching or NOT logged in)
    if not st.session_state.logged_in or menu_selection == "🔍 Market Search":
        st.markdown("---")
        st.header("⚙️ Market Search")
        market_type = st.radio("Select a Market:", ["Cryptocurrency", "Stocks/REITs (B3)"])
        st.markdown("*(To compare assets, separate them by commas. Ex: petr4, vale3)*")
        
        placeholder = "ex: bitcoin, ethereum" if market_type == "Cryptocurrency" else "ex: petr4, mxrf11"
        assets_input = st.text_input("Enter Tickers or Asset Names", placeholder=placeholder).lower()
        
        btn_search = st.button("🔍 Analyze Market")
    else:
        btn_search = False  # Avoid conflicts when in Wallet tab

# --- MAIN CONTENT ---

# A. USER WALLET TAB (Only rendered if logged in AND selected in navigation)
if st.session_state.logged_in and menu_selection == "💼 My Wallet":
    user_id_str = str(st.session_state.user_id) if st.session_state.user_id else ""
    portfolio = fetch_user_portfolio(user_id_str)
    
    st.subheader("💼 My Portfolio Dashboard")
    
    if not portfolio:
        st.info("Your portfolio is empty. Add your first assets using the sidebar form! 🛒")
    else:
        with st.spinner("Fetching live market prices for your portfolio..."):
            total_invested = 0.0
            total_current_value = 0.0
            stocks_fii_rows = []
            crypto_rows = []
            
            for asset in portfolio:
                ticker = asset["ticker"].upper()
                qty = float(asset["quantity"])
                avg_price = float(asset["averagePrice"])
                
                # Dynamic Currency assignment based on Asset category
                is_crypto = ticker.lower() in ["bitcoin", "ethereum", "dogecoin"]
                currency_symbol = "$" if is_crypto else "R$ "
                
                # Fetch live price from the C# Gateway
                live_price = get_live_price(ticker)
                
                cost_basis = qty * avg_price
                current_value = qty * live_price if live_price > 0 else cost_basis
                
                p_l_abs = current_value - cost_basis
                p_l_pct = ((live_price - avg_price) / avg_price) * 100.0 if avg_price > 0 and live_price > 0 else 0.0
                
                total_invested += cost_basis
                total_current_value += current_value
                
                row = {
                    "Ticker": ticker,
                    "Qty": qty,
                    "Avg Price Paid": f"{currency_symbol}{avg_price:.2f}",
                    "Live Price": f"{currency_symbol}{live_price:.2f}" if live_price > 0 else "N/A",
                    "Total Cost": f"{currency_symbol}{cost_basis:.2f}",
                    "Current Value": f"{currency_symbol}{current_value:.2f}",
                    "P&L (%)": f"{p_l_pct:+.2f}%" if live_price > 0 else "0.00%",
                    "P&L (Abs)": f"{currency_symbol}{p_l_abs:+.2f}" if live_price > 0 else f"{currency_symbol}0.00",
                    "raw_current_value": current_value # Helper for the Plotly Pie Chart
                }
                
                if is_crypto:
                    crypto_rows.append(row)
                else:
                    stocks_fii_rows.append(row)
            
            # Combine raw dataframes for the consolidated Pie Chart
            all_rows = stocks_fii_rows + crypto_rows
            df_all = pd.DataFrame(all_rows)
            
            # --- CONSOLIDATED PORTFOLIO METRICS ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Cost Basis", f"R$ {total_invested:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            col2.metric("Current Equity Value", f"R$ {total_current_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            total_p_l_abs = total_current_value - total_invested
            total_p_l_pct = (total_p_l_abs / total_invested) * 100.0 if total_invested > 0 else 0.0
            
            # Render colored metric card for total P&L
            p_l_color = "#00FFAA" if total_p_l_abs >= 0 else "#FF4B4B"
            col3.markdown(
                f"""
                <div>
                    <p style='font-size: 14px; margin-bottom: 0px; color: #FAFAFA;'>Total Profit / Loss</p>
                    <h2 style='color: {p_l_color}; margin-top: 0px; padding: 0px;'>
                        R$ {total_p_l_abs:+.2f} ({total_p_l_pct:+.2f}%)
                    </h2>
                </div>
                """, 
                unsafe_allow_html=True
            )
            
            st.divider()
            
            # Render Tables on left, Pie Chart on right
            grid_col1, grid_col2 = st.columns([3, 2])
            
            with grid_col1:
                display_cols = ["Ticker", "Qty", "Avg Price Paid", "Live Price", "Total Cost", "Current Value", "P&L (%)", "P&L (Abs)"]
                
                if stocks_fii_rows:
                    st.markdown("##### 📈 Stocks & REITs Breakdown")
                    df_stocks = pd.DataFrame(stocks_fii_rows)
                    st.dataframe(df_stocks[display_cols], use_container_width=True, hide_index=True)
                    
                if crypto_rows:
                    if stocks_fii_rows: st.markdown(" ") # Spacer
                    st.markdown("##### 🪙 Cryptocurrency Breakdown")
                    df_cryptos = pd.DataFrame(crypto_rows)
                    st.dataframe(df_cryptos[display_cols], use_container_width=True, hide_index=True)
                    
            with grid_col2:
                st.markdown("##### 🍕 Asset Allocation (Current Value)")
                fig = px.pie(
                    df_all, 
                    values="raw_current_value", 
                    names="Ticker",
                    hole=0.4
                )
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", 
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=True,
                    margin=dict(t=0, b=0, l=0, r=0)
                )
                st.plotly_chart(fig, use_container_width=True)

# B. SEARCH MARKET LOGIC (Runs for everyone inside the Search Tab or if Guest)
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
                        # 1. Prices (C# API)
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

                        # 2. Fundamentals (C# Proxy -> Python API)
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
            
# Show helpful instructions if logged in but not searching and on the Search Tab
elif st.session_state.logged_in and menu_selection == "🔍 Market Search" and not btn_search:
    st.info("👈 Use the 'Market Search' section in the sidebar to search and analyze B3/Crypto assets!")