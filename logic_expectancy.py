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
    # 建立累計 R 曲線
    y = df['R'].cumsum().values
    x = np.arange(len(y))
    
    # 簡單線性回歸計算相關係數
    if len(y) < 2: return 0
    correlation_matrix = np.corrcoef(x, y)
    correlation_xy = correlation_matrix[0, 1]
    r_squared = correlation_xy ** 2
    return r_squared

def calculate_kpis(df, capital, kelly_fraction):
    total_trades = len(df)
    if total_trades == 0: return None
    
    wins = df[df['PnL'] > 0]
    losses = df[df['PnL'] <= 0]
    
    # 1. 基礎數據
    gross_profit = wins['PnL'].sum()
    gross_loss = abs(losses['PnL'].sum())
    total_pnl = df['PnL'].sum()
    total_risk = df['Risk_Amount'].sum()
    
    # 2. 勝率 & 賺賠比
    win_rate = len(wins) / total_trades
    avg_win = wins['PnL'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['PnL'].mean()) if len(losses) > 0 else 0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    # 3. 期望值與因子
    expectancy_custom = total_pnl / total_risk if total_risk > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # 4. 凱利公式 (Kelly Criterion)
    # 完整凱利 % = W - (1-W)/R
    if payoff_ratio > 0:
        full_kelly = win_rate - (1 - win_rate) / payoff_ratio
    else:
        full_kelly = 0
    
    # 調整後凱利 (User 設定的比例，如 1/7)
    adj_kelly_pct = max(0, full_kelly * kelly_fraction) # 負數歸零
    kelly_suggested_risk = capital * adj_kelly_pct

    # 5. 進階數據 (連勝連敗、穩定度)
    max_win, max_loss = calculate_streaks(df)
    r_sq = calculate_r_squared(df)
    
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
        "Adj Kelly Pct": adj_kelly_pct,
        "Kelly Risk $": kelly_suggested_risk
    }

def display_expectancy_lab(xls):
    df, err = get_expectancy_data(xls)
    
    if err:
        st.warning(f"⚠️ {err}")
        return
    if df is None or df.empty:
        st.info("尚未有足夠的交易紀錄可供分析。")
        return

    # --- 用戶輸入區 ---
    with st.expander("⚙️ 參數設定 (凱利公式與本金)", expanded=False):
        c1, c2 = st.columns(2)
        capital = c1.number_input("目前本金 (NTD)", value=300000, step=10000)
        kelly_frac_input = c2.selectbox("凱利下注比例", 
                                  options=[1/1, 1/2, 1/4, 1/7, 1/10], 
                                  format_func=lambda x: "全凱利 (Full)" if x==1 else f"1/{int(1/x)} 凱利",
                                  index=3) # 預設選第4個 (1/7)

    kpi = calculate_kpis(df, capital, kelly_frac_input)
    
    # --- 儀表板顯示 ---
    st.markdown("### 🏥 系統體檢報告 (System Health)")
    
    # 第一排：核心生存指標
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    
    # 獲利因子
    pf = kpi['Profit Factor']
    pf_col = "normal"
    if pf < 1: pf_col = "inverse"
    k2.metric("獲利因子 (PF)", f"{pf:.2f}", delta="> 1.5 為佳", delta_color="off", help="總獲利 / 總虧損")

    # 期望值
    k3.metric("期望值 (Exp)", f"{kpi['Expectancy Custom']:.2f} R", help="總損益 / 含成本總風險")
    
    # 穩定度 (R-Squared)
    r2 = kpi['R Squared']
    r2_msg = "波動大"
    if r2 > 0.9: r2_msg = "極穩"; 
    elif r2 > 0.8: r2_msg = "平穩"
    k4.metric("曲線穩定度 (R²)", f"{r2:.2f}", delta=r2_msg, delta_color="off", help="越接近 1.0 代表獲利曲線越平滑穩定，非運氣致富。")

    # 第二排：結構與連鎖
    j1, j2, j3, j4 = st.columns(4)
    j1.metric("勝率 (Win Rate)", f"{kpi['Win Rate']*100:.1f}%")
    j2.metric("賺賠比 (Payoff)", f"{kpi['Payoff Ratio']:.2f}")
    j3.metric("最大連勝", f"{kpi['Max Win Streak']} 次", delta="High", delta_color="normal")
    j4.metric("最大連敗", f"{kpi['Max Loss Streak']} 次", delta="Risk", delta_color="inverse", help="歷史上最慘曾經連續輸幾次。")

    st.markdown("---")
    
    # 第三排：凱利公式建議 (重點區)
    st.markdown(f"#### 🎰 資金管理建議 (基於 {int(1/kelly_frac_input)} 分之一凱利)")
    if kpi['Full Kelly'] <= 0:
        st.error(f"❌ 警告：你的期望值為負，凱利公式建議 **停止交易** (建議倉位 0%)。")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("建議下注比例 (%)", f"{kpi['Adj Kelly Pct']*100:.2f}%", help=f"依據你的本金 {capital:,} 與勝率賠率計算")
        m2.metric("建議單筆風險金", f"${kpi['Kelly Risk $']:,.0f}", delta="Risk Size", help="這是你下一筆交易應該冒的風險金額")
        m3.caption(f"💡 這是基於本金 **${capital:,}** 計算的結果。\n若你目前單筆風險遠大於此，請考慮縮小部位。")

    st.markdown("---")

    # --- 圖表區 ---
    t1, t2 = st.tabs(["📈 權益曲線 (R)", "📊 策略競技場"])
    
    with t1:
        df['Cumulative R'] = df['R'].cumsum()
        fig_r = go.Figure()
        fig_r.add_trace(go.Scatter(
            x=df['Date'], y=df['Cumulative R'],
            mode='lines+markers', name='累計 R',
            line=dict(color='#1f77b4', width=2),
            fill='tozeroy', fillcolor='rgba(31, 119, 180, 0.1)'
        ))
        
        # 加上趨勢線 (視覺化 R^2)
        x_nums = np.arange(len(df))
        if len(x_nums) > 1:
            z = np.polyfit(x_nums, df['Cumulative R'], 1)
            p = np.poly1d(z)
            fig_r.add_trace(go.Scatter(x=df['Date'], y=p(x_nums), mode='lines', name='趨勢線', line=dict(color='gray', dash='dash', width=1)))

        fig_r.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            xaxis_title="", yaxis_title="累計 R",
            height=400, hovermode="x unified", showlegend=False
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
