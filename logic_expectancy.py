def generate_calendar_html(year, month, df_daily):
    """
    生成 HTML 格式的月曆 (CSS Grid/Table)
    修正：移除多餘縮排，避免 Streamlit 誤判為程式碼區塊
    """
    cal = calendar.Calendar(firstweekday=6) # 星期日開始
    month_days = cal.monthdayscalendar(year, month)
    
    # CSS 樣式 (壓縮為一行或靠左，避免 markdown 解析錯誤)
    html = f"""
    <style>
        .cal-container {{ font-family: "Source Sans Pro", sans-serif; width: 100%; }}
        .cal-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
        .cal-th {{ text-align: center; color: #888; font-size: 12px; padding: 5px 0; border-bottom: 1px solid #eee; }}
        .cal-td {{ 
            height: 90px; 
            vertical-align: top; 
            border: 1px solid #f0f0f0; 
            padding: 4px; 
            position: relative;
        }}
        .day-num {{ font-size: 12px; color: #999; margin-bottom: 2px; }}
        .day-pnl {{ 
            font-size: 14px; 
            font-weight: bold; 
            text-align: right; 
            position: absolute; 
            bottom: 5px; 
            right: 5px; 
        }}
        
        /* 顏色定義 */
        .win-bg {{ background-color: #ecfdf5; color: #059669; }}  /* 淺綠底 */
        .loss-bg {{ background-color: #fef2f2; color: #dc2626; }} /* 淺紅底 */
        .neutral-bg {{ background-color: #ffffff; color: #ccc; }}
    </style>
    <div class="cal-container">
        <table class="cal-table">
            <thead>
                <tr>
                    <th class="cal-th">SUN</th><th class="cal-th">MON</th><th class="cal-th">TUE</th>
                    <th class="cal-th">WED</th><th class="cal-th">THU</th><th class="cal-th">FRI</th>
                    <th class="cal-th">SAT</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for week in month_days:
        html += "<tr>"
        for day in week:
            if day == 0:
                # 空白日期
                html += "<td class='cal-td' style='background-color: #fafafa;'></td>"
                continue
            
            # 查找當日損益
            current_date = pd.Timestamp(year, month, day)
            day_pnl = 0
            has_trade = False
            
            if current_date in df_daily.index:
                day_pnl = df_daily.loc[current_date]
                has_trade = True
            
            # 決定樣式
            bg_class = "neutral-bg"
            pnl_text = ""
            if has_trade:
                if day_pnl > 0:
                    bg_class = "win-bg"
                    pnl_text = f"+${day_pnl:,.0f}"
                elif day_pnl < 0:
                    bg_class = "loss-bg"
                    pnl_text = f"-${abs(day_pnl):,.0f}"
                else:
                    pnl_text = "$0"
            
            # 這裡很重要：HTML 標籤緊貼左邊，不要有縮排
            html += f"""<td class='cal-td {bg_class}'><div class="day-num">{day}</div><div class="day-pnl">{pnl_text}</div></td>"""
            
        html += "</tr>"
    
    html += "</tbody></table></div>"
    return html
