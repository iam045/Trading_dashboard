import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import load_google_sheet 

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
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        # ⚠️ 欄位對應: 0=Date, 1=Strategy, 2=Symbol, 10=Risk, 11=PnL
        needed_cols = [0, 1, 2, 10, 11] 
        
        if df.shape[1] < max(needed_cols): 
            return None, "表格欄位不足，請檢查 logic_advanced.py 中的欄位索引"

        df_clean = df.iloc[:, needed_cols].copy()
        df_clean.columns = ['Date', 'Strategy', 'Symbol', 'Risk_Amount', 'PnL']

        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        df_clean['PnL'] = pd.to_numeric(df_clean['PnL'].astype(str).str.replace(',', ''), errors='coerce')
        
        # 1. 去除無效資料
        df_clean = df_clean.dropna(subset=['Date', 'PnL'])
        
        # 2. 排除損益為 0 的交易 (避免平盤單拉低勝率)
        df_clean = df_clean[df_clean['PnL'] != 0]
        
        # 增加輔助欄位
        df_clean['Weekday'] = df_clean['Date'].dt.day_name()
        
        return df_clean, None

    except Exception as e:
        return None, f"讀取失敗: {e}"

# ==========================================
# 1. 繪圖函式組
# ==========================================

def plot_strategy_performance(df):
    """圖1: 總損益 Bar Chart"""
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
        title="各策略總損益與勝率排名",
        yaxis=dict(title="總損益 ($)"),
        yaxis2=dict(title="勝率 (%)", overlaying='y', side='right', tickformat='.0%'),
        showlegend=True,
        height=350, 
        margin=dict(t=40, b=40)
    )
    return fig

def plot_cumulative_pnl_by_strategy(df):
    """圖2: 權益曲線 Line Chart"""
    df_sorted = df.sort_values('Date')
    df_sorted['CumPnL'] = df_sorted.groupby('Strategy')['PnL'].cumsum()
    
    fig = px.line(
        df_sorted, 
        x='Date', 
        y='CumPnL', 
        color='Strategy',
        title="各策略權益曲線 (穩定性檢測)",
        markers=False
    )
    fig.update_layout(
        height=350,
        hovermode="x unified",
        margin=dict(t=40, b=40)
    )
    return fig

def plot_strategy_quality_bubble(df):
    """[NEW] 圖3: 策略品質矩陣 (氣泡圖) - 勝率 vs 盈虧比"""
    # 計算進階指標
    stats = df.groupby('Strategy').apply(lambda x: pd.Series({
        'Win_Rate': (x['PnL'] > 0).mean(),
        'Avg_Win': x[x['PnL'] > 0]['PnL'].mean() if not x[x['PnL'] > 0].empty else 0,
        'Avg_Loss': abs(x[x['PnL'] < 0]['PnL'].mean()) if not x[x['PnL'] < 0].empty else 0,
        'Total_PnL': x['PnL'].sum(),
        'Count': len(x)
    })).reset_index()

    # 計算盈虧比 (避免除以0)
    stats['Payoff_Ratio'] = stats.apply(lambda row: row['Avg_Win'] / row['Avg_Loss'] if row['Avg_Loss'] > 0 else 0, axis=1)
    
    # 處理氣泡大小 (用絕對值，避免虧損策略氣泡變成負的無法顯示，但用顏色區分賺賠)
    stats['Bubble_Size'] = stats['Total_PnL'].abs()
    
    fig = px.scatter(
        stats,
        x="Win_Rate",
        y="Payoff_Ratio",
        size="Bubble_Size",
        color="Total_PnL", # 顏色代表賺賠
        hover_name="Strategy",
        hover_data={"Bubble_Size": False, "Total_PnL": ":,.0f", "Count": True},
        color_continuous_scale=["#26a69a", "#eeeeee", "#ef5350"], # 綠->白->紅
        title="策略品質矩陣 (氣泡大小 = 總損益規模)"
    )
    
    # 加上十字線 (勝率50%, 盈虧比1:1) 作為及格線
    fig.add_hline(y=1, line_dash="dash", line_color="gray", annotation_text="盈虧比 1:1")
    fig.add_vline(x=0.5, line_dash="dash", line_color="gray", annotation_text="勝率 50%")

    fig.update_layout(
        xaxis_title="勝率 (Win Rate)",
        yaxis_title="盈虧比 (Payoff Ratio)",
        xaxis_tickformat='.0%',
        height=400
    )
    return fig

def plot_weekday_box_analysis(df):
    """[NEW] 圖4: 週一~週五 損益分佈 (箱型圖)"""
    cats = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    df['Weekday'] = pd.Categorical(df['Weekday'], categories=cats, ordered=True)
    df_sorted = df.sort_values('Weekday')

    fig = go.Figure()
    
    # 這裡我們不只看總和，而是看每一筆交易的分佈
    fig.add_trace(go.Box(
        x=df_sorted['Weekday'],
        y=df_sorted['PnL'],
        boxpoints='all', # 顯示所有散點
        jitter=0.3,      # 散點寬度
        pointpos=-1.8,   # 散點位置
        marker=dict(color='#5c6bc0', size=2),
        line=dict(color='#333'),
        fillcolor='rgba(255,255,255,0)', # 透明箱體
        name='交易分佈'
    ))

    fig.update_layout(
        title="週一至週五：損益分佈 (Box Plot)",
        yaxis_title="單筆損益 ($)",
        height=350,
        showlegend=False,
        margin=dict(t=40, b=40)
    )
    return fig

def plot_weekday_bar_analysis(df):
    """圖5: 原本的週一~週五 勝率 (Bar)"""
    cats = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    df['Weekday'] = pd.Categorical(df['Weekday'], categories=cats, ordered=True)
    
    weekday_stats = df.groupby('Weekday', observed=True).agg(
        Win_Rate=('PnL', lambda x: (x > 0).mean())
    ).reset_index()
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=weekday_stats['Weekday'], 
        y=weekday_stats['Win_Rate'],
        marker_color='#5c6bc0',
        text=weekday_stats['Win_Rate'].apply(lambda x: f"{x:.1%}")
    ))
    fig.update_layout(title="週一至週五：勝率表現", height=350, yaxis_tickformat='.0%')
    return fig

def plot_symbol_ranking(df):
    """圖6: 標的賺賠排名"""
    symbol_stats = df.groupby('Symbol')['PnL'].sum().reset_index()
    symbol_stats = symbol_stats.sort_values('PnL', ascending=True)
    
    if len(symbol_stats) > 10:
        top_5_losers = symbol_stats.head(5)
        top_5_winners = symbol_stats.tail(5)
        df_rank = pd.concat([top_5_losers, top_5_winners])
    else:
        df_rank = symbol_stats

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
        height=350,
        margin=dict(l=100, t=40, b=40) 
    )
    return fig

# ==========================================
# 2. 局部刷新元件 (Fragment)
# ==========================================

@st.fragment
def draw_strategy_section(df):
    """策略分析區塊 (包含新舊圖表)"""
    st.subheader("1️⃣ 策略效能深度檢閱")
    
    all_strategies = sorted(df['Strategy'].unique().tolist())
    selected_strategies = st.multiselect(
        "🎯 篩選策略 (可多選):",
        options=all_strategies,
        default=all_strategies,
        placeholder="請選擇至少一個策略..."
    )
    
    if not selected_strategies:
        st.warning("⚠️ 請至少勾選一個策略以顯示數據")
        return

    df_filtered = df[df['Strategy'].isin(selected_strategies)]
    
    # 上排：基本表現
    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(plot_strategy_performance(df_filtered), use_container_width=True)
    with c2: st.plotly_chart(plot_cumulative_pnl_by_strategy(df_filtered), use_container_width=True)
    
    # 下排：[NEW] 品質矩陣 (這張圖一定要看！)
    st.plotly_chart(plot_strategy_quality_bubble(df_filtered), use_container_width=True)
    st.caption("💡 **如何解讀氣泡圖？** X軸越右邊勝率越高，Y軸越上面賺賠比越好。右上角是大賺區，右下角是薄利多銷區。氣泡越大代表總損益越多。")

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

    # --- Section 2: 週期分析 (加入箱型圖) ---
    st.subheader("2️⃣ 交易週期效應 (Day of Week)")
    st.caption("檢查「黑色星期X」魔咒：箱型圖可看出該日的波動範圍與極端值。")
    
    # 使用 [NEW] 箱型圖 + 原本的勝率圖
    fig_day_box = plot_weekday_box_analysis(df)
    fig_day_win = plot_weekday_bar_analysis(df)
    
    dc1, dc2 = st.columns(2)
    with dc1: st.plotly_chart(fig_day_box, use_container_width=True)
    with dc2: st.plotly_chart(fig_day_win, use_container_width=True)

    st.markdown("---")

    # --- Section 3: 標的分析 ---
    st.subheader("3️⃣ 標的 (Symbol) 損益風雲榜")
    st.caption("賺最多與賠最多的前 5 名標的。")
    
    st.plotly_chart(plot_symbol_ranking(df), use_container_width=True)
