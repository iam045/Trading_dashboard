def inject_custom_css():
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; color: #333; }
        .stApp { background-color: #f8f9fa; }
        .block-container { text-align: center; }
        
        h1, h2, h3, p { text-align: center !important; }

        /* --- Metric 卡片樣式 (保持不變) --- */
        div[data-testid="column"]:has(div[data-testid="stMetric"]) {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
            padding: 20px 15px 10px 15px;
            min-height: 160px;
            transition: transform 0.2s;
        }
        div[data-testid="column"]:has(div[data-testid="stMetric"]):hover {
            border-color: #81C7D4;
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.05);
        }

        /* --- Metric 數值微調 --- */
        div[data-testid="stMetricLabel"] { font-size: 13px; color: #888; justify-content: center; width: 100%; }
        div[data-testid="stMetricValue"] { font-size: 24px; font-weight: 600; color: #333; }

        /* --- Popover 按鈕 --- */
        div[data-testid="column"] div[data-testid="stPopover"] button {
            border: none !important;
            background: transparent !important;
            color: #81C7D4 !important;
            width: 100% !important;
            margin-top: 10px !important;
            border-top: 1px solid #f5f5f5 !important;
        }

        /* --- 新版日曆樣式 (整合每週結算欄) --- */
        .cal-container {
            width: 100%;
            overflow-x: auto;
        }
        .cal-table { 
            width: 100%; 
            border-collapse: separate; 
            border-spacing: 6px; /* 單元格間距 */
            margin: 0 auto; 
            table-layout: fixed; /* 固定寬度，避免跑版 */
        }
        
        /* 日期單元格 (左邊 7 欄) */
        .cal-td { 
            height: 90px; /*稍微加高以容納更多資訊*/
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
        
        /* 標題列 (SUN, MON...) */
        .cal-th {
            padding-bottom: 10px;
            color: #888;
            font-size: 13px;
            font-weight: 500;
            text-transform: uppercase;
        }

        /* 日期數字 */
        .day-num { 
            font-size: 14px; 
            color: #aaa; 
            position: absolute; 
            top: 8px; 
            right: 10px; 
            font-weight: bold;
        }
        
        /* 單日損益數字 */
        .day-pnl { 
            margin-top: 22px; 
            font-size: 15px; 
            font-weight: 700; 
            text-align: center;
        }
        
        /* 單日交易資訊 (筆數/勝率 - 仿照圖2) */
        .day-info {
            font-size: 11px;
            color: inherit;
            opacity: 0.8;
            text-align: center;
            margin-top: 2px;
        }

        /* --- 右側：每週結算欄位樣式 --- */
        .week-summary-td {
            width: 160px; /* 固定右側欄寬度 */
            vertical-align: middle;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding-left: 15px !important; /* 與日曆的間距 */
        }
        
        .week-card {
            background-color: #fff;
            border-radius: 12px;
            padding: 15px 10px;
            text-align: center;
            border: 1px solid #e0e0e0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.03);
            height: 80px; /* 讓高度稍微小於日期格，產生置中感 */
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        
        .week-title { font-size: 12px; color: #81C7D4; font-weight: bold; margin-bottom: 4px; }
        .week-pnl { font-size: 18px; font-weight: 700; margin-bottom: 2px; }
        .week-days { font-size: 11px; color: #999; }

        /* 顏色定義 */
        .text-green { color: #00897b; }
        .text-red { color: #e53935; }
        .bg-green { background-color: #e0f2f1 !important; border-color: #b2dfdb !important; color: #004d40 !important; }
        .bg-red { background-color: #ffebee !important; border-color: #ffcdd2 !important; color: #b71c1c !important; }

    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    return "plotly_white"
