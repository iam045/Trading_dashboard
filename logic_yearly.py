import streamlit as st
import pandas as pd
import plotly.express as px

def get_yearly_data(xls):
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    try:
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        df = df[['日期', '損益', '標準R(盈虧比)']].copy()
        df.columns = ['Date', 'PnL', 'R']
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date', 'PnL'])
        df['Year'] = df['Date'].dt.year
        df['Month'] = df['Date'].dt.month
        return df, None
    except:
        return None, "年度資料讀取失敗"

def show_yearly_page(xls):
    st.header("📅 年度績效回顧")
    df, error = get_yearly_data(xls)
    if error: st.error(error); return
    
    yearly_sum = df.groupby('Year')['PnL'].sum()
    st.bar_chart(yearly_sum)
    
    st.subheader("月度獲利熱圖")
    month_pivot = df.pivot_table(index='Year', columns='Month', values='PnL', aggfunc='sum').fillna(0)
    st.write(month_pivot)
