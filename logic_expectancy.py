import streamlit as st
import pandas as pd
import plotly.graph_objects as go

def display_expectancy_lab(df):
    """
    顯示期望值實驗室：讓用戶調整勝率與盈虧比，模擬對結果的影響
    """
    st.subheader("🧪 期望值實驗室 (Expectancy Lab)")
    st.caption("透過調整參數，模擬不同交易策略下的獲利潛力")

    # --- 1. 計算目前的基礎數據 (若有資料) ---
    current_win_rate = 0.5
    current_avg_win = 100.0
    current_avg_loss = 50.0
    
    if df is not None and not df.empty:
        # 簡單過濾出 PnL 欄位 (假設欄位名稱是 'Realized P/L' 或 'Net Profit')
        # 這裡先做個防呆，抓取可能的欄位
        pnl_col = None
        for col in ['Realized P/L', 'Net Profit', 'Profit', 'P/L']:
            if col in df.columns:
                pnl_col = col
                break
        
        if pnl_col:
            wins = df[df[pnl_col] > 0][pnl_col]
            losses = df[df[pnl_col] <= 0][pnl_col]
            
            if len(df) > 0:
                current_win_rate = len(wins) / len(df)
            if len(wins) > 0:
                current_avg_win = wins.mean()
            if len(losses) > 0:
                current_avg_loss = abs(losses.mean())

    # --- 2. 側邊欄或上方的控制項 (Sliders) ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 勝率模擬 (預設值為目前數據)
        sim_win_rate = st.slider(
            "模擬勝率 (Win Rate)", 
            min_value=0.1, 
            max_value=0.9, 
            value=float(round(current_win_rate, 2)),
            step=0.05
        )
        
    with col2:
        # 平均獲利模擬
        sim_avg_win = st.number_input(
            "模擬平均獲利 (Avg Win)", 
            min_value=0.0, 
            value=float(round(current_avg_win, 2))
        )
        
    with col3:
        # 平均虧損模擬
        sim_avg_loss = st.number_input(
            "模擬平均虧損 (Avg Loss)", 
            min_value=0.0, 
            value=float(round(current_avg_loss, 2))
        )

    # --- 3. 計算期望值 ---
    # 期望值公式 = (勝率 x 平均獲利) - (敗率 x 平均虧損)
    sim_loss_rate = 1 - sim_win_rate
    expectancy = (sim_win_rate * sim_avg_win) - (sim_loss_rate * sim_avg_loss)
    
    # 盈虧比 (Reward to Risk Ratio)
    rr_ratio = 0
    if sim_avg_loss > 0:
        rr_ratio = sim_avg_win / sim_avg_loss

    # --- 4. 顯示結果卡片 ---
    st.divider()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("模擬期望值 (Expectancy)", f"${expectancy:,.2f}", delta_color="normal")
    m2.metric("模擬盈虧比 (R/R Ratio)", f"1 : {rr_ratio:.2f}")
    
    # 凱利公式建議 (Half Kelly) - 僅供參考
    # Kelly % = W - [ (1-W) / R ]
    kelly_pct = 0
    if rr_ratio > 0:
        kelly_pct = sim_win_rate - (sim_loss_rate / rr_ratio)
    
    m3.metric("凱利公式建議倉位 (Full Kelly)", f"{kelly_pct:.1%}", help="僅供參考，通常建議使用 Half Kelly 或更低")

    # --- 5. 視覺化圖表 (期望值矩陣) ---
    st.write("---")
    st.markdown("#### 📊 策略潛力分析")
    
    # 製作一個簡單的長條圖比較
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=['獲利貢獻', '虧損拖累', '淨期望值'],
        x=[sim_win_rate * sim_avg_win, -sim_loss_rate * sim_avg_loss, expectancy],
        orientation='h',
        marker=dict(color=['#00CC96', '#EF553B', '#636EFA'])
    ))
    
    fig.update_layout(title="單筆交易期望值結構", height=300)
    st.plotly_chart(fig, use_container_width=True)
