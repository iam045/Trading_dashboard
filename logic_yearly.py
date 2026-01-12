import pandas as pd
import plotly.graph_objects as go
import re
from datetime import datetime

def get_yearly_data_and_chart(xls, year):
    """根據年份抓取日報表並生成 KPI"""
    sheet_name = next((s for s in xls.sheet_names if f"日報表{year}" in s.replace(" ", "")), None)
    if not sheet_name: return None
    
    try:
        # 假設日報表結構未變動，抓取第 1 欄(日期)與第 8 欄(損益)
        df = pd.read_excel(xls, sheet_name=sheet_name, header=4)
        df = df.iloc[:, [0, 7]].copy()
        df.columns = ['Date', 'Daily_PnL']
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])
        
        df['Cumulative'] = df['Daily_PnL'].cumsum()
        final_pnl = df['Cumulative'].iloc[-1]
        high = df['Cumulative'].max()
        low = df['Cumulative'].min()
        mdd = (df['Cumulative'] - df['Cumulative'].cummax()).min()
        
        # 繪圖
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['Date'], y=df['Cumulative'], mode='lines', line=dict(color='#81C7D4')))
        fig.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
        
        # 月統計預留
        m_stats = {f"{m}月": "---" for m in range(1, 13)}
        
        return fig, final_pnl, high, low, mdd, m_stats
    except:
        return None
