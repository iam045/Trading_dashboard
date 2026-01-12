import streamlit as st
import pandas as pd
import plotly.express as px

def get_advanced_data(xls):
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到分頁"
    
    try:
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        # 定義可能存在的欄位
        mapping = {'日期': 'Date', '損益': 'PnL', '標準R(盈虧比)': 'PnL_R', '策略': 'Strategy', '標的': 'Symbol'}
        
        existing = {k: v for k, v in mapping.items() if k in df.columns}
        df_clean = df[list(existing.keys())].rename(columns=existing)
        
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        df_clean['PnL'] = pd.to_numeric(df_clean['PnL'], errors='coerce')
        
        # 預設值處理
        if 'Strategy' not in df_clean.columns: df_clean['Strategy'] = '所有交易'
        if 'Symbol' not in df_clean.columns: df_clean['Symbol'] = '未分類'
        
        return df_clean.dropna(subset=['Date', 'PnL']), None
    except Exception as e:
        return None, str(e)

def display_advanced_analysis(xls):
    st.header("🔍 進階交易細項分析")
    df, error = get_advanced_data(xls)
    
    if error:
        st.error(error)
        return

    # 簡單分析：星期幾表現最好
    df['Weekday'] = df['Date'].dt.day_name()
    weekday_pnl = df.groupby('Weekday')['PnL'].sum().reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
    
    st.subheader("每週交易表現")
    st.bar_chart(weekday_pnl)

    # 策略佔比
    st.subheader("策略獲利分佈")
    fig = px.pie(df, names='Strategy', values='PnL', hole=0.3)
    st.plotly_chart(fig, use_container_width=True)
