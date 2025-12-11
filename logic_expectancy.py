def display_expectancy_lab(xls):
    df, err = get_expectancy_data(xls)
    
    if err:
        st.warning(f"⚠️ {err}")
        return
    if df is None or df.empty:
        st.info("尚未有足夠的交易紀錄可供分析。")
        return

    kpi = calculate_kpis(df)
    
    # --- 1. 系統體檢報告 (3x4 嚴格對齊) ---
    st.markdown("### 🏥 系統體檢報告 (System Health)")
    
    # ===================================================================
    # R1: 交易次數 (只用第一欄，保持靠左，確保與下方對齊)
    # ===================================================================
    # Streamlit 必須宣告 4 個欄位，只使用第一個欄位
    r1c1, r1c2, r1c3, r1c4 = st.columns(4) 
    r1c1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    
    # ===================================================================
    # R2: 損益, 勝率, 連勝, 連敗
    # ===================================================================
    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    r2c1.metric("總損益 (Net PnL)", f"${kpi['Total PnL']:,.0f}")
    r2c2.metric("勝率 (Win Rate)", f"{kpi['Win Rate']*100:.1f}%")
    r2c3.metric("最大連勝", f"{kpi['Max Win Streak']} 次", delta="🔥 High", delta_color="normal")
    r2c4.metric("最大連敗", f"{kpi['Max Loss Streak']} 次", delta="❄️ Risk", delta_color="inverse")
    
    # ===================================================================
    # R3: 期望值, 盈虧比, 獲利因子, 曲線穩定度 (R²)
    # ===================================================================
    r3c1, r3c2, r3c3, r3c4 = st.columns(4)
    
    # 期望值
    r3c1.metric("期望值 (Exp R)", f"{kpi['Expectancy Custom']:.2f} R", help="總損益 / 含成本總風險")
    
    # 盈虧比 (Payoff Ratio)
    r3c2.metric("盈虧比 (Payoff)", f"{kpi['Payoff Ratio']:.2f}")
    
    # 獲利因子 (PF)
    pf = kpi['Profit Factor']
    pf_col = "normal" if pf >= 1 else "inverse"
    r3c3.metric("獲利因子 (PF)", f"{pf:.2f}", delta="> 1.5 佳", delta_color="off")
    
    # 曲線穩定度 (R^2) - 替換原本的「與其他」
    r2 = kpi['R Squared']
    r2_color = "normal" if r2 > 0.8 else "off"
    r3c4.metric("曲線穩定度 (R²)", f"{r2:.2f}", delta="越近 1 越穩", delta_color="off")

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
