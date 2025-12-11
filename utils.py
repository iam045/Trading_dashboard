# utils.py
import streamlit as st
import pandas as pd
import time
import re

# --- 連線設定 ---
@st.cache_resource(ttl=60)
def load_google_sheet():
    """從 Google Cloud 下載 Excel 檔案"""
    try:
        if "google_sheet_id" not in st.secrets:
            return None, "請在 Streamlit Secrets 設定 'google_sheet_id'"
        
        sheet_id = st.secrets["google_sheet_id"]
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx&t={int(time.time())}"
        
        return pd.ExcelFile(url, engine='openpyxl'), None
    except Exception as e:
        return None, f"無法讀取雲端檔案: {e}"

# --- 資料清洗小幫手 ---
def clean_numeric_column(series):
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

# --- 讀取單一分頁邏輯 ---
def read_daily_pnl(xls, sheet_name):
    try:
        df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=50)
        
        # [策略 A] 關鍵字搜尋
        target_keywords = ['日總計', '總計', '累計損益', '損益']
        header_row, pnl_col_idx = -1, -1
        
        for r in range(len(df_raw)):
            row_vals = [str(v).replace(" ", "") for v in df_raw.iloc[r]]
            if any(k in v for k in target_keywords for v in row_vals):
                header_row = r
                for c, val in enumerate(row_vals):
                    if any(k in val for k in target_keywords):
                        pnl_col_idx = c
                        break
                break
        
        if header_row != -1:
            df = df_raw.iloc[header_row+1:, [0, pnl_col_idx]].copy()
            df.columns = ['Date', 'Daily_PnL']
            df['Daily_PnL'] = clean_numeric_column(df['Daily_PnL'])
            if df['Daily_PnL'].count() > 0:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                return df.dropna(subset=['Date', 'Daily_PnL'])

        # [策略 B] 暴力指定 H7
        if df_raw.shape[0] > 6 and df_raw.shape[1] > 7:
            df_force = df_raw.iloc[6:, [0, 7]].copy()
            df_force.columns = ['Date', 'Daily_PnL']
            df_force['Date'] = pd.to_datetime(df_force['Date'], errors='coerce')
            df_force['Daily_PnL'] = clean_numeric_column(df_force['Daily_PnL'])
            return df_force.dropna(subset=['Date', 'Daily_PnL'])

        return pd.DataFrame()
    except: return pd.DataFrame()

# --- 數學插值 (紅綠分色用) ---
def insert_zero_crossings(df):
    if df.empty: return df
    df = df.sort_values('Date').reset_index(drop=True)
    new_rows = []
    for i in range(len(df) - 1):
        curr, next_row = df.iloc[i], df.iloc[i+1]
        y1, y2 = curr['Cumulative_PnL'], next_row['Cumulative_PnL']
        if (y1 > 0 and y2 < 0) or (y1 < 0 and y2 > 0):
            t1, t2 = curr['Date'].timestamp(), next_row['Date'].timestamp()
            zero_t = t1 + (0 - y1) * (t2 - t1) / (y2 - y1)
            new_rows.append({
                'Date': pd.Timestamp.fromtimestamp(zero_t), 
                'Daily_PnL': 0, 'Cumulative_PnL': 0
            })
    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        return df.sort_values('Date').reset_index(drop=True)
    return df
