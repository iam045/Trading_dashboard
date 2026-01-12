import streamlit as st
import pandas as pd
import plotly.express as px

def get_advanced_data(xls):
    """進階分析資料讀取"""
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到分頁"
    
    try:
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        # 欄位映射
        mapping = {'日期': 'Date', '損益': 'PnL', '標準R(盈虧比)': 'R', '標的': 'Symbol', '策略': 'Strategy'}
        existing = {k: v for k, v in mapping.items() if k in df.columns}
        df = df[list(existing.keys())].rename(columns=existing)
        
        # 轉型
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['PnL'] = pd.to_numeric(df['PnL'], errors='coerce')
        df['R'] = pd.to_numeric(df['R'], errors='coerce')
        
        # 預設缺失欄位
        if 'Strategy' not in df.columns: df['Strategy'] = '未分類'
        if 'Symbol' not in df.columns: df['Symbol'] = '未知標的'
        
        df = df.dropna(subset=['Date', 'PnL']).query("PnL != 0")
        df['Weekday'] = df['Date'].dt.day_name()
        df['Result'] = df['PnL'].apply(lambda x: '獲利' if x > 0 else '虧損')
        
        return df, None
    except Exception as e:
        return None, str(e)

def show_advanced_page(xls):
    st.header("📊 進階績效拆解")
    df, error = get_advanced_data(xls)
    if error:
        st.error(error); return

    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("獲利/虧損 分佈")
        fig_pie = px.pie(df, names='Result', values='PnL', hole=0.4, color='Result',
                         color_discrete_map={'獲利':'#2ecc71', '虧損':'#e74c3c'})
        st.plotly_chart(fig_pie)

    with c2:
        st.subheader("星期交易績效 (R)")
        order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        week_stats = df.groupby('Weekday')['R'].sum().reindex(order)
        st.bar_chart(week_stats)

    st.subheader("策略表現分析")
    strat_stats = df.groupby('Strategy').agg({'PnL': 'sum', 'R': 'mean', 'Date': 'count'}).rename(columns={'Date': '筆數', 'R': '平均期望值'})
    st.table(strat_stats)
