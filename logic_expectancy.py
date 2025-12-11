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
    # 1. 搜尋分頁
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet:
        return None, "找不到含有 '期望值' 的分頁"

    try:
        # 2. 讀取資料 (從第 14 列開始當標題)
        # 根據你的描述：日期(0), 策略(1), 損益(11), R(13)
        # 我們把整張表讀進來，再選取需要的欄位
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        # 3. 欄位對應 (依據你提供的 Index)
        # 為了保險，我們使用 iloc (位置) 來選取，而不是依賴欄位名稱 (怕有空格或微小差異)
        # 確保資料夠寬
        if df.shape[1] < 14:
            return None, "表格欄位不足 14 欄，請檢查格式。"

        # 提取關鍵欄位
        df_clean = df.iloc[:, [0, 1, 11, 13]].copy()
        df_clean.columns = ['Date', 'Strategy', 'PnL', 'R']

        # 4. 資料清洗
        df_clean = df_clean.dropna(subset=['Date']) # 日期不能為空
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        df_clean['PnL'] = clean_numeric(df_clean['PnL'])
        df_clean['R'] = clean_numeric(df_clean['R'])
        
        # 移除 PnL 或 R 是空的資料 (代表沒交易)
        df_clean = df_clean.dropna(subset=['PnL', 'R'])
        
        # 排序
        df_clean = df_clean.sort_values('Date')
        
        return df_clean, None

    except Exception as e:
        return None, f"讀取失敗: {e}"

def calculate_kpis(df):
    """計算關鍵績效指標"""
    total_trades = len(df)
    if total_trades == 0: return None
    
    # 勝率
    wins = df[df['PnL'] > 0]
    losses = df[df['PnL'] <= 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / total_trades if total_trades > 0 else 0
    
    # 賺賠比 (Payoff Ratio)
    avg_win = wins['PnL'].mean() if win_count > 0 else 0
    avg_loss = abs(losses['PnL'].mean()) if loss_count > 0 else 0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    # 期望值 (Expectancy $) = 每筆交易平均賺多少
    expectancy_amount = df['PnL'].mean()
    
    # 期望值 (Expectancy R)
    expectancy_r = df['R'].mean()
    
    # SQN (System Quality Number)
    # SQN = sqrt(N) * (Expectancy / StdDev of R)
    r_std = df['R'].std()
    sqn = (expectancy_r / r_std * np.sqrt(total_trades)) if r_std > 0 else 0
    
    return {
        "Total Trades": total_trades,
        "Win Rate": win_rate,
        "Payoff Ratio": payoff_ratio,
        "Avg Win": avg_win,
        "Avg Loss": avg_loss,
        "Expectancy $": expectancy_amount,
        "Expectancy R": expectancy_r,
        "SQN": sqn,
        "Total PnL": df['PnL'].sum()
    }

def display_expectancy_lab(xls):
    """
    期望值實驗室：主介面
    """
    df, err = get_expectancy_data(xls)
    
    if err:
        st.warning(f"⚠️ {err}")
        return
        
    if df is None or df.empty:
        st.info("尚未有足夠的交易紀錄可供分析。")
        return

    # --- 1. 顯示全域 KPI ---
    kpi = calculate_kpis(df)
    
    st.markdown("### 🏥 系統體檢報告 (System Health)")
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    k1.metric("總損益", f"${kpi['Total PnL']:,.0f}")
    
    k2.metric("勝率 (Win Rate)", f"{kpi['Win Rate']*100:.1f}%")
    k2.metric("賺賠比 (Payoff)", f"{kpi['Payoff Ratio']:.2f}")
    
    # SQN 評級顏色
    sqn = kpi['SQN']
    sqn_color = "normal"
    sqn_comment = "普通"
    if sqn < 1.6: sqn_comment = "弱 (難以獲利)"; sqn_color="off"
    elif 1.6 <= sqn < 2.0: sqn_comment = "及格 (普通)"; sqn_color="normal"
    elif 2.0 <= sqn < 3.0: sqn_comment = "優秀 (好系統)"; sqn_color="inverse"
    elif 3.0 <= sqn < 5.0: sqn_comment = "卓越 (聖杯)"; sqn_color="inverse"
    elif sqn >= 5.0: sqn_comment = "傳奇 (不可思議)"; sqn_color="inverse"
    
    k3.metric("期望值 (每筆平均)", f"${kpi['Expectancy $']:,.0f}")
    k3.metric("平均 R / 筆", f"{kpi['Expectancy R']:.2f} R")
    
    k4.metric("SQN 系統品質", f"{sqn:.2f}", delta=sqn_comment, delta_color=sqn_color)
    
    st.markdown("---")

    # --- 2. 圖表分析區 ---
    t1, t2 = st.tabs(["📈 權益曲線 (R)", "📊 盈虧分佈 & 策略"])
    
    with t1:
        # 計算累計 R
        df['Cumulative R'] = df['R'].cumsum()
        
        fig_r = go.Figure()
        fig_r.add_trace(go.Scatter(
            x=df['Date'], y=df['Cumulative R'],
            mode='lines+markers',
            name='累計 R',
            line=dict(color='#1f77b4', width=2),
            fill='tozeroy', fillcolor='rgba(31, 119, 180, 0.1)'
        ))
        
        # 加上平均期望值趨勢線 (可選)
        # x_nums = np.arange(len(df))
        # trend = x_nums * kpi['Expectancy R']
        # fig_r.add_trace(go.Scatter(x=df['Date'], y=trend, mode='lines', name='理論期望值', line=dict(dash='dash', color='gray')))

        fig_r.update_layout(
            title="<b>累計 R 倍數成長曲線</b> (排除資金規模影響，看純技術)",
            xaxis_title="", yaxis_title="累計 R",
            height=450, hovermode="x unified"
        )
        st.plotly_chart(fig_r, use_container_width=True)
        
        st.caption("💡 **為什麼要看 R？** 金額會受本金大小影響，但 **R 倍數** 反映的是你「技術的一致性」。如果這條線穩定向上，代表你的策略是可複製的。")

    with t2:
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("盈虧分佈 (R)")
            fig_hist = px.histogram(df, x="R", nbins=20, title="R 倍數分佈圖", 
                                    color_discrete_sequence=['#636EFA'])
            fig_hist.update_layout(bargap=0.1)
            # 加一條 0 軸線
            fig_hist.add_vline(x=0, line_width=2, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_hist, use_container_width=True)
            st.caption("觀察重點：虧損端 (左邊) 是否有截斷 (停損執行力)？獲利端 (右邊) 是否有延伸 (抱單能力)？")
            
        with c2:
            st.subheader("策略績效競技場")
            # 依策略分組
            if 'Strategy' in df.columns and df['Strategy'].nunique() > 0:
                strat_group = df.groupby('Strategy').agg(
                    Count=('R', 'count'),
                    Sum_R=('R', 'sum'),
                    Avg_R=('R', 'mean'),
                    Win_Rate=('PnL', lambda x: (x>0).sum() / len(x))
                ).sort_values('Sum_R', ascending=False)
                
                # 格式化
                strat_group['Win_Rate'] = strat_group['Win_Rate'].apply(lambda x: f"{x:.1%}")
                strat_group['Avg_R'] = strat_group['Avg_R'].apply(lambda x: f"{x:.2f}")
                strat_group['Sum_R'] = strat_group['Sum_R'].apply(lambda x: f"{x:.2f}")
                
                st.dataframe(strat_group, use_container_width=True)
                
                # 簡單長條圖
                fig_strat = px.bar(strat_group, x=strat_group.index, y='Sum_R', 
                                   title="各策略累計貢獻 (Total R)",
                                   text='Sum_R')
                st.plotly_chart(fig_strat, use_container_width=True)
            else:
                st.info("無法識別策略名稱，請確認 Excel 中的『策略名稱』欄位是否有值。")
