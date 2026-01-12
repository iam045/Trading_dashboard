import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# ==========================================
# 0. 資料處理核心
# ==========================================

def get_advanced_data(xls):
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到 '期望值' 分頁"
    
    try:
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        mapping = {
            '日期': 'Date',
            '策略': 'Strategy',
            '標的': 'Symbol',
            '1R單位': 'Risk_Amount',
            '損益': 'PnL',
            '標準R(盈虧比)': 'R' 
        }
        
        for excel_col, target_col in mapping.items():
            if excel_col not in df.columns:
                if target_col == 'Strategy': df[excel_col] = '未分類'
                elif target_col == 'Symbol': df[excel_col] = '未知標的'
                else: df[excel_col] = np.nan
        
        df_clean = df[[col for col in mapping.keys() if col in df.columns]].copy()
        df_clean.rename(columns=mapping, inplace=True)

        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        for col in ['PnL', 'R', 'Risk_Amount']:
            if col in df_clean.columns:
                df_clean[col] = pd.to_numeric(df_clean[col].astype(str).str.replace(',', ''), errors='coerce')
        
        df_clean = df_clean.dropna(subset=['Date', 'PnL'])
        df_clean = df_clean[df_clean['PnL'] != 0]
        df_clean['Weekday'] = df_clean['Date'].dt.day_name()
        
        return df_clean.sort_values('Date'), None
    except Exception as e:
        return None, f"讀取失敗: {e}"

# ==========================================
# 1. 繪圖函式組 (新增與優化分佈圖)
# ==========================================

def plot_pnl_distribution(df):
    """損益金額分佈圖 (含極端值修正)"""
    fig = go.Figure()
    abs_max = df['PnL'].abs().max()
    bin_size = abs_max / 20 if abs_max > 0 else 100
    bin_end_limit = abs_max + bin_size # 往外推一格確保包含極端值

    fig.add_trace(go.Histogram(
        x=df[df['PnL'] > 0]['PnL'], name='獲利', marker_color='#ef5350', opacity=0.75,
        xbins=dict(start=0, end=bin_end_limit, size=bin_size), autobinx=False
    ))
    fig.add_trace(go.Histogram(
        x=df[df['PnL'] < 0]['PnL'], name='虧損', marker_color='#26a69a', opacity=0.75,
        xbins=dict(start=-bin_end_limit, end=0, size=bin_size), autobinx=False
    ))
    fig.update_layout(
        title="損益金額頻率分佈 ($)", barmode='overlay', height=350,
        xaxis=dict(range=[-abs_max * 1.2, abs_max * 1.2]),
        margin=dict(t=40, b=20, l=40, r=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def plot_r_distribution(df):
    """R值分佈圖 (標準化風險分佈)"""
    fig = go.Figure()
    # R 值的範圍通常較小且集中，我們設定固定的 bin_size 為 0.25 R
    abs_max_r = df['R'].abs().max()
    bin_size = 0.5 if abs_max_r > 5 else 0.25
    bin_end_limit = abs_max_r + bin_size

    fig.add_trace(go.Histogram(
        x=df[df['R'] > 0]['R'], name='獲利 (R)', marker_color='#ef5350', opacity=0.75,
        xbins=dict(start=0, end=bin_end_limit, size=bin_size), autobinx=False
    ))
    fig.add_trace(go.Histogram(
        x=df[df['R'] < 0]['R'], name='虧損 (R)', marker_color='#26a69a', opacity=0.75,
        xbins=dict(start=-bin_end_limit, end=0, size=bin_size), autobinx=False
    ))
    fig.update_layout(
        title="R值頻率分佈 (標準化風險)", barmode='overlay', height=350,
        xaxis=dict(title="R 倍數", range=[-abs_max_r * 1.2, abs_max_r * 1.2]),
        margin=dict(t=40, b=20, l=40, r=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# --- 保持其餘繪圖函式不變 ---
def plot_symbol_ranking(df):
    symbol_stats = df.groupby('Symbol')['PnL'].sum().reset_index().sort_values('PnL', ascending=True)
    df_rank = pd.concat([symbol_stats.head(5), symbol_stats.tail(5)]).drop_duplicates().sort_values('PnL', ascending=True)
    fig = go.Figure(go.Bar(y=df_rank['Symbol'], x=df_rank['PnL'], orientation='h', marker_color=['#ef5350' if x >= 0 else '#26a69a' for x in df_rank['PnL']], text=df_rank['PnL'].apply(lambda x: f"${x:,.0f}"), textposition='outside'))
    fig.update_layout(title="標的損益排行榜", height=450, margin=dict(l=100, t=40, b=40))
    return fig

def plot_strategy_performance(df):
    stats = df.groupby('Strategy').agg(Total_PnL=('PnL', 'sum'), Count=('PnL', 'count'), Win_Count=('PnL', lambda x: (x > 0).sum())).reset_index()
    stats['Win_Rate'] = stats['Win_Count'] / stats['Count']
    stats = stats.sort_values('Total_PnL', ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=stats['Strategy'], y=stats['Total_PnL'], marker_color=['#ef5350' if x >= 0 else '#26a69a' for x in stats['Total_PnL']], text=stats['Total_PnL'].apply(lambda x: f"${x:,.0f}"), name='總損益'))
    fig.add_trace(go.Scatter(x=stats['Strategy'], y=stats['Win_Rate'], yaxis='y2', mode='lines+markers', name='勝率', line=dict(color='#333', width=2, dash='dot')))
    fig.update_layout(title="策略總損益與勝率", yaxis2=dict(overlaying='y', side='right', tickformat='.0%'), showlegend=True, height=350)
    return fig

def plot_cumulative_pnl_by_strategy(df):
    df_sorted = df.sort_values('Date')
    df_sorted['CumPnL'] = df_sorted.groupby('Strategy')['PnL'].cumsum()
    fig = px.line(df_sorted, x='Date', y='CumPnL', color='Strategy', title="策略權益曲線")
    fig.update_layout(height=350)
    return fig

def plot_strategy_quality_bubble(df):
    stats = df.groupby('Strategy').apply(lambda x: pd.Series({
        'Win_Rate': (x['PnL'] > 0).mean(),
        'Avg_Win_R': x[x['R'] > 0]['R'].mean() if not x[x['R'] > 0].empty else 0,
        'Avg_Loss_R': abs(x[x['R'] <= 0]['R'].mean()) if not x[x['R'] <= 0].empty else 1,
        'Total_PnL': x['PnL'].sum()
    })).reset_index()
    stats['Payoff_Ratio_R'] = stats['Avg_Win_R'] / stats['Avg_Loss_R']
    fig = px.scatter(stats, x="Win_Rate", y="Payoff_Ratio_R", size=stats['Total_PnL'].abs(), color="Total_PnL", hover_name="Strategy", color_continuous_scale=["#26a69a", "#eeeeee", "#ef5350"], title="策略品質矩陣 (R)")
    fig.add_hline(y=1, line_dash="dash"); fig.add_vline(x=0.5, line_dash="dash")
    fig.update_layout(xaxis_tickformat='.0%', height=350, coloraxis_showscale=False)
    return fig

def plot_win_loss_box(df):
    fig = go.Figure()
    fig.add_trace(go.Box(y=df[df['PnL'] > 0]['PnL'], name='獲利規模', marker_color='#ef5350', boxpoints='all'))
    fig.add_trace(go.Box(y=df[df['PnL'] < 0]['PnL'], name='虧損規模', marker_color='#26a69a', boxpoints='all'))
    fig.update_layout(title="賺賠規模對比 (Box Plot)", height=350)
    return fig

def plot_weekday_analysis(df):
    cats = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    df['Weekday'] = pd.Categorical(df['Weekday'], categories=cats, ordered=True)
    daily_df = df.groupby(['Date', 'Weekday'], observed=True)['PnL'].sum().reset_index()
    weekday_stats = daily_df.groupby('Weekday', observed=True).agg(Total_PnL=('PnL', 'sum'), Win_Rate=('PnL', lambda x: (x > 0).mean())).reset_index()
    fig1 = go.Figure(go.Bar(x=weekday_stats['Weekday'], y=weekday_stats['Total_PnL'], marker_color=['#ef5350' if x >= 0 else '#26a69a' for x in weekday_stats['Total_PnL']]))
    fig1.update_layout(title="週一至週五：總損益表現", height=350)
    fig2 = go.Figure(go.Bar(x=weekday_stats['Weekday'], y=weekday_stats['Win_Rate'], marker_color='#5c6bc0'))
    fig2.update_layout(title="週一至週五：勝率 (以日計算)", height=350, yaxis_tickformat='.0%')
    return fig1, fig2

# ==========================================
# 2. 局部刷新元件與主入口
# ==========================================

@st.fragment
def draw_strategy_section(df):
    st.subheader("1️⃣ 策略效能深度檢閱")
    all_strategies = sorted(df['Strategy'].unique().tolist())
    selected_strategies = st.multiselect("🎯 篩選策略:", options=all_strategies, default=all_strategies)
    if not selected_strategies: st.warning("⚠️ 請至少勾選一個策略"); return
    df_filtered = df[df['Strategy'].isin(selected_strategies)]
    c1, c2, c3 = st.columns(3)
    with c1: st.plotly_chart(plot_strategy_performance(df_filtered), use_container_width=True)
    with c2: st.plotly_chart(plot_cumulative_pnl_by_strategy(df_filtered), use_container_width=True)
    with c3: st.plotly_chart(plot_strategy_quality_bubble(df_filtered), use_container_width=True)

def display_advanced_analysis(xls):
    st.markdown("### 🔍 交易細項深度分析")
    df, err = get_advanced_data(xls)
    if err: st.warning(f"⚠️ 無法進行分析: {err}"); return
    if df.empty: st.info("目前沒有交易資料。"); return

    st.markdown("---")
    draw_strategy_section(df)
    st.markdown("---")

    # --- Section 2: 分佈圖切換邏輯 ---
    st.subheader("2️⃣ 整體損益分佈結構")
    
    # 在這裡新增切換開關，不影響大版面
    dist_mode = st.radio(
        "📊 切換分佈模式:",
        options=["損益金額 ($)", "R值單位 (R)"],
        horizontal=True,
        label_visibility="collapsed" # 隱藏標籤讓畫面更乾淨
    )

    wins = df[df['PnL'] > 0]['PnL']
    losses = df[df['PnL'] < 0]['PnL']
    m1, m2, m3 = st.columns(3)
    m1.metric("常態獲利 (中位數)", f"${wins.median():,.0f}")
    m2.metric("常態虧損 (中位數)", f"${losses.median():,.0f}")
    m3.metric("樣本總數", f"{len(df)} 筆")

    d1, d2 = st.columns(2)
    with d1: 
        # 根據開關狀態顯示不同圖表
        if dist_mode == "損益金額 ($)":
            st.plotly_chart(plot_pnl_distribution(df), use_container_width=True)
        else:
            st.plotly_chart(plot_r_distribution(df), use_container_width=True)
            
    with d2: st.plotly_chart(plot_win_loss_box(df), use_container_width=True)

    st.markdown("---")
    st.subheader("3️⃣ 交易週期效應")
    f1, f2 = plot_weekday_analysis(df)
    dc1, dc2 = st.columns(2)
    with dc1: st.plotly_chart(f1, use_container_width=True)
    with dc2: st.plotly_chart(f2, use_container_width=True)
    st.markdown("---")
    st.subheader("4️⃣ 標的損益排行榜")
    st.plotly_chart(plot_symbol_ranking(df), use_container_width=True)
