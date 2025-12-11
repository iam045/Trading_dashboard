import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

def clean_numeric(series):
    """清洗數字格式 (移除逗號、轉型)"""
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

def get_expectancy_data(xls):
    """
    讀取並清洗期望值資料
    標題列在 Index 14 (第15列)
    """
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet:
        return None, "找不到含有 '期望值' 的分頁"

    try:
        # 讀取資料
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        # 欄位選取：
        # 日期(0), 策略(1), 風險金額(8), 損益(11), R(13)
        if df.shape[1] < 14:
            return None, "表格欄位不足 14 欄，請檢查格式。"

        # 選取這 5 個關鍵欄位
        df_clean = df.iloc[:, [0, 1, 8, 11, 13]].copy()
        df_clean.columns = ['Date', 'Strategy', 'Risk_Amount', 'PnL', 'R']

        df_clean = df_clean.dropna(subset=['Date']) 
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        
        # 數字轉型
        for col in ['Risk_Amount', 'PnL', 'R']:
            df_clean[col] = clean_numeric(df_clean[col])
        
        # 移除無效交易 (損益或風險是空的)
        df_clean = df_clean.dropna(subset=['PnL', 'Risk_Amount'])
        
        # 確保風險金額是正數 (避免分母為負導致計算錯誤)
        df_clean['Risk_Amount'] = df_clean['Risk_Amount'].abs()
        
        # 移除風險為 0 的資料 (避免除以零)
        df_clean = df_clean[df_clean['Risk_Amount'] > 0]

        return df_clean.sort_values('Date'), None

    except Exception as e:
        return None, f"讀取失敗: {e}"

def calculate_kpis(df):
    """
    計算黃金 5 指標 (依據用戶要求修正 Expectancy 算法)
    """
    total_trades = len(df)
    if total_trades == 0: return None
    
    wins = df[df['PnL'] > 0]
    losses = df[df['PnL'] <= 0]
    
    # 1. 基礎數據
    gross_profit = wins['PnL'].sum()
    gross_loss = abs(losses['PnL'].sum())
    total_pnl = df['PnL'].sum()
    
    # --- 🔥 關鍵修正：改用 (總損益 / 總風險) ---
    total_risk = df['Risk_Amount'].sum()
    expectancy_custom = total_pnl / total_risk if total_risk > 0 else 0
    
    # 2. 勝率
    win_rate = len(wins) / total_trades
    
    # 3. 賺賠比
    avg_win = wins['PnL'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['PnL'].mean()) if len(losses) > 0 else 0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    # 4. Profit Factor (獲利因子)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # 5. SQN (系統品質) - 分子改用精確期望值
    # SQN = sqrt(N) * (Expectancy / StdDev of R)
    r_std = df['R'].std()
    sqn = (expectancy_custom / r_std * np.sqrt(total_trades)) if r_std > 0 else 0
    
    return {
        "Total Trades": total_trades,
        "Total PnL": total_pnl,
        "Total Risk": total_risk,
        "Win Rate": win_rate,
        "Payoff Ratio": payoff_ratio,
        "Expectancy Custom": expectancy_custom, # 你的客製化指標
        "Profit Factor": profit_factor,
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
    
    # --- 儀表板顯示 ---
    st.markdown("### 🏥 系統體檢報告 (System Health)")
    
    # 第一排
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    k1.metric("總損益 (Net PnL)", f"${kpi['Total PnL']:,.0f}")
    
    # SQN
    sqn = kpi['SQN']
    sqn_color = "normal"
    sqn_msg = "普通"
    if sqn < 1.6: sqn_msg = "弱"; sqn_color="off"
    elif 1.6 <= sqn < 2.0: sqn_msg = "及格"; sqn_color="normal"
    elif 2.0 <= sqn < 3.0: sqn_msg = "優秀"; sqn_color="inverse"
    elif sqn >= 3.0: sqn_msg = "聖杯"; sqn_color="inverse"
    k2.metric("SQN 系統品質", f"{sqn:.2f}", delta=sqn_msg, delta_color=sqn_color)
    
    # 獲利因子
    pf = kpi['Profit Factor']
    pf_color = "normal"
    if pf < 1: pf_color = "inverse" 
    k2.metric("獲利因子 (PF)", f"{pf:.2f}", delta="> 1.5 為佳", delta_color="off")

    # 第二排
    # 🔥 這裡顯示的是你指定的算法
    k3.metric("期望值 (Exp R)", f"{kpi['Expectancy Custom']:.2f} R", help=f"算法：總損益 ${kpi['Total PnL']:,.0f} / 總風險 ${kpi['Total Risk']:,.0f}")
    k3.metric("勝率 (Win Rate)", f"{kpi['Win Rate']*100:.1f}%")
    k4.metric("賺賠比 (Payoff)", f"{kpi['Payoff Ratio']:.2f}")

    st.markdown("---")

    # --- 圖表區 ---
    t1, t2 = st.tabs(["📈 權益曲線 (R)", "📊 策略競技場"])
    
    with t1:
        # 這裡的曲線依然使用單筆 R 的累加，因為這能反映「波段走勢」
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
                Avg_R=('R', 'mean'), # 這裡保留平均 R 供參考，或也可以改成 Sum_PnL / Sum_Risk
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
