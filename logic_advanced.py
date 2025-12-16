import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import load_google_sheet 

# ==========================================
# 0. 資料處理核心
# ==========================================

def get_advanced_data(xls):
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到 '期望值' 分頁"
    
    try:
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        needed_cols = [0, 1, 2, 10, 11, 13] 
        
        if df.shape[1] < max(needed_cols): 
            return None, "表格欄位不足"

        df_clean = df.iloc[:, needed_cols].copy()
        df_clean.columns = ['Date', 'Strategy', 'Symbol', 'Risk_Amount', 'PnL', 'R']

        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        df_clean['PnL'] = pd.to_numeric(df_clean['PnL'].astype(str).str.replace(',', ''), errors='coerce')
        df_clean['R'] = pd.to_numeric(df_clean['R'].astype(str).str.replace(',', ''), errors='coerce')
        
        df_clean = df_clean.dropna(subset=['Date', 'PnL'])
        df_clean = df_clean[df_clean['PnL'] != 0] # 排除平盤
        
        df_clean['Weekday'] = df_clean['Date'].dt.day_name()
        
        return df_clean, None

    except Exception as e:
        return None, f"讀取失敗: {e}"

# ==========================================
# 1. 繪圖函式組
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
    stats = df.groupby('Strategy').apply(lambda x: pd.Series({
        'Win_Rate': (x['PnL'] > 0).mean(),
        'Avg_Win_R': x[x['R'] > 0]['R'].mean() if not x[x['R'] > 0].empty else 0,
        'Avg_Loss_R': abs(x[x['R'] <= 0]['R'].mean()) if not x[x['R'] <= 0].empty else 0,
        'Total_PnL': x['PnL'].sum(),
        'Count': len(x)
    })).reset_index()

    stats['Payoff_Ratio_R'] = stats.apply(lambda row: row['Avg_Win_R'] / row['Avg_Loss_R'] if row['Avg_Loss_R'] > 0 else 0, axis=1)
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

# --- 整體分佈分析圖表 ---

def plot_pnl_distribution(df):
    fig = go.Figure()
    
    wins = df[df['PnL'] > 0]['PnL']
    fig.add_trace(go.Histogram(
        x=wins,
        name='獲利',
        marker_color='#ef5350',
        opacity=0.75,
        nbinsx=40 
    ))
    
    losses = df[df['PnL'] < 0]['PnL']
    fig.add_trace(go.Histogram(
        x=losses,
        name='虧損',
        marker_color='#26a69a',
        opacity=0.75,
        nbinsx=40
    ))

    fig.update_layout(
        title="損益金額頻率分佈 (Histogram)",
        xaxis_title="損益金額 ($)",
        yaxis_title="出現次數 (頻率)",
        barmode='overlay', 
        height=350,
        margin=dict(t=40, b=20, l=40, r=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def plot_win_loss_box(df):
    fig = go.Figure()
    
    # 獲利箱
    fig.add_trace(go.Box(
        y=df[df['PnL'] > 0]['PnL'],
        name='獲利規模',
        marker_color='#ef5350',
        boxpoints='all', 
        jitter=0.3,
        pointpos=-1.8
    ))
    
    # 虧損箱
    fig.add_trace(go.Box(
        y=df[df['PnL'] < 0]['PnL'],
        name='虧損規模',
        marker_color='#26a69a',
        boxpoints='all',
        jitter=0.3,
        pointpos=-1.8
    ))

    fig.update_layout(
        title="賺賠規模對比 (Box Plot)", 
        yaxis_title="損益金額 ($)",
        height=350,
        margin=dict(t=40, b=20, l=40, r=40),
        showlegend=False
    )
    return fig

def plot_weekday_analysis(df):
    cats = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    df['Weekday'] = pd.Categorical(df['Weekday'], categories=cats, ordered=True)
    
    # [UPDATED] 這裡修改為「以日為單位」計算勝率
    # 1. 先將數據聚合為「每日損益」
    daily_df = df.groupby(['Date', 'Weekday'], observed=True)['PnL'].sum().reset_index()
    
    # 2. 再針對每日損益進行統計
    weekday_stats = daily_df.groupby('Weekday', observed=True).agg(
        Total_PnL=('PnL', 'sum'),                     # 總損益不變 (所有單加總 = 所有日加總)
        Win_Rate=('PnL', lambda x: (x > 0).mean())    # 勝率變為 (獲利日數 / 總日數)
    ).reset_index()
    
    fig1 = go.Figure()
    colors1 = ['#ef5350' if x >= 0 else '#26a69a' for x in weekday_stats['Total_PnL']]
    fig1.add_trace(go.Bar(x=weekday_stats['Weekday'], y=weekday_stats['Total_PnL'], marker_color=colors1, text=weekday_stats['Total_PnL'].apply(lambda x: f"${x:,.0f}")))
    fig1.update_layout(title="週一至週五：總損益表現", height=350)
    
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=weekday_stats['Weekday'], y=weekday_stats['Win_Rate'], marker_color='#5c6bc0', text=weekday_stats['Win_Rate'].apply(lambda x: f"{x:.1%}")))
    fig2.update_layout(title="週一至週五：勝率表現 (以日計算)", height=350, yaxis_tickformat='.0%')
    return fig1, fig2

def plot_symbol_ranking(df):
    symbol_stats = df.groupby('Symbol')['PnL'].sum().reset_index().sort_values('PnL', ascending=True)
    if len(symbol_stats) > 10: df_rank = pd.concat([symbol_stats.head(5), symbol_stats.tail(5)])
    else: df_rank = symbol_stats
    colors = ['#ef5350' if x >= 0 else '#26a69a' for x in df_rank['PnL']]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=df_rank['Symbol'], x=df_rank['PnL'], orientation='h', marker_color=colors, text=df_rank['PnL'].apply(lambda x: f"${x:,.0f}"), textposition='outside'))
    fig.update_layout(title="標的損益排行榜", xaxis_title="總損益 ($)", height=350, margin=dict(l=100, t=40, b=40))
    return fig

# ==========================================
# 2. 局部刷新元件 (Fragment)
# ==========================================

@st.fragment
def draw_strategy_section(df):
    st.subheader("1️⃣ 策略效能深度檢閱")
    
    all_strategies = sorted(df['Strategy'].unique().tolist())
    selected_strategies = st.multiselect(
        "🎯 篩選策略 (僅影響本區塊圖表):",
        options=all_strategies,
        default=all_strategies,
        placeholder="請選擇至少一個策略..."
    )
    
    if not selected_strategies:
        st.warning("⚠️ 請至少勾選一個策略以顯示數據")
        return

    df_filtered = df[df['Strategy'].isin(selected_strategies)]
    
    c1, c2, c3 = st.columns(3)
    with c1: st.plotly_chart(plot_strategy_performance(df_filtered), use_container_width=True)
    with c2: st.plotly_chart(plot_cumulative_pnl_by_strategy(df_filtered), use_container_width=True)
    with c3:
        st.plotly_chart(plot_strategy_quality_bubble(df_filtered), use_container_width=True)
        st.markdown("<p style='font-size: 12px; color: #666; text-align: center; margin-top: -10px;'>💡 氣泡大小 = 總損益規模</p>", unsafe_allow_html=True)

# ==========================================
# 3. 主入口
# ==========================================

def display_advanced_analysis(xls):
    st.markdown("### 🔍 交易細項深度分析")
    st.caption("挖掘數據背後的行為模式：策略穩定性、時間週期效應、以及選股能力。")
    
    df, err = get_advanced_data(xls)
    if err:
        st.warning(f"⚠️ 無法進行分析: {err}")
        return
        
    if df.empty:
        st.info("目前沒有足夠的交易資料可供分析 (需排除損益為0的紀錄)。")
        return

    st.markdown("---")

    # --- Section 1: 策略分析 (Fragment) ---
    draw_strategy_section(df)

    st.markdown("---")

    # --- Section 2: 整體損益分佈結構 ---
    st.subheader("2️⃣ 整體損益分佈結構")
    
    wins = df[df['PnL'] > 0]['PnL']
    losses = df[df['PnL'] < 0]['PnL']
    
    median_win = wins.median() if not wins.empty else 0
    median_loss = losses.median() if not losses.empty else 0
    median_ratio = abs(median_win / median_loss) if median_loss != 0 else 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("常態獲利 (中位數)", f"${median_win:,.0f}", help="代表您 50% 的獲利單都大於此金額，這是您最典型的獲利水準。")
    m2.metric("常態虧損 (中位數)", f"${median_loss:,.0f}", help="代表您 50% 的虧損單都小於此金額，這是您最典型的虧損水準。")
    m3.metric("常態盈虧比", f"{median_ratio:.2f}", help="常態獲利 / 常態虧損。如果 > 1.5 代表結構很棒。")
    
    st.write("")

    d1, d2 = st.columns(2)
    with d1: 
        st.plotly_chart(plot_pnl_distribution(df), use_container_width=True)
        st.caption("👈 **直方圖**：看最高的柱子在哪，那就是您最常出現的損益金額。")
    with d2: 
        st.plotly_chart(plot_win_loss_box(df), use_container_width=True)
        st.caption("👈 **箱型圖**：箱子中間的線就是上方的「中位數」。")

    st.markdown("---")

    # --- Section 3: 週期分析 ---
    st.subheader("3️⃣ 交易週期效應 (Day of Week)")
    fig_day_pnl, fig_day_win = plot_weekday_analysis(df)
    
    dc1, dc2 = st.columns(2)
    with dc1: st.plotly_chart(fig_day_pnl, use_container_width=True)
    with dc2: st.plotly_chart(fig_day_win, use_container_width=True)

    st.markdown("---")

    # --- Section 4: 標的分析 ---
    st.subheader("4️⃣ 標的 (Symbol) 損益風雲榜")
    st.plotly_chart(plot_symbol_ranking(df), use_container_width=True)
