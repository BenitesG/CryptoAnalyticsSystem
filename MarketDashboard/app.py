import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# Visual configurations and title
st.set_page_config(page_title="Market Analytics", layout="wide")
st.title("📊 Market Analytics Dashboard")
st.markdown("Welcome to the Market Analytics Dashboard! Analyze and compare price trends of Cryptocurrencies and Stocks listed on B3.")

# User interactions
with st.sidebar:
    st.header("Configurations")
    
    market_type = st.radio("Select a Market:", ["Cryptocurrency", "Stocks/REITs (B3)"])
    
    st.markdown("*(To compare assets, separate them by commas. Ex: petr4, vale3)*")
    
    placeholder = "ex: bitcoin, ethereum" if market_type == "Cryptocurrency" else "ex: petr4, mxrf11"
    assets_input = st.text_input("Enter Tickers or Asset Names", placeholder=placeholder).lower()
    
    btn_search = st.button("🔍 Analyze Market")

# Button logic
if btn_search:
    
    # 1. FIX DUPLICATES: Transform input into a clean, deduplicated list
    raw_list = [x.strip() for x in assets_input.split(",") if x.strip()]
    asset_list = list(dict.fromkeys(raw_list)) # This removes duplicates but keeps the order!
    
    if not asset_list: 
        st.error("⚠️ Please enter at least one asset name!")
        st.stop() 
        
    with st.spinner(f"Analyzing {len(asset_list)} asset(s)..."):
        
        asset_type_url = "crypto" if market_type == "Cryptocurrency" else "stock"
        
        df_master = pd.DataFrame()
        
        st.subheader("📝 Analysis Summary (Last 7 Days)")

        for asset in asset_list:
            # Note: Ensure the port (5091) matches your C# API
            url_api_csharp = f"http://localhost:5091/price/{asset_type_url}/{asset}/history" 
            
            try:
                response = requests.get(url_api_csharp)
                
                if response.status_code == 200:
                    complete_data = response.json()
                    analysis = complete_data["last_7_days"]
                    historical_prices = analysis.get("prices", [])
                    
                    if historical_prices:
                        current_price = historical_prices[-1]
                        fmt = "{:,.6f}" if analysis['average'] < 1 else "{:,.2f}"
                        
                        # --- BEAUTIFUL EXPANDABLE CARDS ---
                        # Create an expander for each asset
                        with st.expander(f"🟢 {asset.upper()} | Current Price: ${fmt.format(current_price)}", expanded=True):
                            col1, col2, col3, col4 = st.columns(4)
                            
                            col1.metric("Average Price", f"${fmt.format(analysis['average'])}")
                            col2.metric("7-Day High", f"${fmt.format(analysis['max'])}")
                            
                            delta_color = "normal" if analysis['trend'] == "UP" else "inverse"
                            col3.metric("Trend", analysis['trend'], f"{analysis['percentage_change']}%", delta_color=delta_color)
                            
                            col4.metric("Volatility (Risk)", fmt.format(analysis['volatility']))
                        # ----------------------------------

                        # Build a temporary DataFrame for the chart
                        # We use 'Timeline' because Crypto is 168 hours, but B3 is 5 days.
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

        # Comparative Chart
        if not df_master.empty:
            st.markdown("---") 
            st.subheader(f"📈 Comparative Price Curve")
            
            fig = px.line(
                df_master, 
                x="Timeline (Data Points)", 
                y="Price", 
                color="Asset"
            )
            
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

            # Export CSV
            csv_file = df_master.to_csv(index=False).encode('utf-8')
            
            st.markdown("---")
            st.download_button(
                label="📥 Download Consolidated Report (CSV)",
                data=csv_file,
                file_name="consolidated_market_report.csv",
                mime="text/csv",
            )