import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# Visual configurations and title
st.set_page_config(page_title="Market Analytics", layout="wide")
st.title("📊 Market Analytics Dashboard")
st.markdown("Welcome to the Market Analytics Dashboard! Here you can analyze the price trends of cryptocurrencies and stocks listed on B3. Select a market, enter the ticker or asset name, and get insights about the last 7 days of price movements, including average price, all-time high, trend, and volatility. You can also visualize the price curve and download a CSV report for further analysis.")

# User interactions
with st.sidebar:
    st.header("Configurations")
    
    market_type = st.radio("Select a Market:", ["Criptocurrency", "Ações/FIIs (B3)"])
    
    placeholder = "ex: bitcoin" if market_type == "Criptocurrency" else "ex: petr4"
    ative = st.text_input("Enter the Ticker or Asset Name", placeholder=placeholder).lower()
    
    btn_search = st.button("🔍 Analyze")

# Button logic
if btn_search:
    if not ative.strip(): 
        st.error("⚠️ Por favor, digite o nome de um ativo!")
        st.stop() 
        
    with st.spinner(f"Analyzing {ative.upper()}..."):
        
        asset_type_url = "crypto" if market_type == "Criptocurrency" else "stock"

        url_api_csharp = f"http://localhost:5091/price/{asset_type_url}/{ative}/history" 
        
        try:
            response = requests.get(url_api_csharp)
            
            if response.status_code == 200:
                complete_data = response.json()
                analysis = complete_data["last_7_days"]
                
                st.success("✅ Data retrieved successfully!")
                
                historical_prices = analysis.get("prices", [])
                current_price = historical_prices[-1] if historical_prices else 0.0

                fmt = "{:,.6f}" if analysis['average'] < 1 else "{:,.2f}"
                
                st.metric("Current price", f"${fmt.format(current_price)}", delta=f"{analysis['percentage_change']}%", delta_color="normal")
                
                st.markdown("---")
                
                st.subheader("Analysis of the Week (Last 7 Days)")
                col1, col2, col3, col4 = st.columns(4)
                
                delta_val = f"{analysis['percentage_change']}%"
                
                col1.metric("Average Price", f"${fmt.format(analysis['average'])}")
                col2.metric("All-Time High", f"${fmt.format(analysis['max'])}")
                col3.metric("Volatility (Risk)", fmt.format(analysis['volatility']))
                
                delta_color = "normal" if analysis['trend'] == "UP" else "inverse"
                col4.metric("Tendency", analysis['trend'], delta=delta_val, delta_color=delta_color)
                
                st.markdown("---") 
                st.subheader(f"📈 Price Curve (Last 7 days)")
                
                historical_prices = analysis.get("prices", [])
                
                if historical_prices:
                    df_grafico = pd.DataFrame({
                        "Hours (Last 7 Days)": range(len(historical_prices)),
                        "Price (USD)": historical_prices
                    })

                    fig = px.line(
                        df_grafico, 
                        x="Hours (Last 7 Days)", 
                        y="Price (USD)", 
                        color_discrete_sequence=["#00FFAA"] 
                    )
                    
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

                    csv_file = df_grafico.to_csv(index=False).encode('utf-8')
                    
                    st.markdown("---")
                    st.download_button(
                        label="📥 Download Report (CSV)",
                        data=csv_file,
                        file_name=f"report_{ative}.csv",
                        mime="text/csv",
                    )
                else:
                    st.warning("Historical data not available for this coin.")
                
            else:
                if asset_type_url == "crypto":
                    st.error(f"❌ {ative.capitalize()} not found in database.")
                    
                elif asset_type_url == "stock":
                    st.error(f"❌ {ative} not found in B3 (Brapi). Please check the ticker and try again.")
                
        except Exception as e:
            st.error(f"⚠️ Connection error. Please check if the C# API is running! Details: {e}")