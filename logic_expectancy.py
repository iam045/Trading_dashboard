import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

def clean_numeric(series):
    """清洗數字格式 (移除逗號、轉型)"""
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

def get_expectancy_data(xls):
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet:
        return None, "找不到含有 '期望值' 的分頁"

    try:
        # 讀取資料 (標題在第15列 -> header=14)
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        if df.shape[1] < 14:
            return None, "表格欄位不足 14 欄，請檢查格式。"

        # 欄位選取：日期(0), 策略(1), 最後總風險(10), 損益(11), R(13)
        df_clean = df.iloc[:, [0, 1, 10, 11, 13]].copy()
        df_clean.columns = ['Date', 'Strategy', 'Risk_Amount', 'PnL', 'R']

        df_clean = df_clean.dropna(subset=['Date']) 
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        
        for col in ['Risk_Amount', 'PnL', 'R']:
            df_clean[col] = clean_numeric(df_clean[col])
        
        df_clean = df_clean.dropna(subset=['PnL', 'Risk_Amount'])
        df_clean['Risk_Amount'] = df_clean['Risk_Amount'].abs()
        df_clean = df_clean[df_clean['Risk_Amount'] > 0]

        return df_clean.sort_values('Date'), None

    except Exception as e:
        return None, f"讀取失敗: {e}"

def calculate_streaks(df):
    """計算最大連勝與連敗"""
    pnl = df['PnL'].values
    max_win_streak = 0
    max_loss_streak = 0
    curr_win = 0
    curr_loss = 0
    
    for val in pnl:
        if val > 0:
            curr_win += 1
            curr_loss = 0
            if curr_win > max_win_streak: max_win_streak = curr_win
        elif val <= 0:
            curr_loss += 1
            curr_win = 0
            if curr_loss > max_loss_streak: max_loss_streak = curr_loss
            
    return max_win_streak, max_loss_streak

def calculate_r_squared(df):
    """計算權益曲線的平滑度 (R-Squared)"""
    y = df['R'].cumsum().values
    x = np.arange(len(y))
    if len(y) < 2: return 0
    correlation_matrix = np.corrcoef(x, y)
    correlation_xy = correlation_matrix[0, 1]
    r_squared = correlation_xy ** 2
    return r_squared

def calculate_kpis(df):
    total_trades = len(df)
    if total_trades == 0: return None
    
    wins = df[df['PnL'] > 0]
    losses = df[df['PnL'] <= 0]
    
    gross_profit = wins['PnL'].sum()
    gross_loss = abs(losses['PnL'].sum())
    total_pnl = df['PnL'].sum()
    total_risk = df['Risk_Amount'].sum()
    
    win_rate = len(wins) / total_trades
    avg_win = wins['PnL'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['PnL'].mean()) if len(losses) > 0 else 0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    expectancy_custom = total_pnl / total_risk if total_risk > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # 凱利公式基礎值 (Full Kelly %)
    if payoff_ratio > 0:
        full_kelly = win_rate - (1 - win_rate) / payoff_ratio
    else:
        full_kelly = 0
        
    # 進階數據
    max_win, max_loss = calculate_streaks(df)
    r_sq = calculate_r_squared(df)
    
    # SQN
    r_std = df['R'].std()
    sqn = (expectancy_custom / r_std * np.sqrt(total_trades)) if r_std > 0 else 0
    
    return {
        "Total Trades": total_trades,
        "Total PnL": total_pnl,
        "Win Rate": win_rate,
        "Payoff Ratio": payoff_ratio,
        "Expectancy Custom": expectancy_custom,
        "Profit Factor": profit_factor,
        "Max Win Streak": max_win,
        "Max Loss Streak": max_loss,
        "R Squared": r_sq,
        "Full Kelly": full_kelly,
        "SQN": sqn
    }

def display_expectancy_lab(xls):
    df, err = get_expectancy_data(xls)
    
    if err:
        st.warning(f"⚠️ {err}")
        return
    if df is None or df.empty:
        st.info("尚未有足夠的交易紀錄可供分析。")
        return

    kpi = calculate_kpis(df)
    
    # --- 1. 系統體檢報告 (依照要求排序) ---
    st.markdown("### 🏥 系統體檢報告 (System Health)")
    
    # 第一排：戰績與連續紀錄
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    r1c1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    r1c2.metric("勝率 (Win Rate)", f"{kpi['Win Rate']*100:.1f}%")
    r1c3.metric("最大連勝", f"{kpi['Max Win Streak']} 次", delta="🔥 High", delta_color="normal")
    r1c4.metric("最大連敗", f"{kpi['Max Loss Streak']} 次", delta="❄️ Risk", delta_color="inverse")
    
    # 第二排：損益與期望值核心
    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
    r2c1.metric("總損益 (Net PnL)", f"${kpi['Total PnL']:,.0f}")
    r2c2.metric("期望值 (Exp R)", f"{kpi['Expectancy Custom']:.2f} R", help="總損益 / 含成本總風險")
    r2c3.metric("盈虧比 (Payoff)", f"{kpi['Payoff Ratio']:.2f}")
    
    # 獲利因子
    pf = kpi['Profit Factor']
    pf_col = "normal" if pf >= 1 else "inverse"
    r2c4.metric("獲利因子 (PF)", f"{pf:.2f}", delta="> 1.5 佳", delta_color="off")
    
    # 曲線穩定度 (R^2)
    r2 = kpi['R Squared']
    r2_color = "normal" if r2 > 0.8 else "off"
    r2c5.metric("曲線穩定度 (R²)", f"{r2:.2f}", delta="越近 1 越穩", delta_color="off")

    st.markdown("---")
    
    # --- 2. 資金管理控制台 (凱利公式 - 合併版) ---
    st.markdown("#### 🎰 資金管理控制台 (Kelly Strategy)")
    
    # 建立一個像控制面板的佈局
    with st.container():
        # 用 columns 來並排 "輸入" 與 "結果"
        c_input1, c_input2, c_arrow, c_res1, c_res2 = st.columns([1.2, 1.2, 0.2, 1.2, 1.5])
        
        with c_input1:
            capital = st.number_input("目前本金 (NTD)", value=300000, step=10000)
        
        with c_input2:
            kelly_frac_input = st.selectbox("凱利倍數", 
                                  options=[1/1, 1/2, 1/4, 1/7, 1/10], 
                                  format_func=lambda x: "全凱利 (Full)" if x==1 else f"1/{int(1/x)} 凱利",
                                  index=3) # 預設 1/7

        # 中間放個箭頭或分隔，視覺上引導
        with c_arrow:
            st.markdown("<h3 style='text-align: center; color: gray;'>👉</h3>", unsafe_allow_html=True)

        # 計算結果
        adj_kelly_pct = max(0, kpi['Full Kelly'] * kelly_frac_input)
        kelly_risk_money = capital * adj_kelly_pct

        with c_res1:
            st.metric("建議倉位 %", f"{adj_kelly_pct*100:.2f}%")
        
        with c_res2:
            st.metric("建議單筆風險金", f"${kelly_risk_money:,.0f}", delta="Risk Size")

    if kpi['Full Kelly'] <= 0:
        st.error("❌ 警報：系統期望值為負，凱利公式建議 **停止交易 (0%)**。")

    st.markdown("---")

    # --- 3. 圖表區 ---
    t1, t2 = st.tabs(["📈 權益曲線 (R) & 穩定度", "📊 策略競技場"])
    
    with t1:
        df['Cumulative R'] = df['R'].cumsum()
        fig_r = go.Figure()
        
        # 1. 實際曲線
        fig_r.add_trace(go.Scatter(
            x=df['Date'], y=df['Cumulative R'],
            mode='lines+markers', name='累計 R',
            line=dict(color='#1f77b4', width=2),
            fill='tozeroy', fillcolor='rgba(31, 119, 180, 0.1)'
        ))
        
        # 2. 趨勢線 (明顯化：紅色虛線)
        x_nums = np.arange(len(df))
        if len(x_nums) > 1:
            z = np.polyfit(x_nums, df['Cumulative R'], 1)
            p = np.poly1d(z)
            trend_line = p(x_nums)
            fig_r.add_trace(go.Scatter(
                x=df['Date'], y=trend_line, 
                mode='lines', name='理想趨勢', 
                line=dict(color='red', dash='dash', width=2)
            ))
            
            # 3. 直接在圖上標註 R平方
            mid_idx = len(df) // 2
            mid_date = df['Date'].iloc[mid_idx]
            max_r = df['Cumulative R'].max()
            
            fig_r.add_annotation(
                x=mid_date, y=max_r,
                text=f"R² (穩定度) = {kpi['R Squared']:.2f}",
                showarrow=False,
                yshift=10,
                font=dict(size=14, color="red"),
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="red"
            )

        fig_r.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            xaxis_title="", yaxis_title="累計 R",
            height=400, hovermode="x unified", showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_r, use_container_width=True)

    with t2:
        if 'Strategy' in df.columns and df['Strategy'].nunique() > 0:
            strat_group = df.groupby('Strategy').agg(
                Count=('R', 'count'),
                Sum_R=('R', 'sum'),
                Avg_R=('R', 'mean'), 
                Win_Rate=('PnL', lambda x: (x>0).sum() / len(x))
            ).sort_values('Sum_R', ascending=False)
            
            strat_group['Win_Rate'] = strat_group['Win_Rate'].apply(lambda x: f"{x:.1%}")
            strat_group['Avg_R'] = strat_group['Avg_R'].apply(lambda x: f"{x:.2f}")
            strat_group['Sum_R'] = strat_group['Sum_R'].apply(lambda x: f"{x:.2f}")
            
            st.dataframe(strat_group, use_container_width=True)
            
            fig_strat = px.bar(strat_group, x=strat_group.index, y='Sum_R', 
                               title="各策略貢獻度 (Total R)", text='Sum_R')
            fig_strat.update_layout(margin=dict(t=30, b=10, l=10, r=10))
            st.plotly_chart(fig_strat, use_container_width=True)
        else:
            st.info("無法識別策略名稱。")
