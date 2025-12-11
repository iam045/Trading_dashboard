def inject_custom_css():
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; color: #333; }
        .stApp { background-color: #f8f9fa; }
        .block-container { text-align: center; }
        h1, h2, h3, p { text-align: center !important; }

        /* --- 1. 卡片容器 (Column) --- */
        div[data-testid="column"]:has(div[data-testid="stMetric"]) {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
            padding: 20px 10px; /* 增加一點 padding */
            text-align: center;
            position: relative; /* 關鍵：作為定位基準 */
            transition: transform 0.2s;
            min-height: 140px;
        }
        div[data-testid="column"]:has(div[data-testid="stMetric"]):hover {
            border-color: #81C7D4;
            transform: translateY(-2px);
        }

        /* --- 2. 改造 Popover 按鈕 (關鍵修改) --- */
        /* 定位：浮在卡片右上角 */
        div[data-testid="column"] div[data-testid="stPopover"] {
            position: absolute !important;
            top: 10px !important;
            right: 10px !important; /* 靠右對齊 */
            width: auto !important;
            z-index: 99 !important;
        }

        /* 樣式：去除所有按鈕特徵，只留文字(圖示) */
        div[data-testid="column"] div[data-testid="stPopover"] > button {
            border: none !important;
            background: transparent !important;
            box-shadow: none !important;
            color: #81C7D4 !important; /* 主題色 */
            padding: 0px !important;
            margin: 0px !important;
            font-size: 1.2rem !important; /* 圖示大小 */
            line-height: 1 !important;
            min-height: 0px !important;
            height: auto !important;
        }

        /* 滑鼠移過去的效果 */
        div[data-testid="column"] div[data-testid="stPopover"] > button:hover {
            color: #4dd0e1 !important;
            transform: scale(1.15); /* 稍微放大 */
            background: transparent !important;
        }
        
        /* 點擊時不要有框線 */
        div[data-testid="column"] div[data-testid="stPopover"] > button:focus,
        div[data-testid="column"] div[data-testid="stPopover"] > button:active {
            outline: none !important;
            box-shadow: none !important;
            border: none !important;
            background: transparent !important;
        }

        /* --- 3. Metric 微調 --- */
        div[data-testid="stMetric"] {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
        }
        div[data-testid="stMetricLabel"] { font-size: 13px; color: #888; justify-content: center; width: 100%; }
        div[data-testid="stMetricValue"] { font-size: 26px; font-weight: 600; color: #333; margin-top: 5px; }

        /* 其他通用樣式 */
        .cal-table { width: 100%; border-collapse: separate; border-spacing: 5px; margin: 0 auto; }
        .cal-td { 
            height: 70px; width: 14%; vertical-align: middle; 
            border-radius: 12px; background-color: #fff; color: #333;
            box-shadow: 0 2px 5px rgba(0,0,0,0.02); border: 1px solid #f1f1f1;
            transition: all 0.2s;
        }
        .cal-td:hover { border-color: #81C7D4; transform: translateY(-2px); }
        .day-num { font-size: 12px; color: #bbb; margin-bottom: 2px; }
        .day-pnl { font-size: 13px; font-weight: 600; }
        .modebar { display: none !important; }
        .cal-selector div[data-baseweb="select"] { text-align: left; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    return "plotly_white"
