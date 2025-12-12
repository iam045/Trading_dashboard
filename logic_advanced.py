import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import load_google_sheet # 假設 utils 有這個，若無可直接用 app.py 傳進來的 xls

# ==========================================
# 0. 資料處理核心
# ==========================================

def get_advanced_data(xls):
    """
    從 '期望值' 分頁讀取更多欄位供進階分析使用
    """
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到 '期望值' 分頁"
    
    try:
        # 讀取 Excel (假設標題在第 15 列，即 header=14)
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        # -----------------------------------------------------------
        # ⚠️ 請根據您的 Excel 實際欄位位置調整這裡的數字 (Index)
        # 目前假設: 0=Date, 1=Strategy, 2=Symbol(標的), 10=Risk, 11=PnL
        # -----------------------------------------------------------
        
        needed_cols = [0, 1, 2, 10, 11] # Date, Strategy, Symbol, Risk, PnL
        
        if df.shape[1] < max(needed_cols): 
            return None, "表格欄位不足，請檢查 logic_advanced.py 中的欄位索引"

        df_clean = df.iloc[:, needed_cols].copy()
        df_clean.columns = ['Date', 'Strategy', 'Symbol', 'Risk_Amount', 'PnL']

        # 資料清理
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        df_clean['PnL'] = pd.to_numeric(df_clean['PnL'].astype(str).str.replace(',', ''), errors='coerce')
        
        # 去除空值 (日期或損益為空代表無效)
        df_clean = df_clean.dropna(subset=['Date', 'PnL'])
        
        # 增加輔助欄位：星期幾 (Monday=0, Sunday=6)
        df_clean['Weekday'] = df_clean['Date'].dt.day_name()
        df_clean['Weekday_Int'] = df_clean['Date'].dt.dayofweek
        
        return df_clean, None

    except Exception as e:
        return None, f"讀取失敗: {e}"

# ==========================================
# 1. 繪圖函式組
# ==========================================

def plot_strategy_performance(df):
    """功能 1: 各策略獨立分析 (Bar Chart + Win Rate)"""
    # 統計各策略數據
    stats = df.groupby('Strategy').agg(
        Total_PnL=('PnL', 'sum'),
        Count=('PnL', 'count'),
        Win_Count=('PnL', lambda x: (x > 0).sum())
    ).reset_index()
    
    stats['Win_Rate'] = stats['Win_Count'] / stats['Count']
    stats = stats.sort_values('Total_PnL', ascending=False)
    
    # 台股配色: 賺錢紅, 賠錢綠
    colors = ['#ef5350' if x >= 0 else '#26a69a' for x in stats['Total_PnL']]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=stats['Strategy'], 
        y=stats['Total_PnL'],
        marker_color=colors,
        text=stats['Total_PnL'].apply(lambda x: f"${x:,.0f}"),
        textposition='auto',
        name='總損益'
    ))
    
    # 雙軸：加入勝率線圖
    fig.add_trace(go.Scatter(
        x=stats['Strategy'],
        y=stats['Win_Rate'],
        yaxis='y2',
        mode='lines+markers',
        name='勝率',
        line=dict(color='#333', width=2, dash='dot')
    ))

    fig.update_layout(
        title="各策略總損益與勝率排名",
        yaxis=dict(title="總損益 ($)"),
        yaxis2=dict(title="勝率 (%)", overlaying='y', side='right', tickformat='.0%'),
        showlegend=True,
        height=500, # 加高一點讓單張圖更好看
        margin=dict(t=50, b=50)
    )
    return fig

def plot_cumulative_pnl_by_strategy(df):
    """建議功能: 策略權益曲線競賽 (Line Chart)"""
    df_sorted = df.sort_values('Date')
    df_sorted['CumPnL'] = df_sorted.groupby('Strategy')['PnL'].cumsum()
    
    fig = px.line(
        df_sorted, 
        x='Date', 
        y='CumPnL', 
        color='Strategy',
        title="各策略權益曲線 (誰是穩定獲利王？)",
        markers=False
    )
    fig.update_layout(
        height=500, # 加高一點
        hovermode="x unified",
        margin=dict(t=50, b=50)
    )
    return fig

def plot_weekday_analysis(df):
    """功能 2: 週一~週五 哪天容易贏 (Heatmap Style Bar)"""
    # 按照週一到週五排序
    cats = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    df['Weekday'] = pd.Categorical(df['Weekday'], categories=cats, ordered=True)
    
    weekday_stats = df.groupby('Weekday', observed=True).agg(
        Total_PnL=('PnL', 'sum'),
        Win_Rate=('PnL', lambda x: (x > 0).mean())
    ).reset_index()
    
    # 兩個圖表：左邊損益，右邊勝率
    c1, c2 = st.columns(2)
    
    # 圖1: 損益
    fig1 = go.Figure()
    colors1 = ['#ef5350' if x >= 0 else '#26a69a' for x in weekday_stats['Total_PnL']]
    fig1.add_trace(go.Bar(
        x=weekday_stats['Weekday'], 
        y=weekday_stats['Total_PnL'],
        marker_color=colors1,
        text=weekday_stats['Total_PnL'].apply(lambda x: f"${x:,.0f}")
    ))
    fig1.update_layout(title="週一至週五：總損益表現", height=350)
    
    # 圖2: 勝率
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=weekday_stats['Weekday'], 
        y=weekday_stats['Win_Rate'],
        marker_color='#5c6bc0',
        text=weekday_stats['Win_Rate'].apply(lambda x: f"{x:.1%}")
    ))
    fig2.update_layout(title="週一至週五：勝率表現", height=350, yaxis_tickformat='.0%')
    
    return fig1, fig2

def plot_symbol_ranking(df):
    """功能 3: 標的賺賠排名 (Horizontal Bar)"""
    # 統計標的損益
    symbol_stats = df.groupby('Symbol')['PnL'].sum().reset_index()
    symbol_stats = symbol_stats.sort_values('PnL', ascending=True) # 從虧最多排到賺最多
    
    # 取頭尾各 5 名 (如果標的太少就全取)
    if len(symbol_stats) > 10:
        top_5_losers = symbol_stats.head(5)
        top_5_winners = symbol_stats.tail(5)
        df_rank = pd.concat([top_5_losers, top_5_winners])
    else:
        df_rank = symbol_stats

    # 配色
    colors = ['#ef5350' if x >= 0 else '#26a69a' for x in df_rank['PnL']]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df_rank['Symbol'],
        x=df_rank['PnL'],
        orientation='h',
        marker_color=colors,
        text=df_rank['PnL'].apply(lambda x: f"${x:,.0f}"),
        textposition='outside'
    ))
    
    fig.update_layout(
        title="標的損益排行榜 (Top 5 賺錢 vs 賠錢)",
        xaxis_title="總損益 ($)",
        height=500,
        margin=dict(l=100) # 左邊留空給標的名稱
    )
    return fig

# ==========================================
# 2. 主入口
# ==========================================

def display_advanced_analysis(xls):
    st.markdown("### 🔍 交易細項深度分析")
    st.caption("挖掘數據背後的行為模式：策略穩定性、時間週期效應、以及選股能力。")
    
    # 1. 載入資料
    df, err = get_advanced_data(xls)
    if err:
        st.warning(f"⚠️ 無法進行分析: {err}")
        st.info("💡 請確認 '期望值' 分頁中，是否包含 '日期', '策略', '標的', '損益' 等欄位。")
        return
        
    if df.empty:
        st.info("目前沒有足夠的交易資料可供分析。")
        return

    st.markdown("---")

    # --- Section 1: 策略分析 (改為上下排列) ---
    st.subheader("1️⃣ 策略效能檢閱")
    
    # 第一張：各策略總損益 Bar Chart
    st.plotly_chart(plot_strategy_performance(df), use_container_width=True)
    
    st.write("") # 增加一點間距
    
    # 第二張：策略權益曲線 Line Chart
    st.plotly_chart(plot_cumulative_pnl_by_strategy(df), use_container_width=True)

    st.markdown("---")

    # --- Section 2: 週期分析 ---
    st.subheader("2️⃣ 交易週期效應 (Day of Week)")
    st.caption("檢查是否有「黑色星期X」魔咒，或是特定的獲利日。")
    fig_day_pnl, fig_day_win = plot_weekday_analysis(df)
    
    dc1, dc2 = st.columns(2)
    with dc1: st.plotly_chart(fig_day_pnl, use_container_width=True)
    with dc2: st.plotly_chart(fig_day_win, use_container_width=True)

    st.markdown("---")

    # --- Section 3: 標的分析 ---
    st.subheader("3️⃣ 標的 (Symbol) 損益風雲榜")
    st.caption("賺最多與賠最多的前 5 名標的。")
    
    st.plotly_chart(plot_symbol_ranking(df), use_container_width=True)
