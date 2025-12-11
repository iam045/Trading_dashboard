import streamlit as st
import pandas as pd
import numpy as np
import calendar
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 1. 基礎運算與資料讀取 (Helper Functions)
# ==========================================

def clean_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

def get_expectancy_data(xls):
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet:
        return None, "找不到含有 '期望值' 的分頁"

    try:
        # 讀取 Excel
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        if df.shape[1] < 14:
            return None, "期望值表格欄位不足 14 欄"

        # 選取特定欄位
        df_clean = df.iloc[:, [0, 1, 10, 11, 13]].copy()
        df_clean.columns = ['Date', 'Strategy', 'Risk_Amount', 'PnL', 'R']

        # 資料清洗與過濾
        df_clean['Date'] = df_clean['Date'].ffill() 
        df_clean = df_clean.dropna(subset=['Strategy'])     # 必須有策略名
        df_clean = df_clean.dropna(subset=['Date'])         # 必須有日期
        # 轉換日期格式
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce').dt.normalize()
        
        # 轉換數字格式
        for col in ['Risk_Amount', 'PnL', 'R']:
            df_clean[col] = clean_numeric(df_clean[col])
        
        # 過濾掉損益或風險為空的資料
        df_clean = df_clean.dropna(subset=['PnL', 'Risk_Amount'])
        # 過濾掉風險 <= 0 的資料 (避免分母為0)
        df_clean = df_clean[df_clean['Risk_Amount'] > 0]

        # 依照日期排序 (若同一天有多筆，通常會維持 Excel 內的順序)
        return df_clean.sort_values('Date'), None

    except Exception as e:
        return None, f"讀取期望值失敗: {e}"

def get_daily_report_data(xls):
    sheet_names = xls.sheet_names
    daily_sheets = [s for s in sheet_names if "日報表" in s]
    
    if not daily_sheets:
        return None, "找不到含有 '日報表' 的分頁", "無"
    
    daily_sheets.sort(reverse=True)
    target_sheets = daily_sheets[:2]
    
    all_dfs = []
    error_msg = ""
    
    for sheet in target_sheets:
        try:
            df = pd.read_excel(xls, sheet_name=sheet, header=4)
            if df.shape[1] < 8: continue 
                
            df_cal = df.iloc[:, [0, 7]].copy() 
            df_cal.columns = ['Date', 'DayPnL']
            
            df_cal = df_cal.dropna(subset=['Date'])
            df_cal['Date'] = pd.to_datetime(df_cal['Date'], errors='coerce')
            df_cal = df_cal.dropna(subset=['Date'])
            df_cal['Date'] = df_cal['Date'].dt.normalize()
            
            df_cal['DayPnL'] = clean_numeric(df_cal['DayPnL'])
            df_cal = df_cal.fillna(0)
            
            all_dfs.append(df_cal)
            
        except Exception as e:
            error_msg += f"讀取 {sheet} 失敗; "
            continue

    if not all_dfs:
        return None, f"無法讀取有效日報表數據。{error_msg}", "無資料"

    final_df = pd.concat(all_dfs, ignore_index=True)
    final_df = final_df.sort_values('Date')
    info_str = f"僅讀取最新 2 個月: {', '.join(target_sheets)}"
    
    return final_df, None, info_str

def calculate_streaks(df):
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
    if len(df) < 2: return 0
    y = df['R'].cumsum().values
    x = np.arange(len(y))
    if len(x) != len(y): return 0
    correlation_matrix = np.corrcoef(x, y)
    r_squared = correlation_matrix[0, 1] ** 2
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
    win_rate = len(wins) / total_trades if total_trades > 0 else 0
    avg_win = wins['PnL'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['PnL'].mean()) if len(losses) > 0 else 0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    expectancy_custom = total_pnl / total_risk if total_risk > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    full_kelly = (win_rate - (1 - win_rate) / payoff_ratio) if payoff_ratio > 0 else 0
    
    max_win, max_loss = calculate_streaks(df)
    r_sq = calculate_r_squared(df)
    return {
        "Total Trades": total_trades, "Total PnL": total_pnl, "Win Rate": win_rate,
        "Payoff Ratio": payoff_ratio, "Expectancy Custom": expectancy_custom,
        "Profit Factor": profit_factor, "Max Win Streak": max_win,
        "Max Loss Streak": max_loss, "R Squared": r_sq, "Full Kelly": full_kelly
    }

def generate_calendar_html(year, month, pnl_dict):
    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdayscalendar(year, month)
    html = f"""
<style>
    .cal-container {{ font-family: "Source Sans Pro", sans-serif; width: 100%; }}
    .cal-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    .cal-th {{ text-align: center; color: #888; font-size: 12px; padding: 5px 0; border-bottom: 1px solid #eee; }}
    .cal-td {{ height: 90px; vertical-align: top; border: 1px solid #f0f0f0; padding: 4px; position: relative; }}
    .day-num {{ font-size: 12px; color: #999; margin-bottom: 2px; }}
    .day-pnl {{ font-size: 14px; font-weight: bold; text-align: right; position: absolute; bottom: 5px; right: 5px; }}
    .win-bg {{ background-color: #ecfdf5; color: #059669; }}
    .loss-bg {{ background-color: #fef2f2; color: #dc2626; }}
    .neutral-bg {{ background-color: #ffffff; color: #ccc; }}
</style>
<div class="cal-container"><table class="cal-table"><thead><tr>
<th class="cal-th">SUN</th><th class="cal-th">MON</th><th class="cal-th">TUE</th><th class="cal-th">WED</th><th class="cal-th">THU</th><th class="cal-th">FRI</th><th class="cal-th">SAT</th>
</tr></thead><tbody>
"""
    for week in month_days:
        html += "<tr>"
        for day in week:
            if day == 0:
                html += "<td class='cal-td' style='background-color: #fafafa;'></td>"
                continue
            date_key = f"{year}-{month:02d}-{day:02d}"
            day_pnl = pnl_dict.get(date_key, 0)
            
            has_trade = (date_key in pnl_dict) and (day_pnl != 0)
            
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
            html += f"<td class='cal-td {bg_class}'><div class='day-num'>{day}</div><div class='day-pnl'>{pnl_text}</div></td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    return html

# ==========================================
# 2. 進階計算：趨勢分析 (數據透明化版)
# ==========================================

def calculate_trends(df, mode='cumulative', window=50):
    """
    計算每筆交易後的 KPI 變化
    """
    # 確保排序並建立乾淨的索引
    df = df.sort_values('Date').reset_index(drop=True).copy()
    
    # 增加交易序號 (從1開始)
    df['Trade_Num'] = df.index + 1
    
    # 預計算輔助欄位
    df['gross_win'] = df['PnL'].apply(lambda x: x if x > 0 else 0)
    df['gross_loss'] = df['PnL'].apply(lambda x: abs(x) if x <= 0 else 0)
    df['is_win'] = (df['PnL'] > 0).astype(int)
    df['is_loss'] = (df['PnL'] <= 0).astype(int)
    
    pnl_series = df['PnL']
    risk_series = df['Risk_Amount']
    gross_win_series = df['gross_win']
    gross_loss_series = df['gross_loss']
    win_count_series = df['is_win']
    loss_count_series = df['is_loss']
    
    if mode == 'rolling':
        s_pnl = pnl_series.rolling(window=window, min_periods=1).sum()
        s_risk = risk_series.rolling(window=window, min_periods=1).sum()
        s_g_win = gross_win_series.rolling(window=window, min_periods=1).sum()
        s_g_loss = gross_loss_series.rolling(window=window, min_periods=1).sum()
        s_c_win = win_count_series.rolling(window=window, min_periods=1).sum()
        s_c_loss = loss_count_series.rolling(window=window, min_periods=1).sum()
    else:
        s_pnl = pnl_series.cumsum()
        s_risk = risk_series.cumsum()
        s_g_win = gross_win_series.cumsum()
        s_g_loss = gross_loss_series.cumsum()
        s_c_win = win_count_series.cumsum()
        s_c_loss = loss_count_series.cumsum()

    # --- KPI 計算 ---
    df['Expectancy'] = s_pnl / s_risk.replace(0, np.nan)
    
    df['Profit Factor'] = s_g_win / s_g_loss.replace(0, np.nan)
    df['Profit Factor'] = df['Profit Factor'].fillna(10).clip(upper=10)

    avg_win = s_g_win / s_c_win.replace(0, np.nan)
    avg_loss = s_g_loss / s_c_loss.replace(0, np.nan)
    df['Payoff Ratio'] = avg_win / avg_loss.replace(0, np.nan)
    
    # --- R Squared ---
    equity_curve = df['PnL'].cumsum()
    x_axis = pd.Series(np.arange(len(df)), index=df.index)
    
    if mode == 'rolling':
        r = equity_curve.rolling(window=window, min_periods=3).corr(x_axis)
        df['R Squared'] = r ** 2
    else:
        r = equity_curve.expanding(min_periods=3).corr(x_axis)
        df['R Squared'] = r ** 2

    df = df.fillna(0)
    
    # 只保留畫圖與檢查需要的欄位
    return df[['Date', 'Trade_Num', 'PnL', 'Risk_Amount', 'Expectancy', 'Profit Factor', 'Payoff Ratio', 'R Squared']]

# ==========================================
# 3. UI 顯示邏輯 (Fragment 局部刷新區塊)
# ==========================================

@st.fragment
def draw_kelly_fragment(kpi):
    k1, k2, k3, k4 = st.columns([1, 1, 1, 1])
    with k1: 
        capital = st.number_input("目前本金", value=300000, step=10000)
    with k2: 
        fraction_options = [1/5, 1/6, 1/7, 1/8]
        kelly_frac = st.selectbox(
            "凱利倍數", fraction_options, index=2, 
            format_func=lambda x: f"1/{int(1/x)} Kelly"
        )
    full_kelly_val = kpi.get('Full Kelly', 0)
    adj_kelly = max(0, full_kelly_val * kelly_frac)
    risk_amt = capital * adj_kelly
    
    k3.metric("建議倉位 %", f"{adj_kelly*100:.2f}%")
    k4.metric("建議單筆風險", f"${risk_amt:,.0f}")
    st.markdown("---") 

@st.fragment
def draw_bottom_fragment(df_cal, sheet_info_cal, df_kpi):
    tab1, tab2 = st.tabs(["📅 交易日曆", "📈 趨勢分析"])
    
    # --- Tab 1: 日曆 ---
    with tab1:
        if df_cal is not None and not df_cal.empty:
            df_cal['DateStr'] = df_cal['Date'].dt.strftime('%Y-%m-%d')
            daily_pnl_series = df_cal.groupby('DateStr')['DayPnL'].sum()
            pnl_dict = daily_pnl_series.to_dict()
            unique_months = df_cal['Date'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
            
            if len(unique_months) > 0:
                sel_col, _ = st.columns([1, 4]) 
                with sel_col:
                    selected_period = st.selectbox("選擇月份", unique_months, index=0, key='cal_month_selector')
                
                y, m = selected_period.year, selected_period.month
                month_prefix = f"{y}-{m:02d}"
                month_data = daily_pnl_series[daily_pnl_series.index.str.startswith(month_prefix)]
                
                cal_col, stat_col = st.columns([3, 1])
                with cal_col:
                    st.markdown(f"**{selected_period.strftime('%B %Y')}**")
                    cal_html = generate_calendar_html(y, m, pnl_dict)
                    st.markdown(cal_html, unsafe_allow_html=True)
                    
                with stat_col:
                    m_pnl = month_data.sum()
                    m_max_win = month_data.max() if not month_data.empty and month_data.max() > 0 else 0
                    m_max_loss = month_data.min() if not month_data.empty and month_data.min() < 0 else 0
                    m_win_days = (month_data > 0).sum()
                    m_loss_days = (month_data < 0).sum()
                    total_days = m_win_days + m_loss_days
                    m_win_rate = m_win_days / total_days if total_days > 0 else 0
                    
                    with st.container():
                        st.metric("月損益", f"${m_pnl:,.0f}", delta="本月成果")
                        st.divider()
                        st.metric("單日最大賺", f"${m_max_win:,.0f}", delta_color="normal")
                        st.metric("單日最大賠", f"${m_max_loss:,.0f}", delta_color="inverse")
                        st.metric("月勝率", f"{m_win_rate:.1%}", help="計算方式: 獲利天數 / 總交易天數")
                        st.divider()
                        st.write(f"📈 獲利天數: **{m_win_days}**")
                        st.write(f"📉 虧損天數: **{m_loss_days}**")
            else:
                st.info("讀取的資料中無有效月份。")
        else:
            st.warning("⚠️ 無法讀取日報表資料，請確認檔案。")

    # --- Tab 2: 趨勢分析 ---
    with tab2:
        if df_kpi is not None and not df_kpi.empty:
            
            # 1. 顯示資料概況 (回答使用者: 總共有幾筆)
            total_rows = len(df_kpi)
            st.markdown(f"**📊 資料來源：** Excel 分頁 `期望值`，共讀取到 **{total_rows}** 筆有效交易資料。")
            
            # 2. 控制列
            cc1, cc2 = st.columns([1, 2])
            with cc1:
                calc_mode = st.radio("計算模式", ["Cumulative (累計)", "Rolling (滾動)"], index=1, horizontal=True)
            
            window_size = 50
            if "Rolling" in calc_mode:
                with cc2:
                    window_size = st.slider("滾動視窗大小 (筆數)", min_value=10, max_value=200, value=50, step=10)
                mode_key = 'rolling'
            else:
                mode_key = 'cumulative'

            # 3. 計算
            df_trends = calculate_trends(df_kpi, mode=mode_key, window=window_size)
            
            # 4. 數據檢查器 (回答使用者: 資料長什麼樣子?)
            with st.expander("🔍 點此檢查詳細運算數據 (Data Inspector)"):
                st.write(f"以下是計算後的詳細數據 (模式: {calc_mode}, 視窗: {window_size} 筆):")
                st.dataframe(df_trends, use_container_width=True)

            # 5. 繪圖
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=(
                    f"期望值 ({'近'+str(window_size)+'筆' if mode_key=='rolling' else '累計'})", 
                    f"獲利因子 ({'近'+str(window_size)+'筆' if mode_key=='rolling' else '累計'})", 
                    f"盈虧比 ({'近'+str(window_size)+'筆' if mode_key=='rolling' else '累計'})", 
                    f"穩定度 R² ({'近'+str(window_size)+'筆' if mode_key=='rolling' else '累計'})"
                ),
                vertical_spacing=0.15
            )

            hover_template = "日期: %{x}<br>數值: %{y:.2f}<br>交易序號: %{customdata[0]}<extra></extra>"

            fig.add_trace(go.Scatter(
                x=df_trends['Date'], y=df_trends['Expectancy'], 
                customdata=df_trends[['Trade_Num']], hovertemplate=hover_template,
                mode='lines', name='Exp', line=dict(color='#636EFA', width=1.5)
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=df_trends['Date'], y=df_trends['Profit Factor'], 
                customdata=df_trends[['Trade_Num']], hovertemplate=hover_template,
                mode='lines', name='PF', line=dict(color='#00CC96', width=1.5)
            ), row=1, col=2)

            fig.add_trace(go.Scatter(
                x=df_trends['Date'], y=df_trends['Payoff Ratio'], 
                customdata=df_trends[['Trade_Num']], hovertemplate=hover_template,
                mode='lines', name='Payoff', line=dict(color='#EF553B', width=1.5)
            ), row=2, col=1)

            fig.add_trace(go.Scatter(
                x=df_trends['Date'], y=df_trends['R Squared'], 
                customdata=df_trends[['Trade_Num']], hovertemplate=hover_template,
                mode='lines', name='R²', line=dict(color='#AB63FA', width=1.5)
            ), row=2, col=2)

            fig.update_layout(height=500, showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(showgrid=True, gridcolor='#eee')
            
            st.plotly_chart(fig, use_container_width=True)
            
            if mode_key == 'rolling':
                st.caption(f"💡 提示：若您的總交易筆數 ({total_rows}) 少於滾動視窗 ({window_size})，曲線將與累計模式相似。")
        else:
            st.info("無足夠交易數據可繪製趨勢圖。")

# ==========================================
# 4. 主程式進入點
# ==========================================

def display_expectancy_lab(xls):
    df_kpi, err_kpi = get_expectancy_data(xls)
    df_cal, err_cal, sheet_info_cal = get_daily_report_data(xls)

    if err_kpi:
        st.warning(f"⚠️ KPI 資料讀取警示: {err_kpi}")
    if df_kpi is None or df_kpi.empty:
        st.info("尚未有足夠的交易紀錄可供分析 KPI。")
        return

    kpi = calculate_kpis(df_kpi)
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("總損益 (Net PnL)", f"${kpi['Total PnL']:,.0f}", help="所有交易的淨損益總和")
    c2.metric("期望值 (Exp)", f"{kpi['Expectancy Custom']:.2f} R", help="公式: 總損益 / 總風險金額。\n意義: 每投入 1 元風險，預期能賺回多少元 (R)。")
    pf = kpi['Profit Factor']
    c3.metric("獲利因子 (PF)", f"{pf:.2f}", delta=">1.5 佳" if pf>1.5 else None, help="公式: 總獲利金額 / 總虧損金額。\n意義: 衡量獲利效率，數值越大代表用越少的虧損換取獲利。")
    c4.metric("盈虧比 (Payoff)", f"{kpi['Payoff Ratio']:.2f}", help="公式: 平均獲利 / 平均虧損。\n意義: 賺錢時賺多少 v.s. 賠錢時賠多少的比例。")
    c5.metric("勝率 (Win Rate)", f"{kpi['Win Rate']*100:.1f}%", help="公式: 獲利筆數 / 總交易筆數。")
    st.markdown("---")
    
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆", help="系統回測的總樣本數")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次", delta="High", delta_color="normal", help="連續獲利的最高次數")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次", delta="Risk", delta_color="inverse", help="連續虧損的最高次數 (Drawdown 風險指標)")
    r2 = kpi['R Squared']
    d4.metric("曲線穩定度 (R²)", f"{r2:.2f}", help="公式: 資金曲線與 45度直線 的相關係數平方。\n意義: 0~1 之間，越接近 1 代表資金成長越平滑穩定，非大起大落。")
    d5.empty()
    st.markdown("---")

    draw_kelly_fragment(kpi)

    draw_bottom_fragment(df_cal, sheet_info_cal, df_kpi)
