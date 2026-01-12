import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def get_expectancy_data(xls):
    """從 Excel 讀取並清洗期望值數據"""
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet:
        return None, "找不到名稱包含 '期望值' 的分頁"
    
    try:
        # header=14 代表標題在第 15 列
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        # 定義欄位映射 (左邊是 Excel 名稱，右邊是程式變數名)
        mapping = {
            '日期': 'Date',
            '損益': 'PnL',
            '標準R(盈虧比)': 'R',
            '1R單位': 'Risk_Amount',
            '期望值': 'Expectancy',
            '累計損益': 'Cum_PnL'
        }
        
        # 檢查必備欄位
        existing_cols = [col for col in mapping.keys() if col in df.columns]
        df = df[existing_cols].copy()
        df.rename(columns={k: v for k, v in mapping.items() if k in df.columns}, inplace=True)

        # 清洗資料
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        for col in ['PnL', 'R', 'Risk_Amount', 'Expectancy', 'Cum_PnL']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
        
        # 移除日期或損益為空的無效行
        df = df.dropna(subset=['Date', 'PnL']).sort_values('Date')
        
        # 補全可能缺少的欄位 (確保 UI 不崩潰)
        if 'R' not in df.columns:
            df['R'] = df['PnL'] / df['Risk_Amount'].replace(0, 1)
        if 'Expectancy' not in df.columns:
            df['Expectancy'] = df['R'].expanding().mean()
            
        return df, None
    except Exception as e:
        return None, f"數據處理失敗: {str(e)}"

def show_expectancy_page(xls):
    st.header("🧪 期望值實驗室 (R-Unit Based)")
    
    df, error = get_expectancy_data(xls)
    if error:
        st.error(error)
        return

    # 計算核心指標
    total_trades = len(df)
    avg_ev = df['R'].mean()
    win_rate = (df['PnL'] > 0).sum() / total_trades
    total_r = df['R'].sum()

    # UI 指標卡
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("交易次數", f"{total_trades} 筆")
    col2.metric("當前期望值", f"{avg_ev:.3f} R", delta=None)
    col3.metric("累積獲利 R", f"{total_r:.2f} R")
    col4.metric("勝率", f"{win_rate:.1%}")

    # 1. 期望值動態趨勢圖
    st.subheader("期望值變動曲線 (Running EV)")
    fig_ev = px.line(df, x='Date', y='Expectancy', 
                     title="策略穩定度趨勢 (應穩定在 0.2R 以上)",
                     labels={'Expectancy': '期望值 (R)', 'Date': '日期'})
    fig_ev.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_ev.add_hline(y=avg_ev, line_color="red", annotation_text=f"目前平均: {avg_ev:.3f}")
    st.plotly_chart(fig_ev, use_container_width=True)

    # 2. 獲利累積曲線
    st.subheader("累積損益曲線 (TWD)")
    fig_pnl = px.area(df, x='Date', y='Cum_PnL', 
                      title="帳戶資金成長曲線",
                      labels={'Cum_PnL': '累積損益 (元)'})
    st.plotly_chart(fig_pnl, use_container_width=True)

    # 顯示原始資料表
    with st.expander("查看底層數據 (最新 10 筆)"):
        st.dataframe(df.tail(10), use_container_width=True)
