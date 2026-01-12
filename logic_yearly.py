import pandas as pd
import plotly.graph_objects as go
import re
from datetime import datetime
from utils import read_daily_pnl, insert_zero_crossings # 確保從 utils 引用功能

def get_yearly_data_and_chart(xls, year):
    """
    負責處理單一年度的所有數據計算與繪圖，回傳 KPI 與 Figure 物件。
    """
    sheet_map = {re.sub(r"[ _－/.-]", "", str(n)): n for n in xls.sheet_names}
    all_data = []

    for m in range(1, 13):
        targets = [f"日報表{year}{m:02d}", f"日報表{year}{m}"]
        real_name = next((sheet_map[t] for t in targets if t in sheet_map), None)
        if real_name:
            df_m = read_daily_pnl(xls, real_name)
            if not df_m.empty: all_data.append(df_m)
    
    if not all_data: return None

    df_year = pd.concat(all_data)
    df_year = df_year[df_year['Date'].dt.year == year]
    
    # 未來過濾邏輯
    current_year = datetime.now().year
    if year == current_year:
        df_year = df_year[df_year['Date'] <= pd.Timestamp.now().normalize()]
    
    if df_year.empty: return None

    df_year = df_year.sort_values('Date')
    df_year['Cumulative_PnL'] = df_year['Daily_PnL'].cumsum()
    
    # KPI 計算
    latest_pnl = df_year['Cumulative_PnL'].iloc[-1]
    max_pnl = df_year['Cumulative_PnL'].max()
    min_pnl = df_year['Cumulative_PnL'].min()
    running_max = df_year['Cumulative_PnL'].cummax()
    mdd = (df_year['Cumulative_PnL'] - running_max).min()
    
    # 月統計
    monthly_sums = df_year.groupby(df_year['Date'].dt.month)['Daily_PnL'].sum()
    m_stats = {f"{m}月": f"${monthly_sums.get(m, 0):,.0f}" if m in monthly_sums else "---" for m in range(1, 13)}

    # 繪圖
    df_plot = insert_zero_crossings(df_year)
    y_pos = df_plot['Cumulative_PnL'].apply(lambda x: x if x >= 0 else None)
    y_neg = df_plot['Cumulative_PnL'].apply(lambda x: x if x <= 0 else None)

    fig = go.Figure()
    # 獲利區 (紅色)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=y_pos, mode='lines', name='獲利',
                             line=dict(color='#ff4d4d', width=2), fill='tozeroy', fillcolor='rgba(255, 77, 77, 0.1)'))
    # 虧損區 (綠色)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=y_neg, mode='lines', name='虧損',
                             line=dict(color='#00cc66', width=2), fill='tozeroy', fillcolor='rgba(0, 204, 102, 0.1)'))

    month_starts = [pd.Timestamp(f"{year}-{m:02d}-01") for m in range(1, 13)]
    for d in month_starts:
        if d.month > 1: fig.add_vline(x=d, line_width=1, line_dash="dash", line_color="gray", opacity=0.3)

    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        xaxis_title="", yaxis_title="累計損益",
        hovermode="x unified", height=450, showlegend=False,
        xaxis=dict(range=[f"{year}-01-01", f"{year}-12-31"], tickmode='array',
                   tickvals=month_starts, ticktext=[f"{m}月" for m in range(1, 13)])
    )
    
    return fig, latest_pnl, max_pnl, min_pnl, mdd, m_stats
