import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- CONSTANTES DE API ---
# Porta do C# (Preço e Histórico)
API_CSHARP_URL = "http://localhost:5091"
# TODO: Mudar para porta do C# quando o Proxy de fundamentos estiver pronto.
# Temporariamente apontando para o FastAPI.
API_BRAIN_URL = "http://localhost:8000" 

# --- FUNÇÕES DE FUNDAMENTOS ---
class FundamentalsFetchError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code

@st.cache_data(ttl=300) # Cache de 5 min para evitar bater no scraper atoa
def _fetch_fundamentals_cached(asset_type: str, ticker: str):
    response = requests.get(f"{API_BRAIN_URL}/fundamentals/{asset_type}/{ticker}", timeout=15)
    response.raise_for_status()
    return response.json()

def fetch_fundamentals(asset_type: str, ticker: str):
    """Busca fundamentos no MarketBrain (FastAPI)."""
    try:
        data = _fetch_fundamentals_cached(asset_type, ticker)
        return 200, data
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response else None
        if status_code == 404:
            return status_code, None
        raise FundamentalsFetchError(
            "⚠️ Serviço de fundamentos indisponível no momento.",
            status_code=status_code
        ) from exc
    except requests.RequestException as exc:
        raise FundamentalsFetchError(
            "⚠️ Erro de conexão com o serviço de fundamentos.",
        ) from exc

def fetch_fundamentals_with_fallback(ticker: str):
    """Heurística: Tenta FII se terminar em 11, senão Ação. Faz fallback se der 404."""
    try:
        if ticker.endswith("11"):
            status_code, data = fetch_fundamentals("fii", ticker)
            if data:
                return "fii", data, None
            if status_code == 404:
                # Fallback para Ação (Units como TAEE11, SANB11)
                fallback_status, data = fetch_fundamentals("stock", ticker)
                if data:
                    return "stock", data, None
                return None, None, fallback_status
            return None, None, status_code
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
        "dy": "DY",
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
        "localizacao": "Localização",
        "qualidade_imoveis": "Qualidade Imóveis",
        "qualidade_cris": "Qualidade CRIs",
    }
    return label_map.get(key, key.replace("_", " ").title())


def _format_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)

def render_fundamentals_ui(asset_type: str, data: dict):
    """Renders fundamentals grid - only shows non-empty/non-zero fields."""
    st.markdown("##### 🏢 Indicadores Fundamentalista")
    
    if asset_type == "stock":
        sector = data.get('sector')
        if sector:
            st.caption(f"**Setor:** {sector}")
        
        metrics = []
        p_l = data.get("p_l")
        if p_l is not None and p_l != 0:
            metrics.append(("P/L", p_l))
        p_vp = data.get("p_vp")
        if p_vp is not None and p_vp != 0:
            metrics.append(("P/VP", p_vp))
        dy = data.get('dy')
        if dy is not None and dy > 0:
            metrics.append(("DY", f"{dy:.2f}%"))
        roe = data.get("roe")
        if roe is not None and roe != 0:
            metrics.append(("ROE", f"{roe:.2f}%"))
        debt_ebitda = data.get("debt_ebitda")
        if debt_ebitda is not None and debt_ebitda != 0:
            metrics.append(("Dív. Líquida/EBITDA", debt_ebitda))
        cagr = data.get('cagr_5y')
        if cagr is not None and cagr != 0:
            metrics.append(("CAGR Lucros (5A)", f"{cagr:.2f}%"))
        
        if metrics:
            cols = st.columns(min(3, len(metrics)))
            for idx, (label, value) in enumerate(metrics):
                with cols[idx % len(cols)]:
                    st.metric(label, value)

        displayed_keys = {
            "sector", "p_l", "p_vp", "dy", "roe", "debt_ebitda", "cagr_5y"
        }
        extras = [(k, v) for k, v in data.items() if k not in displayed_keys and k != "ticker" and v is not None]
        if extras:
            st.divider()
            cols = st.columns(min(3, len(extras)))
            for idx, (key, value) in enumerate(extras):
                with cols[idx % len(cols)]:
                    st.metric(_labelize_key(key), _format_value(value))
        
    elif asset_type == "fii":
        fii_type_raw = data.get('tipo_fii', 'N/A').lower()
        fii_type_pt = "Tijolo" if "tijolo" in fii_type_raw else "Papel" if "papel" in fii_type_raw else "Híbrido"
        
        segment = data.get('segment', '')
        caption_text = f"**Tipo:** {fii_type_pt}"
        if segment:
            caption_text = f"**Segmento:** {segment} | " + caption_text
        st.caption(caption_text)
        
        # Common FII Metrics
        common_metrics = []
        pvp = data.get("p_vp")
        if pvp is not None and pvp != 0:
            common_metrics.append(("P/VP", pvp))
        if "papel" in fii_type_raw:
            dy = data.get('dy')
            if dy is not None and dy > 0:
                common_metrics.append(("DY", f"{dy:.2f}%"))
        
        if common_metrics:
            cols = st.columns(min(3, len(common_metrics)))
            for idx, (label, value) in enumerate(common_metrics):
                with cols[idx % len(cols)]:
                    st.metric(label, value)
        
        # Specific Brick FII Metrics
        if "tijolo" in fii_type_raw:
            st.divider()
            brick_metrics = []
            vacancy = data.get('vacancy')
            if vacancy is not None and vacancy > 0:
                brick_metrics.append(("Vacância", f"{vacancy:.2f}%"))
            
            if brick_metrics:
                cols = st.columns(min(3, len(brick_metrics)))
                for idx, (label, value) in enumerate(brick_metrics):
                    with cols[idx % len(cols)]:
                        st.metric(label, value)
            
            # Second row for Brick
            brick_metrics2 = []
            largest = data.get('largest_tenant_pct')
            if largest is not None and largest > 0:
                brick_metrics2.append(("Concentração Inquilinos", f"{largest:.2f}%"))
            term = data.get("avg_contract_term")
            if term:
                brick_metrics2.append(("Prazo Contratos", term))
            localizacao = data.get("localizacao")
            if localizacao:
                brick_metrics2.append(("Localização", localizacao))
            qualidade_imoveis = data.get("qualidade_imoveis")
            if qualidade_imoveis:
                brick_metrics2.append(("Qualidade Imóveis", qualidade_imoveis))
            
            if brick_metrics2:
                st.divider()
                cols = st.columns(len(brick_metrics2))
                for idx, (label, value) in enumerate(brick_metrics2):
                    with cols[idx]:
                        st.metric(label, value)
            
        # Specific Paper FII Metrics
        elif "papel" in fii_type_raw:
            st.divider()
            paper_metrics = []
            cdi = data.get("%_cdi_ipca")
            if cdi:
                paper_metrics.append(("Indexador", cdi))
            inad = data.get('inadimplencia')
            if inad is not None and inad > 0:
                paper_metrics.append(("Inadimplência", f"{inad:.2f}%"))
            qualidade_cris = data.get("qualidade_cris")
            if qualidade_cris:
                paper_metrics.append(("Qualidade CRIs", qualidade_cris))
            cri_ratings = data.get("cri_ratings")
            if cri_ratings and not qualidade_cris:
                paper_metrics.append(("Qualidade CRIs", cri_ratings))
            
            if paper_metrics:
                cols = st.columns(min(3, len(paper_metrics)))
                for idx, (label, value) in enumerate(paper_metrics):
                    with cols[idx % len(cols)]:
                        st.metric(label, value)

        displayed_keys = {
            "tipo_fii", "segment", "p_vp", "dy", "vacancy", "largest_tenant_pct", "avg_contract_term",
            "localizacao", "qualidade_imoveis", "%_cdi_ipca", "inadimplencia", "qualidade_cris",
            "cri_ratings"
        }
        extras = [(k, v) for k, v in data.items() if k not in displayed_keys and k != "ticker" and v is not None]
        if extras:
            st.divider()
            cols = st.columns(min(3, len(extras)))
            for idx, (key, value) in enumerate(extras):
                with cols[idx % len(cols)]:
                    st.metric(_labelize_key(key), _format_value(value))

# --- CONFIGURAÇÃO DA PÁGINA ---
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

# --- LÓGICA PRINCIPAL ---
if btn_search:
    raw_list = [x.strip() for x in assets_input.split(",") if x.strip()]
    asset_list = list(dict.fromkeys(raw_list)) 
    
    if not asset_list: 
        st.error("⚠️ Please enter at least one asset name!")
        st.stop() 
        
    with st.spinner(f"Analyzing {len(asset_list)} asset(s)..."):
        asset_type_url = "crypto" if market_type == "Cryptocurrency" else "stock"
        df_master = pd.DataFrame()
        st.subheader("📝 Analysis Summary")

        for asset in asset_list:
            url_api_csharp = f"{API_CSHARP_URL}/price/{asset_type_url}/{asset}/history" 
            
            try:
                response = requests.get(url_api_csharp)
                
                if response.status_code == 200:
                    complete_data = response.json()
                    analysis = complete_data["last_7_days"]
                    historical_prices = analysis.get("prices", [])
                    
                    if historical_prices:
                        current_price = historical_prices[-1]
                        fmt = "{:,.6f}" if analysis['average'] < 1 else "{:,.2f}"
                        
                        # --- CARDS EXPANSÍVEIS ---
                        with st.expander(f"🟢 {asset.upper()} | Current Price: ${fmt.format(current_price)}", expanded=True):
                            # 1. LINHA DE PREÇOS (C# API)
                            col1, col2, col3, col4, col5 = st.columns(5)
                            col1.metric("Average Price", f"${fmt.format(analysis['average'])}")
                            col2.metric("7-Day High", f"${fmt.format(analysis['max'])}")
                            
                            delta_color = "normal" if analysis['trend'] == "UP" else "inverse"
                            col3.metric("Trend", analysis['trend'], f"{analysis['percentage_change']}%", delta_color=delta_color)
                            col4.metric("Volatility (Risk)", fmt.format(analysis['volatility']))
                            
                            signal = str(analysis.get("action_signal", "HOLD")).upper()
                            color_hex = "#00FFAA" if signal in ["BUY", "STRONG BUY"] else "#FF4B4B" if signal == "SELL" else "#808495"
                            col5.markdown(f"<div><p style='font-size: 14px; margin-bottom: 0px; color: #FAFAFA;'>Action Signal</p><h2 style='color: {color_hex}; margin-top: 0px; padding: 0px;'>{signal}</h2></div>", unsafe_allow_html=True)

                            # 2. LINHA DE FUNDAMENTOS (Python API - Apenas B3)
                            if market_type == "Stocks/REITs (B3)":
                                st.divider()
                                a_type, fund_data, fund_status = fetch_fundamentals_with_fallback(asset)
                                if fund_data and a_type:
                                    render_fundamentals_ui(a_type, fund_data)
                                elif fund_status == 404:
                                    st.warning("⚠️ Dados fundamentalistas não encontrados para este ativo.")
                                else:
                                    st.error("⚠️ Serviço de fundamentos indisponível no momento. Tente novamente mais tarde.")

                        # Prepara DF para o Gráfico
                        df_temp = pd.DataFrame({
                            "Timeline (Data Points)": range(len(historical_prices)),
                            "Price": historical_prices,
                            "Asset": asset.upper()
                        })
                        df_master = pd.concat([df_master, df_temp], ignore_index=True)
                        
                    else:
                        st.warning(f"⚠️ Historical data not available for {asset.upper()}.")
                else:
                    st.error(f"❌ '{asset.upper()}' not found in the {market_type} database.")
                    
            except Exception as e:
                st.error(f"⚠️ Connection error for {asset.upper()}. Please check if the C# API is running! Details: {e}")

        # --- GRÁFICO COMPARATIVO ---
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
