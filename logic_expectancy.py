@st.fragment
def draw_calendar_fragment(df_cal, theme_mode):
    if df_cal is None or df_cal.empty:
        st.warning("無日報表資料"); return

    df_cal['DateStr'] = df_cal['Date'].dt.strftime('%Y-%m-%d')
    # 建立快速查詢字典：日期 -> 損益
    daily_pnl_map = df_cal.groupby('DateStr')['DayPnL'].sum().to_dict()
    
    unique_months = df_cal['Date'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
    if len(unique_months) == 0: st.info("無有效月份"); return

    st.markdown("---")
    
    # 1. 月份選擇器 (靠左)
    c_header_left, _ = st.columns([1, 4])
    with c_header_left:
        st.markdown('<div class="cal-selector">', unsafe_allow_html=True)
        sel_period = st.selectbox("選擇月份", unique_months, index=0, key='cal_month_selector', label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
    
    y, m = sel_period.year, sel_period.month
    
    # --- [NEW] 2. 計算該月統記數據 (補回的部分) ---
    # 篩選出該月份的所有交易資料
    mask_month = (df_cal['Date'].dt.year == y) & (df_cal['Date'].dt.month == m)
    df_month = df_cal[mask_month]

    # 計算邏輯
    m_pnl = df_month['DayPnL'].sum()
    
    # 計算日勝率 (分母為該月有交易的天數)
    total_days = len(df_month)
    win_days = df_month[df_month['DayPnL'] > 0]
    loss_days = df_month[df_month['DayPnL'] < 0]
    
    m_win_rate = (len(win_days) / total_days) if total_days > 0 else 0
    
    # 最大賺與最大賠
    day_max_win = win_days['DayPnL'].max() if not win_days.empty else 0
    day_max_loss = loss_days['DayPnL'].min() if not loss_days.empty else 0

    # --- [NEW] 3. 顯示數據卡片 (紅色區域) ---
    # 這裡會自動套用我們全域設定好的卡片 CSS
    m1, m2, m3, m4 = st.columns(4)
    
    with m1: st.metric("本月淨損益", f"${m_pnl:,.0f}")
    with m2: st.metric("本月日勝率", f"{m_win_rate*100:.1f}%")
    with m3: st.metric("日最大獲利", f"${day_max_win:,.0f}")
    with m4: st.metric("日最大虧損", f"${day_max_loss:,.0f}") # 若要顯示負號可維持原樣，若要顯示絕對值可加 abs()

    st.write("") # 增加一點間距
    
    # 4. 標題與日曆表格
    st.markdown(f"<h3 style='text-align: left !important; margin-bottom: 15px;'>{sel_period.strftime('%B %Y')}</h3>", unsafe_allow_html=True)

    # 準備日曆資料
    cal_obj = calendar.Calendar(firstweekday=6) # Sunday start
    month_days = cal_obj.monthdayscalendar(y, m)
    
    # HTML 建構開始 (維持無縮排以避免跑版)
    html = """<div class="cal-container"><table class='cal-table'><thead><tr><th class='cal-th'>Sun</th><th class='cal-th'>Mon</th><th class='cal-th'>Tue</th><th class='cal-th'>Wed</th><th class='cal-th'>Thu</th><th class='cal-th'>Fri</th><th class='cal-th'>Sat</th><th class='cal-th' style='width: 150px;'></th></tr></thead><tbody>"""

    week_count = 1
    
    for week in month_days:
        html += "<tr>"
        
        # --- 計算該週統計數據 ---
        week_pnl = 0
        active_days = 0
        
        for day in week:
            if day == 0: continue
            date_key = f"{y}-{m:02d}-{day:02d}"
            pnl = daily_pnl_map.get(date_key, 0)
            if pnl != 0:
                week_pnl += pnl
                active_days += 1
        
        # --- 生成左側 7 天的格子 ---
        for day in week:
            if day == 0:
                html += "<td class='cal-td' style='background: transparent; border: none; box-shadow: none;'></td>"
                continue
            
            date_key = f"{y}-{m:02d}-{day:02d}"
            day_pnl = daily_pnl_map.get(date_key, 0)
            
            td_class = "cal-td"
            pnl_html = ""
            
            if day_pnl != 0:
                color_class = "bg-green" if day_pnl > 0 else "bg-red"
                td_class += f" {color_class}"
                sign = "+" if day_pnl > 0 else "-"
                pnl_html = f"<div class='day-pnl'>{sign}${abs(day_pnl):,.0f}</div><div class='day-info'>Trade</div>"
            else:
                pnl_html = "<div style='height: 20px;'></div>"

            html += f"<td class='{td_class}'><div class='day-num'>{day}</div>{pnl_html}</td>"
        
        # --- 生成右側「每週結算」卡片 (第 8 欄) ---
        w_pnl_class = "text-green" if week_pnl >= 0 else "text-red"
        w_pnl_sign = "+" if week_pnl > 0 else ("-" if week_pnl < 0 else "")
        w_pnl_str = f"${abs(week_pnl):,.0f}" if active_days > 0 else "$0"
        
        show_card = any(d != 0 for d in week)
        
        if show_card:
            card_html = f"<div class='week-card'><div class='week-title'>Week {week_count}</div><div class='week-pnl {w_pnl_class}'>{w_pnl_sign}{w_pnl_str}</div><div class='week-days'>{active_days} active days</div></div>"
            html += f"<td class='week-summary-td'>{card_html}</td>"
            week_count += 1
        else:
            html += "<td class='week-summary-td'></td>"

        html += "</tr>"

    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)
