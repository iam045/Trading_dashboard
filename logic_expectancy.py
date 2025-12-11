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

def calculate_kpis(df):
    total_trades = len(df)
    if total_trades == 0: return None
    
    wins = df[df['PnL'] > 0]
    losses = df[df['PnL'] <= 0]
    
    gross_profit = wins['PnL'].sum()
    gross_loss = abs(losses['PnL'].sum())
    total_pnl = df['PnL'].sum()
    total_risk = df['Risk_Amount'].sum()
    
    # 核心指標計算
    win_rate = len(wins) / total_trades
    
    avg_win = wins['PnL'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['PnL'].mean()) if len(losses) > 0 else 0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    expectancy_custom = total_pnl / total_risk if total_risk > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    return {
        "Total Trades": total_trades,
        "Total PnL": total_pnl,
        "Total Risk": total_risk,
        "Win Rate": win_rate,
        "Payoff Ratio": payoff_ratio,
        "Expectancy Custom": expectancy_custom,
        "Profit Factor": profit_factor
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
    
    # --- 儀表板顯示 ---
    st.markdown("### 🏥 系統體檢報告 (System Health)")
    
    # 第一排：核心數據
    k1, k2, k3, k4 = st.columns(4)
    
    k1.metric("總交易次數", f"{kpi['Total Trades']} 筆", 
              help="統計期間內的有效交易總筆數。")
    
    k2.metric("總損益 (Net PnL)", f"${kpi['Total PnL']:,.0f}", 
              help="所有交易的淨損益加總。")
    
    # 獲利因子 (PF)
    pf = kpi['Profit Factor']
    pf_color = "normal"
    if pf < 1: pf_color = "inverse" 
    k3.metric("獲利因子 (PF)", f"{pf:.2f}", delta="> 1.5 為佳", delta_color="off",
              help="定義：總獲利金額 / 總虧損金額。\n意義：衡量生意的划算程度，大於 1 代表賺錢，大於 1.5 代表系統穩健。")

    # 期望值 (往前移)
    k4.metric("期望值 (Exp)", f"{kpi['Expectancy Custom']:.2f} R", 
              help=f"定義：總損益 / 總風險(含成本)。\n意義：代表你每投入 1 塊錢風險，平均能帶回多少淨利。\n(數值越高，代表資金運用效率越好)")

    # 第二排：系統結構
    j1, j2, j3, j4 = st.columns(4)
    
    j1.metric("勝率 (Win Rate)", f"{kpi['Win Rate']*100:.1f}%",
              help="定義：賺錢筆數 / 總筆數。\n意義：代表出手的準確度。")
    
    j2.metric("賺賠比 (Payoff)", f"{kpi['Payoff Ratio']:.2f}",
              help="定義：平均獲利金額 / 平均虧損金額。\n意義：代表贏一次的錢，夠你輸幾次。")
    
    # 這裡留空或未來放其他指標
    j3.write("") 
    j4.write("")

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
