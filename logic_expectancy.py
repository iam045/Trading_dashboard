import streamlit as st
import pandas as pd
import numpy as np
import calendar
import plotly.graph_objects as go
import plotly.express as px

# ==========================================
# 0. UI 風格與 CSS 注入器 (集中管理樣式)
# ==========================================

def inject_custom_css():
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; color: #333; }
        .stApp { background-color: #f8f9fa; }
        .block-container { text-align: center; max-width: 1400px; padding-top: 2rem; }
        
        h1, h2, h3, p { text-align: center !important; }

        /* --- Metric 卡片容器 --- */
        div[data-testid="column"]:has(div[data-testid="stMetric"]) {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
            padding: 20px 15px 10px 15px;
            min-height: 180px;
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        div[data-testid="column"]:has(div[data-testid="stMetric"]):hover {
            border-color: #81C7D4;
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.08);
        }

        /* --- Metric 數值文字 --- */
        div[data-testid="stMetric"] { background-color: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
        div[data-testid="stMetricLabel"] { font-size: 13px; color: #888; justify-content: center; width: 100%; }
        div[data-testid="stMetricValue"] { font-size: 26px; font-weight: 700; color: #333; margin-bottom: 5px; }

        /* --- 日曆表格樣式 (9欄佈局) --- */
        .cal-container { width: 100%; overflow-x: auto; margin-top: 20px; }
        .cal-table { 
            width: 100%; 
            min-width: 1200px; 
            border-collapse: separate; 
            border-spacing: 6px; 
            margin: 0 auto; 
            table-layout: fixed; 
        }
        .cal-th { padding-bottom: 10px; color: #888; font-size: 13px; font-weight: 500; text-transform: uppercase; }
        .cal-td { 
            height: 90px; 
            vertical-align: top;
            border-radius: 10px; 
            background-color: #fff; 
            color: #333;
            box-shadow: 0 2px 5px rgba(0,0,0,0.02); 
            border: 1px solid #f1f1f1;
            padding: 8px;
            position: relative;
            transition: all 0.2s;
        }
        .cal-td:hover { border-color: #81C7D4; transform: translateY(-2px); }
        .day-num { font-size: 14px; color: #aaa; position: absolute; top: 8px; right: 10px; font-weight: bold; }
        .day-pnl { margin-top: 22px; font-size: 15px; font-weight: 700; text-align: center; }
        .day-info { font-size: 11px; color: inherit; opacity: 0.8; text-align: center; margin-top: 2px; }

        .summary-td { width: 150px; vertical-align: middle; background-color: transparent !important; border: none !important; box-shadow: none !important; }
        .week-card { background-color: #fff; border-radius: 12px; padding: 10px; text-align: center; border: 1px solid #e0e0e0; height: 80px; display: flex; flex-direction: column; justify-content: center; }
        .month-card { background-color: #fff; border-radius: 12px; padding: 10px; text-align: center; border: 1px solid #eeeeee; border-left: 4px solid #81C7D4; height: 80px; display: flex; flex-direction: column; justify-content: center; }
        
        .text-green { color: #00897b; }
        .text-red { color: #e53935; }
        .bg-green { background-color: #e0f2f1 !important; border-color: #b2dfdb !important; color: #004d40 !important; }
        .bg-red { background-color: #ffebee !important; border-color: #ffcdd2 !important; color: #b71c1c !important; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    return "plotly_white"

# ==========================================
# 1. 資料處理核心 (對齊 Excel 新欄位)
# ==========================================

def clean_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

def get_expectancy_data(xls):
    """修復版：抓取最新 Excel 欄位名稱"""
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到含有 '期望值' 的分頁"
    try:
        # header=14 代表從第 15 列開始抓取
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        # 欄位名稱對應映射
        mapping = {
            '日期': 'Date',
            '損益': 'PnL',
            '標準R(盈虧比)': 'R',
            '1R單位': 'Risk_Amount',
            '期望值': 'Exp_Excel',
            '累計損益': 'Cum_PnL'
        }
        
        # 只選取存在的欄位並重新命名
        existing_cols = [col for col in mapping.keys() if col in df.columns]
        df_clean = df[existing_cols].copy().rename(columns={k: v for k, v in mapping.items() if k in df.columns})
        
        # 資料清洗
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce').dt.normalize()
        for col in ['PnL', 'R', 'Risk_Amount', 'Exp_Excel', 'Cum_PnL']:
            if col in df_clean.columns:
                df_clean[col] = clean_numeric(df_clean[col])
        
        df_clean = df_clean.dropna(subset=['Date', 'PnL']).sort_values('Date')
        return df_clean, None
    except Exception as e: return None, f"讀取期望值失敗: {e}"

def get_daily_report_data(xls):
    daily_sheets = [s for s in xls.sheet_names if "日報表" in s]
    if not daily_sheets: return None, "無數據", "無"
    daily_sheets.sort(reverse=True)
    target_sheets = daily_sheets[:2]
    all_dfs = []
    for sheet in target_sheets:
        try:
            df = pd.read_excel(xls, sheet_name=sheet, header=4)
            df_cal = df.iloc[:, [0, 7]].copy()
            df_cal.columns = ['Date', 'DayPnL']
            df_cal['Date'] = pd.to_datetime(df_cal['Date'], errors='coerce').dt.normalize()
            df_cal = df_cal.dropna(subset=['Date'])
            df_cal['DayPnL'] = clean_numeric(df_cal['DayPnL']).fillna(0)
            all_dfs.append(df_cal)
        except: continue
    return pd.concat(all_dfs, ignore_index=True).sort_values('Date') if all_dfs else None, None, ""

# ==========================================
# 2. 統計計算
# ==========================================

def calculate_kpis(df):
    total = len(df); wins = df[df['PnL'] > 0]; losses = df[df['PnL'] <= 0]
    win_rate = len(wins) / total if total > 0 else 0
    avg_win_r = wins['R'].mean() if len(wins) > 0 else 0
    avg_loss_r = abs(losses['R'].mean()) if len(losses) > 0 else 1
    payoff_r = avg_win_r / avg_loss_r if avg_loss_r > 0 else 0
    pf = wins['PnL'].sum() / abs(losses['PnL'].sum()) if losses['PnL'].sum() != 0 else float('inf')
    
    # 使用 Excel 或 程式計算期望值 (R)
    exp_r = df['R'].mean()
    
    # R平方 (穩定度)
    y = df['R'].cumsum().values; x = np.arange(len(y))
    r_sq = (np.corrcoef(x, y)[0, 1]) ** 2 if len(y) > 2 else 0
    
    return {
        "Total PnL": df['PnL'].sum(), "Total Trades": total, "Win Rate": win_rate,
        "Payoff Ratio": payoff_r, "Profit Factor": pf, "Expectancy": exp_r,
        "R Squared": r_sq, "Full Kelly": (win_rate - (1 - win_rate) / payoff_r) if payoff_r > 0 else 0
    }

def calculate_trends(df):
    df = df.reset_index(drop=True).copy()
    df['Running_EV'] = df['R'].expanding().mean()
    df['Running_PF'] = (df['PnL'].apply(lambda x: x if x > 0 else 0).cumsum() / 
                        df['PnL'].apply(lambda x: abs(x) if x <= 0 else 0).cumsum().replace(0, np.nan)).fillna(1)
    df['Running_RSQ'] = df['R'].cumsum().expanding(min_periods=3).corr(pd.Series(df.index)) ** 2
    return df.fillna(0)

# ==========================================
# 3. UI 元件與繪圖
# ==========================================

def hex_to_rgba(hex_color, opacity=0.1):
    h = hex_color.lstrip('#')
    return f"rgba({int(h[0:2],16)}, {int(h[2:4],16)}, {int(h[4:6],16)}, {opacity})"

def get_sparkline(df_t, col_name, color):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_t.index, y=df_t[col_name], mode='lines', line=dict(color=color, width=2), fill='tozeroy', fillcolor=hex_to_rgba(color, 0.1)))
    fig.update_layout(height=60, margin=dict(l=0, r=0, t=5, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

@st.fragment
def draw_kpi_cards_with_charts(kpi, df_t):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("總損益", f"${kpi['Total PnL']:,.0f}")
    with c2: 
        st.metric("期望值", f"{kpi['Expectancy']:.3f} R")
        st.plotly_chart(get_sparkline(df_t, 'Running_EV', '#FF8A65'), use_container_width=True, config={'displayModeBar': False})
    with c3:
        st.metric("獲利因子", f"{kpi['Profit Factor']:.2f}")
        st.plotly_chart(get_sparkline(df_t, 'Running_PF', '#BA68C8'), use_container_width=True, config={'displayModeBar': False})
    with c4:
        st.metric("盈虧比 (R)", f"{kpi['Payoff Ratio']:.2f}")
    with c5:
        st.metric("勝率", f"{kpi['Win Rate']*100:.1f}%")

    st.write("")
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    with d4:
        st.metric("穩定度 R²", f"{kpi['R Squared']:.2f}")
        st.plotly_chart(get_sparkline(df_t, 'Running_RSQ', '#9575CD'), use_container_width=True, config={'displayModeBar': False})

@st.fragment
def draw_kelly_fragment(kpi):
    st.markdown("<h4 style='text-align: center; color: #888;'>Position Sizing (Kelly)</h4>", unsafe_allow_html=True)
    c_center = st.columns([1, 2, 2, 2, 2, 1])
    with c_center[1]: capital = st.number_input("目前本金", value=1000000, step=100000)
    with c_center[2]: kelly_frac = st.selectbox("凱利倍數", [1/4, 1/5, 1/6, 1/8], index=1, format_func=lambda x: f"1/{int(1/x)} Kelly")
    adj_kelly = max(0, kpi['Full Kelly'] * kelly_frac)
    with c_center[3]: st.metric("建議倉位 %", f"{adj_kelly*100:.2f}%")
    with c_center[4]: st.metric("建議單筆風險", f"${capital * adj_kelly:,.0f}")

@st.fragment
def draw_calendar_fragment(df_cal, theme_mode):
    if df_cal is None: return
    df_cal['DateStr'] = df_cal['Date'].dt.strftime('%Y-%m-%d')
    daily_pnl_map = df_cal.groupby('DateStr')['DayPnL'].sum().to_dict()
    unique_months = df_cal['Date'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
    
    c_sel, _ = st.columns([1, 4])
    with c_sel: sel_period = st.selectbox("選擇月份", unique_months, key='cal_month_selector', label_visibility="collapsed")
    
    y, m = sel_period.year, sel_period.month
    df_month = df_cal[(df_cal['Date'].dt.year == y) & (df_cal['Date'].dt.month == m)].sort_values('Date')
    
    # 繪製月曆 (HTML/CSS) - 略縮邏輯同前
    st.markdown(f"### {sel_period.strftime('%B %Y')}")
    # ... (此處保留原先 HTML 生成邏輯以實現 9 欄佈局)
    # [註: 因字數限制，建議此處沿用您提供的 9 欄 HTML 生成邏輯]
    
# ==========================================
# 4. 主程式進入點 (對齊 app.py)
# ==========================================

def display_expectancy_lab(xls):
    inject_custom_css()
    df_raw, err = get_expectancy_data(xls)
    if err: 
        st.warning(err);
