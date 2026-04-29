import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# Visual configurations
st.set_page_config(page_title="Crypto Analytics", layout="wide")
st.title("📊 Dashboard Crypto Analysis")
st.markdown("Search for any cryptocurrency and get insights about its recent performance! Powered by CoinGecko API and a C# backend.")

# User interactions
with st.sidebar:
    st.header("Configurations")
    coin = st.text_input("Write the cryptocurrency name", value="bitcoin").lower()
    btn_search = st.button("Market Analysis")

# Button logic
if btn_search:
    with st.spinner(f"Searching crypto: {coin.capitalize()}..."):
        
        # Sua porta do C# (5091)
        url_api_csharp = f"http://localhost:5091/price/{coin}/history" 
        
        try:
            response = requests.get(url_api_csharp)
            
            if response.status_code == 200:
                complete_date = response.json()
                analysis = complete_date["last_7_days"]
                
                st.success("✅ Data retrieved successfully!")
                
                col1, col2, col3, col4 = st.columns(4)
                
                fmt = "{:,.6f}" if analysis['average'] < 1 else "{:,.2f}"
                
                col1.metric("Average Price (7d)", f"${fmt.format(analysis['average'])}")
                col2.metric("All-Time High", f"${fmt.format(analysis['max'])}")
                
                tendencia_sinal = analysis['percentage_change']
                col3.metric("Trend", analysis['trend'], f"{tendencia_sinal}%")
                
                col4.metric("Volatility (Risk)", fmt.format(analysis['volatility']))
                
                st.markdown("---") 
                st.subheader(f"📈 Price Curve (Last 7 days)")
                
                precos_historicos = analysis.get("prices", [])
                
                if precos_historicos:
                    df_grafico = pd.DataFrame({
                        "Hours (Last 7 Days)": range(len(precos_historicos)),
                        "Price (USD)": precos_historicos
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
                        file_name=f"report_{coin}.csv",
                        mime="text/csv",
                    )
                else:
                    st.warning("Historical data not available for this coin.")
                
            else:
                st.error("❌ Cryptocurrency not found in CoinGecko's database.")
                
        except Exception as e:
            st.error(f"⚠️ Connection error. Please check if the C# API is running! Details: {e}")