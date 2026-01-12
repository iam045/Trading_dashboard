import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# ==========================================
# 0. 資料處理核心 (修復為名稱對應)
# ==========================================

def get_advanced_data(xls):
    """從 Excel 讀取數據，並對齊最新欄位名稱"""
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到 '期望值' 分頁"
    
    try:
        # header=14 代表從第 15 列開始抓取
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        # 欄位映射表：對齊您 Excel 的中文字標題
        mapping = {
            '日期': 'Date',
            '策略': 'Strategy',
            '標的': 'Symbol',
            '1R單位': 'Risk_Amount',
            '損益': 'PnL',
            '標準R(盈虧比)': 'R'
        }
        
        # 檢查必備欄位是否存在，若不存在則補空值或預設值
        for excel_col, target_col in mapping.items():
            if excel_col not in df.columns:
                if target_col == 'Strategy': df[excel_col] = '未分類'
                elif target_col == 'Symbol': df[excel_col] = '未知標的'
                else: df[excel_col] = np.nan
        
        # 重新整理 DataFrame
        df_clean = df[[col for col in mapping.keys()]].copy()
        df_clean.rename(columns=mapping, inplace=True)

        # 數值清理與轉型
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        for col in ['PnL', 'R', 'Risk_Amount']:
            df_clean[col] = pd.to_numeric(df_clean[col].astype(str).str.replace(',', ''), errors='coerce')
        
        # 移除無效日期與排除損益為 0 的單 (平盤不計入統計)
        df_clean = df_clean.dropna(subset=['Date', 'PnL'])
        df_clean = df_clean[df_clean['PnL'] != 0]
        
        # 增加星期資訊
        df_clean['Weekday'] = df_clean['Date'].dt.day_name()
        
        return df_clean.sort_values('Date'), None

    except Exception as e:
        return None, f"讀取失敗: {e}"

# ==========================================
# 1. 繪圖函式組 (保持您原有的精美邏輯)
# ==========================================

def plot_strategy_performance(df):
    stats = df.groupby('Strategy').agg(
        Total_PnL=('PnL', 'sum'),
        Count=('PnL', 'count'),
        Win_Count=('PnL', lambda x: (x > 0).sum())
    ).reset_index()
    
    stats['Win_Rate'] = stats['Win_Count'] / stats['Count']
    stats = stats.sort_values('Total_PnL', ascending=False)
    
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
    
    fig.add_trace(go.Scatter(
        x=stats['Strategy'],
        y=stats['Win_Rate'],
        yaxis='y2',
        mode='lines+markers',
        name='勝率',
        line=dict(color='#333', width=2, dash='dot')
    ))

    fig.update_layout(
        title="策略總損益與勝率",
        yaxis=dict(title="總損益 ($)"),
        yaxis2=dict(title="勝率 (%)", overlaying='y', side='right', tickformat='.0%'),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=350, 
        margin=dict(t=40, b=20, l=40, r=40)
    )
    return fig

def plot_cumulative_pnl_by_strategy(df):
    df_sorted = df.sort_values('Date')
    df_sorted['CumPnL'] = df_sorted.groupby('Strategy')['PnL'].cumsum()
    
    fig = px.line(
        df_sorted, 
        x='Date', 
        y='CumPnL', 
        color='Strategy',
        title="策略權益曲線",
        markers=False
    )
    fig.update_layout(
        height=350,
        hovermode="x unified",
        margin=dict(t=40, b=20, l=20, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def plot_strategy_quality_bubble(df):
    # 使用 R 值計算品質矩陣
    stats = df.groupby('Strategy').apply(lambda x: pd.Series({
        'Win_Rate': (x['PnL'] > 0).mean(),
        'Avg_Win_R': x[x['R'] > 0]['R'].mean() if not x[x['R'] > 0].empty else 0,
        'Avg_Loss_R': abs(x[x['R'] <= 0]['R'].mean()) if not x[x['R'] <= 0].empty else 1,
        'Total_PnL': x['PnL'].sum(),
        'Count': len(x)
    })).reset_index()

    stats['Payoff_Ratio_R'] = stats['Avg_Win_R'] / stats['Avg_Loss_R']
    stats['Bubble_Size'] = stats['Total_PnL'].abs()
    
    fig = px.scatter(
        stats,
        x="Win_Rate",
        y="Payoff_Ratio_R",
        size="Bubble_Size",
        color="Total_PnL",
        hover_name="Strategy",
        hover_data={"Bubble_Size": False, "Total_PnL": ":,.0f", "Count": True, "Avg_Win_R": ":.2f", "Avg_Loss_R": ":.2f"},
        color_continuous_scale=["#26a69a", "#eeeeee", "#ef5350"],
        title="策略品質矩陣 (R)"
    )
    
    fig.add_hline(y=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0.5, line_dash="dash", line_color="gray")

    fig.update_layout(
        xaxis_title="勝率",
        yaxis_title="盈虧比 (R)",
        xaxis_tickformat='.0%',
        height=350,
        margin=dict(t=40, b=20, l=20, r=20),
        coloraxis_showscale=False
    )
    return fig

def plot_pnl_distribution(df):
    fig = go.Figure()
    wins = df[df['PnL'] > 0]['PnL']
    fig.add_trace(go.Histogram(x=wins, name='獲利', marker_color='#ef5350', opacity=0.75))
    
    losses = df[df['PnL'] < 0]['PnL']
    fig.add_trace(go.Histogram(x=losses, name='虧損', marker_color='#26a69a', opacity=0.75))

    fig.update_layout(
        title="損益金額頻率分佈 (Histogram)",
        barmode='overlay', 
        height=350,
        margin=dict(t=40, b=20, l=40, r=40)
    )
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
    weekday_stats = daily_df.groupby('Weekday', observed=True).agg(
        Total_PnL=('PnL', 'sum'),
        Win_Rate=('PnL', lambda x: (x > 0).mean()),
        Day_Count=('PnL', 'count')
    ).reset_index()
    
    fig1 = go.Figure()
    colors1 = ['#ef5350' if x >= 0 else '#26a69a' for x in weekday_stats['Total_PnL']]
    fig1.add_trace(go.Bar(x=weekday_stats['Weekday'], y=weekday_stats['Total_PnL'], marker_color=colors1))
    fig1.update_layout(title="週一至週五：總損益表現", height=350)
    
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=weekday_stats['Weekday'], y=weekday_stats['Win_Rate'], marker_color='#5c6bc0'))
    fig2.update_layout(title="週一至週五：勝率 (以日計算)", height=350, yaxis_tickformat='.0%')
    
    return fig1, fig2

def plot_symbol_ranking(df):
    symbol_stats = df.groupby('Symbol')['PnL'].sum().reset_index().sort_values('PnL', ascending=True)
    df_rank = symbol_stats.tail(10) # 顯示前 10 名標的
    colors = ['#ef5350' if x >= 0 else '#26a69a' for x in df_rank['PnL']]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=df_rank['Symbol'], x=df_rank['PnL'], orientation='h', marker_color=colors))
    fig.update_layout(title="標的損益排行榜 (前 10)", height=350)
    return fig

# ==========================================
# 2. 局部刷新元件 (Fragment)
# ==========================================

@st.fragment
def draw_strategy_section(df):
    st.subheader("1️⃣ 策略效能深度檢閱")
    all_strategies = sorted(df['Strategy'].unique().tolist())
    selected_strategies = st.multiselect("🎯 篩選策略:", options=all_strategies, default=all_strategies)
    
    if not selected_strategies:
        st.warning("⚠️ 請至少勾選一個策略")
        return

    df_filtered = df[df['Strategy'].isin(selected_strategies)]
    c1, c2, c3 = st.columns(3)
    with c1: st.plotly_chart(plot_strategy_performance(df_filtered), use_container_width=True)
    with c2: st.plotly_chart(plot_cumulative_pnl_by_strategy(df_filtered), use_container_width=True)
    with c3: st.plotly_chart(plot_strategy_quality_bubble(df_filtered), use_container_width=True)

# ==========================================
# 3. 主入口 (對齊 app.py)
# ==========================================

def display_advanced_analysis(xls):
    st.markdown("### 🔍 交易細項深度分析")
    df, err = get_advanced_data(xls)
    
    if err:
        st.warning(f"⚠️ 無法進行分析: {err}"); return
    if df.empty:
        st.info("目前沒有交易資料。"); return

    st.markdown("---")
    draw_strategy_section(df)
    st.markdown("---")

    st.subheader("2️⃣ 整體損益分佈結構")
    wins = df[df['PnL'] > 0]['PnL']
    losses = df[df['PnL'] < 0]['PnL']
    
    m1, m2, m3 = st.columns(3)
    m1.metric("常態獲利 (中位數)", f"${wins.median():,.0f}")
    m2.metric("常態虧損 (中位數)", f"${losses.median():,.0f}")
    m3.metric("樣本總數", f"{len(df)} 筆")

    d1, d2 = st.columns(2)
    with d1: st.plotly_chart(plot_pnl_distribution(df), use_container_width=True)
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
