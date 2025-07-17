import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import io
from datetime import datetime
import json
import re
import bcrypt
import matplotlib.font_manager as fm # フォントマネージャーをインポート
import os

# このファイルと同じ階層に static フォルダがある場合
font_path = os.path.join(os.path.dirname(__file__), "static", "NotoSansJP-VariableFont_wght.ttf")
# 絶対パスに変換（これが一番安全！）
font_path = os.path.abspath(font_path)

if os.path.exists(font_path):
    font_prop = fm.FontProperties(fname=font_path)
    plt.rcParams["font.family"] = font_prop.get_name()
    japanese_font_available = True
else:
    font_prop = None
    japanese_font_available = False
    st.warning("日本語フォントが見つかりませんでした。グラフのラベルが文字化けする可能性があります。")

# matplotlibのフォント設定
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10

# フォント読み込みチェック
if os.path.exists(font_path):
    #font_prop = fm.FontProperties(fname=font_path)
    #font_name = font_prop.get_name()
    #plt.rcParams['font.family'] = font_name  # ← matplotlib 全体でのフォント設定

    # 特定のフォントパスをmatplotlibのキャッシュに追加
    fm.fontManager.addfont(font_path)
    # 追加したフォントのプロパティを再取得
    font_prop_new = fm.FontProperties(fname=font_path)
    # matplotlibのデフォルトフォントをそのフォントに設定
    plt.rcParams['font.family'] = font_prop_new.get_name()

    japanese_font_available = True
else:
    japanese_font_available = False
    st.warning("日本語フォントが見つかりませんでした。グラフのラベルが文字化けする可能性があります。")

# --- 定数と設定 ---
USERS_FILE = 'users.json' # ユーザー情報を保存するファイル

# --- ヘルパー関数 ---
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'r+', encoding='utf-8') as f:
        # ファイルの内容を全て読み込む
        data = f.read()
        # ファイルポインタを先頭に戻す
        f.seek(0)
        # データを書き込む
        json.dump(users, f, indent=4, ensure_ascii=False)
        # 余分な内容を切り捨てる（ファイルが小さくなった場合に対応）
        f.truncate()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def get_localized_text(key):
    # 日本語と英語の切り替え
    if st.session_state.get('language', 'ja') == 'ja':
        translations = {
            "VRイベント分析ツール": "VRイベント分析ツール",
            "パスワードをリセット": "パスワードをリセット",
            "登録": "登録",
            "パスワードが一致しません。": "パスワードが一致しません。",
            "ユーザー登録が完了しました。": "ユーザー登録が完了しました。",
            "ユーザー登録": "ユーザー登録",
            "新しいパスワード": "新しいパスワード",
            "パスワード（確認用）": "パスワード（確認用）",
            "ユーザー名": "ユーザー名",
            "パスワード": "パスワード",
            "ログイン": "ログイン",
            "ユーザー名またはパスワードが間違っています。": "ユーザー名またはパスワードが間違っています。",
            "ログインしていません。": "ログインしていません。",
            "ログアウト": "ログアウト",
            "データ管理": "データ管理",
            "データ分析": "データ分析",
            "ユーザー: ": "ユーザー: ",
            "ファイルをアップロード（CSV形式）": "ファイルをアップロード（CSV形式）",
            "CSVファイルをアップロードしてください。": "CSVファイルをアップロードしてください。",
            "アップロードされたファイル": "アップロードされたファイル",
            "ファイル名": "ファイル名",
            "削除": "削除",
            "ファイルの形式が正しくありません。CSVファイルを選択してください。": "ファイルの形式が正しくありません。CSVファイルを選択してください。",
            "ファイルが正常にアップロードされました。": "ファイルが正常にアップロードされました。",
            "データがアップロードされていません。": "データがアップロードされていません。",
            "日付範囲フィルター": "日付範囲フィルター",
            "開始日": "開始日",
            "終了日": "終了日",
            "日付データがありません。": "日付データがありません。",
            "日付列が見つかりませんでした。": "日付列が見つかりませんでした。",
            "日付範囲をリセット": "日付範囲をリセット",
            "担当チームが選択されていません。全ての担当チームのデータが表示されます。": "担当チームが選択されていません。全ての担当チームのデータが表示されます。",
            "データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。": "データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。",
            "ヒートマップ": "ヒートマップ",
            "選択された列": "選択された列",
            "最小値": "最小値",
            "最大値": "最大値",
            "ヒストグラム": "ヒストグラム",
            "箱ひげ図": "箱ひげ図",
            "集計テーブル": "集計テーブル",
            "表示する列を選択してください": "表示する列を選択してください",
            "選択されたデータで相関は計算できませんでした。": "選択されたデータで相関は計算できませんでした。",
            "相関行列": "相関行列",
            "📈 データ分析": "📈 データ分析",
            "📊 データ管理": "📊 データ管理",
            "## 🔍 フィルター設定": "## 🔍 フィルター設定",
            "参加者属性": "参加者属性",
            "参加者層が選択されていません。全ての参加者層のデータが表示されます。": "参加者層が選択されていません。全ての参加者層のデータが表示されます。",
            "選択されたファイルがありません。": "選択されたファイルがありません。",
            "処理するファイルを選択してください。": "処理するファイルを選択してください。",
            "ファイルを処理": "ファイルを処理",
            "以下の列が数値型ではありません。分析する前に変換してください: ": "以下の列が数値型ではありません。分析する前に変換してください: ",
            "選択されたファイルが正常に処理されました。": "選択されたファイルが正常に処理されました。",
            "VRイベント名": "VRイベント名",
            "イベント名が選択されていません。全てのイベントのデータが表示されます。": "イベント名が選択されていません。全てのイベントのデータが表示されます。",
            "選択されたデータがありません。": "選択されたデータがありません。",
            "言語設定": "言語設定",
            "日本語": "日本語",
            "英語": "英語",
            "「担当チーム」の列が見つかりませんでした。": "「担当チーム」の列が見つかりませんでした。",
            "「参加者数」の列が見つかりませんでした。": "「参加者数」の列が見つかりませんでした。",
            "「リアクション率」の列が見つかりませんでした。": "「リアクション率」の列が見つかりませんでした。",
            "「リアクション率」と「参加者数」の相関: ": "「リアクション率」と「参加者数」の相関: ",
            "「リアクション率」と「参加者数」の相関は計算できませんでした（データ不足または定数）。": "「リアクション率」と「参加者数」の相関は計算できませんでした（データ不足または定数）。",
            "担当チーム": "担当チーム",
            "参加者層": "参加者層",
            "イベント名": "イベント名",
            "「合計滞在時間」の列が見つかりませんでした。": "「合計滞在時間」の列が見つかりませんでした。",
            "「VRデバイス利用者数」の列が見つかりませんでした。": "「VRデバイス利用者数」の列が見つかりませんでした。",
            "「合計滞在時間」と「VRデバイス利用者数」の相関: ": "「合計滞在時間」と「VRデバイス利用者数」の相関: ",
            "「合計滞在時間」と「VRデバイス利用者数」の相関は計算できませんでした（データ不足または定数）。": "「合計滞在時間」と「VRデバイス利用者数」の相関は計算できませんでした（データ不足または定数）。",
            "## データクレンジング": "## データクレンジング",
            "元の列": "元の列",
            "新しい列名": "新しい列名",
            "変更": "変更",
            "新しい列名を入力してください。": "新しい列名を入力してください。",
            "列名が変更されました。": "列名が変更されました。",
            "列を削除": "列を削除",
            "列が削除されました。": "列が削除されました。",
            "新しい値": "新しい値",
            "値を置換": "値を置換",
            "置換する元の値を入力してください。": "置換する元の値を入力してください。",
            "置換する新しい値を入力してください。": "置換する新しい値を入力してください。",
            "値が置換されました。": "値が置換されました。",
            "CSVをダウンロード": "CSVをダウンロード",
            "処理済みデータダウンロード": "処理済みデータダウンロード",
            "相関分析のサマリー": "相関分析のサマリー",
            "データ概要": "データ概要",
            "ユニークなイベント数": "ユニークなイベント数",
            "合計参加者数": "合計参加者数",
            "平均滞在時間（分）": "平均滞在時間（分）",
            "VRデバイス平均利用率（%）": "VRデバイス平均利用率（%）",
            "VRデバイス利用者数": "VRデバイス利用者数",
            "参加者数": "参加者数",
            "リアクション率": "リアクション率",
            "合計滞在時間（分）": "合計滞在時間（分）",
            "データに「合計滞在時間」列が見つかりません。": "データに「合計滞在時間」列が見つかりません。",
            "データに「VRデバイス利用者数」列が見つかりません。": "データに「VRデバイス利用者数」列が見つかりません。",
            "データに「参加者数」列が見つかりません。": "データに「参加者数」列が見つかりません。",
            "データに「リアクション率」列が見つかりません。": "データに「リアクション率」列が見つかりません。",
            "データに「イベント名」列が見つかりません。": "データに「イベント名」列が見つかりません。",
            "データに「開催日」列が見つかりません。": "データに「開催日」列が見つかりません。",
            "イベント日": "イベント日",
            "タイムゾーン変換": "タイムゾーン変換",
            "データ変換": "データ変換",
            "日付列 '開催日' のデータ型変換に失敗しました。": "日付列 '開催日' のデータ型変換に失敗しました。",
            "タイムゾーン変換に失敗しました。": "タイムゾーン変換に失敗しました。",
            "日付列 '開催日' が見つかりませんでした。": "日付列 '開催日' が見つかりませんでした。",
            "データ型変換に失敗しました。": "データ型変換に失敗しました。",
            "正常に変換されました。": "正常に変換されました。",
            "列のデータ型を変更": "列のデータ型を変更",
            "選択された列": "選択された列",
            "新しいデータ型": "新しいデータ型",
            "適用": "適用",
            "データ型を変更する列を選択してください。": "データ型を変更する列を選択してください。",
            "データ型が変更されました。": "データ型が変更されました。",
            "以下の列が数値型ではありません。分析する前に変換してください。": "以下の列が数値型ではありません。分析する前に変換してください。",
            "データ型変換に関する注意": "データ型変換に関する注意",
            "ヒント: 「参加者数」や「リアクション率」などの数値データを含む列は、分析の前に数値型 (例: float) に変換することをお勧めします。そうしないと、グラフや相関分析が正しく機能しない場合があります。": "ヒント: 「参加者数」や「リアクション率」などの数値データを含む列は、分析の前に数値型 (例: float) に変換することをお勧めします。そうしないと、グラフや相関分析が正しく機能しない場合があります。",
            "アップロードされたファイルは処理されていません。データ管理タブでファイルを処理してください。": "アップロードされたファイルは処理されていません。データ管理タブでファイルを処理してください。",
            "処理済みのデータをロード": "処理済みのデータをロード",
            "処理済みのデータがありません。": "処理済みのデータがありません。",
            "データ読み込み": "データ読み込み",
            "処理済みデータのロードに成功しました。": "処理済みデータのロードに成功しました。",
        }
    else:
        translations = {
            "VRイベント分析ツール": "VR Event Analysis Tool",
            "パスワードをリセット": "Reset Password",
            "登録": "Register",
            "パスワードが一致しません。": "Passwords do not match.",
            "ユーザー登録が完了しました。": "User registration complete.",
            "ユーザー登録": "User Registration",
            "新しいパスワード": "New Password",
            "パスワード（確認用）": "Confirm Password",
            "ユーザー名": "Username",
            "パスワード": "Password",
            "ログイン": "Login",
            "ユーザー名またはパスワードが間違っています。": "Incorrect username or password.",
            "ログインしていません。": "Not logged in.",
            "ログアウト": "Logout",
            "データ管理": "Data Management",
            "データ分析": "Data Analysis",
            "ユーザー: ": "User: ",
            "ファイルをアップロード（CSV形式）": "Upload Files (CSV format)",
            "CSVファイルをアップロードしてください。": "Please upload CSV files.",
            "アップロードされたファイル": "Uploaded Files",
            "ファイル名": "File Name",
            "削除": "Delete",
            "ファイルの形式が正しくありません。CSVファイルを選択してください。": "Incorrect file format. Please select CSV files.",
            "ファイルが正常にアップロードされました。": "Files uploaded successfully.",
            "データがアップロードされていません。": "No data uploaded.",
            "日付範囲フィルター": "Date Range Filter",
            "開始日": "Start Date",
            "終了日": "End Date",
            "日付データがありません。": "No date data available.",
            "日付列が見つかりませんでした。": "Date column not found.",
            "日付範囲をリセット": "Reset Date Range",
            "担当チームが選択されていません。全ての担当チームのデータが表示されます。": "No teams selected. Data for all teams will be displayed.",
            "データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。": "No data uploaded or filtered out. Please upload files in the Data Management tab.",
            "ヒートマップ": "Heatmap",
            "選択された列": "Selected Columns",
            "最小値": "Min Value",
            "最大値": "Max Value",
            "ヒストグラム": "Histogram",
            "箱ひげ図": "Box Plot",
            "集計テーブル": "Summary Table",
            "表示する列を選択してください": "Select columns to display",
            "選択されたデータで相関は計算できませんでした。": "Correlation could not be calculated for the selected data.",
            "相関行列": "Correlation Matrix",
            "📈 データ分析": "📈 Data Analysis",
            "📊 データ管理": "📊 Data Management",
            "## 🔍 フィルター設定": "## 🔍 Filter Settings",
            "参加者属性": "Participant Attributes",
            "参加者層が選択されていません。全ての参加者層のデータが表示されます。": "No participant segments selected. Data for all segments will be displayed.",
            "選択されたファイルがありません。": "No files selected.",
            "処理するファイルを選択してください。": "Please select files to process.",
            "ファイルを処理": "Process Files",
            "以下の列が数値型ではありません。分析する前に変換してください: ": "The following columns are not numeric. Please convert them before analysis: ",
            "選択されたファイルが正常に処理されました。": "Selected files processed successfully.",
            "VRイベント名": "VR Event Name",
            "イベント名が選択されていません。全てのイベントのデータが表示されます。": "No event names selected. Data for all events will be displayed.",
            "選択されたデータがありません。": "No data selected.",
            "言語設定": "Language Settings",
            "日本語": "Japanese",
            "英語": "English",
            "「担当チーム」の列が見つかりませんでした。": "Column '担当チーム' not found.",
            "「参加者数」の列が見つかりませんでした。": "Column '参加者数' not found.",
            "「リアクション率」の列が見つかりませんでした。": "Column 'リアクション率' not found.",
            "「リアクション率」と「参加者数」の相関: ": "Correlation between 'リアクション率' and '参加者数': ",
            "「リアクション率」と「参加者数」の相関は計算できませんでした（データ不足または定数）。": "Correlation between 'リアクション率' and '参加者数' could not be calculated (insufficient or constant data).",
            "担当チーム": "Team in Charge",
            "参加者層": "Participant Segment",
            "イベント名": "Event Name",
            "「合計滞在時間」の列が見つかりませんでした。": "Column '合計滞在時間' not found.",
            "「VRデバイス利用者数」の列が見つかりませんでした。": "Column 'VRデバイス利用者数' not found.",
            "「合計滞在時間」と「VRデバイス利用者数」の相関: ": "Correlation between '合計滞在時間' and 'VRデバイス利用者数': ",
            "「合計滞在時間」と「VRデバイス利用者数」の相関は計算できませんでした（データ不足または定数）。": "Correlation between '合計滞在時間' and 'VRデバイス利用者数' could not be calculated (insufficient or constant data).",
            "## データクレンジング": "## Data Cleansing",
            "元の列": "Original Column",
            "新しい列名": "New Column Name",
            "変更": "Change",
            "新しい列名を入力してください。": "Please enter a new column name.",
            "列名が変更されました。": "Column name changed.",
            "列を削除": "Delete Column",
            "列が削除されました。": "Column deleted.",
            "新しい値": "New Value",
            "値を置換": "Replace Value",
            "置換する元の値を入力してください。": "Enter value to replace.",
            "置換する新しい値を入力してください。": "Enter new value.",
            "値が置換されました。": "Value replaced.",
            "CSVをダウンロード": "Download CSV",
            "処理済みデータダウンロード": "Processed Data Download",
            "相関分析のサマリー": "Correlation Analysis Summary",
            "データ概要": "Data Overview",
            "ユニークなイベント数": "Unique Events",
            "合計参加者数": "Total Participants",
            "平均滞在時間（分）": "Average Stay Duration (min)",
            "VRデバイス平均利用率（%）": "Average VR Device Usage Rate (%)",
            "VRデバイス利用者数": "VR Device Users",
            "参加者数": "Participants",
            "リアクション率": "Reaction Rate",
            "合計滞在時間（分）": "Total Stay Duration (min)",
            "データに「合計滞在時間」列が見つかりません。": "Column '合計滞在時間' not found in data.",
            "データに「VRデバイス利用者数」列が見つかりません。": "Column 'VRデバイス利用者数' not found in data.",
            "データに「参加者数」列が見つかりません。": "Column '参加者数' not found in data.",
            "データに「リアクション率」列が見つかりません。": "Column 'リアクション率' not found in data.",
            "データに「イベント名」列が見つかりません。": "Column 'イベント名' not found in data.",
            "データに「開催日」列が見つかりません。": "Column '開催日' not found in data.",
            "イベント日": "Event Date",
            "タイムゾーン変換": "Timezone Conversion",
            "データ変換": "Data Conversion",
            "日付列 '開催日' のデータ型変換に失敗しました。": "Failed to convert data type of date column '開催日'.",
            "タイムゾーン変換に失敗しました。": "Timezone conversion failed.",
            "日付列 '開催日' が見つかりませんでした。": "Date column '開催日' not found.",
            "データ型変換に失敗しました。": "Data type conversion failed.",
            "正常に変換されました。": "Converted successfully.",
            "列のデータ型を変更": "Change Column Data Type",
            "選択された列": "Selected Column",
            "新しいデータ型": "New Data Type",
            "適用": "Apply",
            "データ型を変更する列を選択してください。": "Please select a column to change its data type.",
            "データ型が変更されました。": "Data type changed.",
            "以下の列が数値型ではありません。分析する前に変換してください。": "The following columns are not numeric. Please convert them before analysis.",
            "データ型変換に関する注意": "Note on Data Type Conversion",
            "ヒント: 「参加者数」や「リアクション率」などの数値データを含む列は、分析の前に数値型 (例: float) に変換することをお勧めします。そうしないと、グラフや相関分析が正しく機能しない場合があります。": "Hint: Columns containing numerical data like '参加者数' (Number of Participants) or 'リアクション率' (Reaction Rate) are recommended to be converted to a numeric type (e.g., float) before analysis. Otherwise, graphs and correlation analysis may not function correctly.",
            "アップロードされたファイルは処理されていません。データ管理タブでファイルを処理してください。": "Uploaded files have not been processed. Please process files in the Data Management tab.",
            "処理済みのデータをロード": "Load Processed Data",
            "処理済みのデータがありません。": "No processed data available.",
            "データ読み込み": "Load Data",
            "処理済みデータのロードに成功しました。": "Successfully loaded processed data.",
        }
    return translations.get(key, key) # キーが見つからない場合はキー自体を返す

# --- ログイン/登録ページ ---
def show_login_page():
    st.title(get_localized_text("VRイベント分析ツール"))

    if 'language' not in st.session_state:
        st.session_state['language'] = 'ja' # デフォルトは日本語

    # 言語選択ラジオボタンをログインページにも追加
    language_choice = st.radio(
        get_localized_text("言語設定"),
        ('ja', 'en'),
        format_func=lambda x: get_localized_text("日本語") if x == 'ja' else get_localized_text("英語"),
        key="login_language_radio"
    )
    if language_choice != st.session_state['language']:
        st.session_state['language'] = language_choice
        st.rerun() # 言語変更時にページを再描画

    st.subheader(get_localized_text("ログイン"))
    
    username = st.text_input(get_localized_text("ユーザー名"), key="login_username")
    password = st.text_input(get_localized_text("パスワード"), type="password", key="login_password")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(get_localized_text("ログイン"), key="login_button"):
            users = load_users()
            if username in users and check_password(password, users[username]):
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.session_state["page"] = "data_management" # ログイン成功後、データ管理ページへ
                st.rerun()
            else:
                st.error(get_localized_text("ユーザー名またはパスワードが間違っています。"))

    with col2:
        if st.button(get_localized_text("登録"), key="register_button"):
            st.session_state["show_register"] = True
            st.rerun()
    
    with col3:
        if st.button(get_localized_text("パスワードをリセット"), key="reset_password_button"):
            st.session_state["show_reset_password"] = True
            st.rerun()


    if st.session_state.get("show_register"):
        st.subheader(get_localized_text("ユーザー登録"))
        new_username = st.text_input(get_localized_text("ユーザー名"), key="new_username")
        new_password = st.text_input(get_localized_text("パスワード"), type="password", key="new_password")
        confirm_password = st.text_input(get_localized_text("パスワード（確認用）"), type="password", key="confirm_password")

        if st.button(get_localized_text("登録"), key="submit_register"):
            if new_password == confirm_password:
                users = load_users()
                if new_username in users:
                    st.error(get_localized_text("このユーザー名は既に存在します。"))
                else:
                    users[new_username] = hash_password(new_password)
                    save_users(users)
                    st.success(get_localized_text("ユーザー登録が完了しました。"))
                    st.session_state["show_register"] = False
                    st.rerun()
            else:
                st.error(get_localized_text("パスワードが一致しません。"))

    if st.session_state.get("show_reset_password"):
        st.subheader(get_localized_text("パスワードをリセット"))
        reset_username = st.text_input(get_localized_text("ユーザー名"), key="reset_username")
        new_password_reset = st.text_input(get_localized_text("新しいパスワード"), type="password", key="new_password_reset")
        confirm_password_reset = st.text_input(get_localized_text("パスワード（確認用）"), type="password", key="confirm_password_reset")

        if st.button(get_localized_text("パスワードをリセット"), key="submit_reset_password"):
            users = load_users()
            if reset_username not in users:
                st.error(get_localized_text("ユーザーが見つかりません。"))
            elif new_password_reset != confirm_password_reset:
                st.error(get_localized_text("パスワードが一致しません。"))
            else:
                users[reset_username] = hash_password(new_password_reset)
                save_users(users)
                st.success(get_localized_text("パスワードがリセットされました。"))
                st.session_state["show_reset_password"] = False
                st.rerun()

# --- データ管理ページ ---
def show_data_management_page():
    st.title(get_localized_text("📊 データ管理"))
    
    st.markdown(get_localized_text("## データクレンジング"))
    
    # 既存の uploaded_files をセッションステートから取得、なければ空のリスト
    if 'uploaded_files_data' not in st.session_state:
        st.session_state.uploaded_files_data = []

    uploaded_files_current_run = st.file_uploader(
        get_localized_text("ファイルをアップロード（CSV形式）"), 
        type="csv", 
        accept_multiple_files=True,
        key="file_uploader"
    )

    # 新しくアップロードされたファイルがある場合
    if uploaded_files_current_run:
        # 新しいファイルのファイル名をリストアップ
        new_file_names = [f.name for f in uploaded_files_current_run]
        # 既存のファイル名を取得
        existing_file_names = [f_data['name'] for f_data in st.session_state.uploaded_files_data]
        
        # 新しいファイルで、かつ既存リストにないものだけを追加
        files_to_add = []
        for uploaded_file in uploaded_files_current_run:
            if uploaded_file.name not in existing_file_names:
                # ファイルの内容をBytesIOで保持
                file_content = uploaded_file.read()
                files_to_add.append({
                    'name': uploaded_file.name,
                    'content': file_content,
                    'processed': False # 初期状態では未処理
                })
        
        if files_to_add:
            st.session_state.uploaded_files_data.extend(files_to_add)
            st.success(get_localized_text("ファイルが正常にアップロードされました。"))
            # アップロード後にファイル一覧を更新するため再実行
            st.rerun()

    st.markdown("---")
    st.subheader(get_localized_text("アップロードされたファイル"))

    if not st.session_state.uploaded_files_data:
        st.info(get_localized_text("データがアップロードされていません。"))
    else:
        file_names_to_display = [f_data['name'] for f_data in st.session_state.uploaded_files_data]
        
        # 処理するファイルの選択
        if 'selected_files_to_process' not in st.session_state:
            st.session_state.selected_files_to_process = []

        # Streamlitのファイルアップローダーは、同じファイル名で複数回アップロードされると
        # 内部的に新しいオブジェクトとして扱うため、ファイル名で重複排除し、既存リストを更新する
        st.session_state.uploaded_files_data = [
            file_data for file_data in st.session_state.uploaded_files_data
            if file_data['name'] in file_names_to_display # 実際に表示されているファイル名に含まれるものだけ残す
        ]

        if not st.session_state.uploaded_files_data:
            st.info(get_localized_text("選択されたファイルがありません。"))
        else:
            df_files = pd.DataFrame(st.session_state.uploaded_files_data)
            df_files['processed_status'] = df_files['processed'].apply(lambda x: '✔' if x else ' ')

            # 表示用のデータフレームを作成し、チェックボックスとファイル名、処理ステータスを表示
            display_df = pd.DataFrame({
                get_localized_text("ファイル名"): df_files['name'],
                get_localized_text("処理済み"): df_files['processed_status']
            })
            
            st.dataframe(display_df, hide_index=True, use_container_width=True)

            # 処理対象ファイルを選択するmultiselect
            selected_files_for_processing = st.multiselect(
                get_localized_text("処理するファイルを選択してください。"),
                options=[f_data['name'] for f_data in st.session_state.uploaded_files_data],
                default=st.session_state.selected_files_to_process,
                key="process_file_multiselect"
            )
            st.session_state.selected_files_to_process = selected_files_for_processing

            col_process, col_delete = st.columns([1, 1])

            with col_process:
                if st.button(get_localized_text("ファイルを処理"), key="process_selected_files_button"):
                    if not st.session_state.selected_files_to_process:
                        st.warning(get_localized_text("処理するファイルを選択してください。"))
                    else:
                        combined_df = pd.DataFrame()
                        processed_file_names = []
                        for file_data in st.session_state.uploaded_files_data:
                            if file_data['name'] in st.session_state.selected_files_to_process:
                                try:
                                    # BytesIOからDataFrameを読み込む
                                    df = pd.read_csv(io.BytesIO(file_data['content']))
                                    combined_df = pd.concat([combined_df, df], ignore_index=True)
                                    processed_file_names.append(file_data['name'])
                                    # 処理済みフラグを立てる
                                    file_data['processed'] = True
                                except Exception as e:
                                    st.error(f"Error processing {file_data['name']}: {e}")
                                    file_data['processed'] = False # 処理失敗

                        if not combined_df.empty:
                            st.session_state['dfmain'] = combined_df
                            st.session_state['current_data'] = combined_df.copy() # データクレンジング用
                            st.session_state['processed_data_available'] = True
                            st.success(get_localized_text("選択されたファイルが正常に処理されました。"))
                            # データ型変換のヒントを表示するためにチェック
                            check_and_warn_non_numeric_columns(combined_df)
                            st.rerun() # 処理後にUIを更新するため
                        else:
                            st.warning(get_localized_text("選択されたデータがありません。"))
                            st.session_state['processed_data_available'] = False
            
            with col_delete:
                # 削除ボタンと削除するファイルの選択
                if st.button(get_localized_text("削除"), key="delete_selected_files_button"):
                    if not st.session_state.selected_files_to_process:
                        st.warning(get_localized_text("処理するファイルを選択してください。"))
                    else:
                        st.session_state.uploaded_files_data = [
                            f_data for f_data in st.session_state.uploaded_files_data 
                            if f_data['name'] not in st.session_state.selected_files_to_process
                        ]
                        st.session_state.selected_files_to_process = [] # 選択をクリア
                        # もし削除によってdfmainが空になるならクリア
                        if not st.session_state.uploaded_files_data:
                            if 'dfmain' in st.session_state:
                                del st.session_state['dfmain']
                            if 'current_data' in st.session_state:
                                del st.session_state['current_data']
                            st.session_state['processed_data_available'] = False
                        st.success(get_localized_text("ファイルが削除されました。"))
                        st.rerun() # 削除後にUIを更新するため

    st.markdown("---")
    st.subheader(get_localized_text("データ変換"))

    if 'current_data' in st.session_state and not st.session_state.current_data.empty:
        df_display = st.session_state.current_data.copy()
        
        st.dataframe(df_display, use_container_width=True, height=300)

        # データ型変換に関する注意喚起
        st.markdown(f"**{get_localized_text('データ型変換に関する注意')}**")
        st.info(get_localized_text("ヒント: 「参加者数」や「リアクション率」などの数値データを含む列は、分析の前に数値型 (例: float) に変換することをお勧めします。そうしないと、グラフや相関分析が正しく機能しない場合があります。"))

        st.markdown("---")
        st.subheader(get_localized_text("列のデータ型を変更"))
        
        col_type_1, col_type_2, col_type_3 = st.columns(3)
        with col_type_1:
            column_to_convert = st.selectbox(
                get_localized_text("選択された列"), 
                options=[''] + list(df_display.columns), 
                key="column_to_convert_selectbox"
            )
        with col_type_2:
            new_data_type = st.selectbox(
                get_localized_text("新しいデータ型"), 
                options=['', 'int', 'float', 'str', 'datetime'], 
                key="new_data_type_selectbox"
            )
        with col_type_3:
            st.markdown("<br>", unsafe_allow_html=True) # スペース調整
            if st.button(get_localized_text("適用"), key="apply_data_type_button"):
                if column_to_convert and new_data_type:
                    try:
                        if new_data_type == 'datetime':
                            st.session_state.current_data[column_to_convert] = pd.to_datetime(st.session_state.current_data[column_to_convert], errors='coerce')
                        elif new_data_type == 'int':
                            # NaNがある場合はまずfloatに変換してからintに変換
                            st.session_state.current_data[column_to_convert] = pd.to_numeric(st.session_state.current_data[column_to_convert], errors='coerce')
                            st.session_state.current_data[column_to_convert] = st.session_state.current_data[column_to_convert].fillna(0).astype(int) # NaNを0で埋めてからint
                        else:
                            st.session_state.current_data[column_to_convert] = st.session_state.current_data[column_to_convert].astype(new_data_type)
                        st.success(get_localized_text("データ型が変更されました。"))
                        st.rerun() # 変更を適用して再描画
                    except Exception as e:
                        st.error(f"{get_localized_text('データ型変換に失敗しました。')} {e}")
                else:
                    st.warning(get_localized_text("データ型を変更する列を選択してください。"))


        st.markdown("---")
        st.subheader(get_localized_text("列名の変更と削除"))
        col_rename, col_delete_col = st.columns(2)

        with col_rename:
            column_to_rename = st.selectbox(get_localized_text("元の列"), options=[''] + list(df_display.columns), key="rename_select")
            new_column_name = st.text_input(get_localized_text("新しい列名"), key="new_column_name_input")
            if st.button(get_localized_text("変更"), key="rename_button"):
                if column_to_rename and new_column_name:
                    if new_column_name in df_display.columns:
                        st.error(get_localized_text("その列名は既に存在します。"))
                    else:
                        st.session_state.current_data.rename(columns={column_to_rename: new_column_name}, inplace=True)
                        st.success(get_localized_text("列名が変更されました。"))
                        st.rerun()
                else:
                    st.warning(get_localized_text("新しい列名を入力してください。"))

        with col_delete_col:
            column_to_delete = st.selectbox(get_localized_text("列を削除"), options=[''] + list(df_display.columns), key="delete_column_select")
            if st.button(get_localized_text("列を削除"), key="delete_column_button"):
                if column_to_delete:
                    st.session_state.current_data.drop(columns=[column_to_delete], inplace=True)
                    st.success(get_localized_text("列が削除されました。"))
                    st.rerun()
                else:
                    st.warning(get_localized_text("削除する列を選択してください。"))

        st.markdown("---")
        st.subheader(get_localized_text("値の置換"))
        col_replace_1, col_replace_2, col_replace_3 = st.columns(3)
        with col_replace_1:
            column_to_replace = st.selectbox(
                get_localized_text("選択された列"), 
                options=[''] + list(df_display.columns), 
                key="column_to_replace_selectbox"
            )
        with col_replace_2:
            old_value = st.text_input(get_localized_text("元の値"), key="old_value_input")
        with col_replace_3:
            new_value = st.text_input(get_localized_text("新しい値"), key="new_value_input")
            if st.button(get_localized_text("値を置換"), key="replace_value_button"):
                if column_to_replace and old_value is not None and new_value is not None:
                    # 数値型に変換可能な場合は数値として比較・置換
                    try:
                        old_val_num = float(old_value)
                        new_val_num = float(new_value)
                        # 列のデータ型が数値型の場合に数値として置換を試みる
                        if pd.api.types.is_numeric_dtype(st.session_state.current_data[column_to_replace]):
                            st.session_state.current_data[column_to_replace] = st.session_state.current_data[column_to_replace].replace(old_val_num, new_val_num)
                        else: # 数値型でない場合は文字列として置換
                             st.session_state.current_data[column_to_replace] = st.session_state.current_data[column_to_replace].astype(str).replace(old_value, new_value)
                    except ValueError: # 数値型に変換できない場合は文字列として置換
                        st.session_state.current_data[column_to_replace] = st.session_state.current_data[column_to_replace].astype(str).replace(old_value, new_value)
                    
                    st.success(get_localized_text("値が置換されました。"))
                    st.rerun()
                else:
                    st.warning(get_localized_text("置換する元の値と新しい値を入力してください。"))

        st.markdown("---")
        st.subheader(get_localized_text("タイムゾーン変換"))
        if '開催日' in st.session_state.current_data.columns:
            st.info(get_localized_text("日付列 '開催日' が見つかりました。タイムゾーン変換が可能です。"))
            if st.button(get_localized_text("タイムゾーン変換"), key="convert_timezone_button"):
                try:
                    # まず datetime に変換（errors='coerce' で変換できない値をNaTにする）
                    st.session_state.current_data['開催日'] = pd.to_datetime(st.session_state.current_data['開催日'], errors='coerce')
                    # NaTを削除または処理することも検討（ここではそのまま）

                    # タイムゾーン情報を付与 (UTCと仮定)
                    st.session_state.current_data['開催日'] = st.session_state.current_data['開催日'].dt.tz_localize('UTC', errors='coerce')

                    # 日本時間 (JST) に変換
                    st.session_state.current_data['開催日'] = st.session_state.current_data['開催日'].dt.tz_convert('Asia/Tokyo')
                    st.success(get_localized_text("正常に変換されました。"))
                    st.rerun()
                except KeyError:
                    st.error(get_localized_text("日付列 '開催日' が見つかりませんでした。"))
                except Exception as e:
                    st.error(f"{get_localized_text('タイムゾーン変換に失敗しました。')} {e}")
        else:
            st.info(get_localized_text("日付列 '開催日' が見つかりませんでした。"))

        st.markdown("---")
        st.subheader(get_localized_text("処理済みデータダウンロード"))
        # current_data が存在し、空ではない場合にダウンロードボタンを表示
        if 'current_data' in st.session_state and not st.session_state.current_data.empty:
            csv_data = st.session_state.current_data.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label=get_localized_text("CSVをダウンロード"),
                data=csv_data,
                file_name="processed_data.csv",
                mime="text/csv",
                key="download_processed_csv"
            )
    else:
        st.info(get_localized_text("処理済みのデータがありません。"))

# 数値型でない列をチェックし警告する関数
def check_and_warn_non_numeric_columns(df):
    non_numeric_cols = []
    for col in df.columns:
        # 'datetime'型はここでは数値型として扱わない
        if not pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_datetime64_any_dtype(df[col]):
            non_numeric_cols.append(col)
    
    if non_numeric_cols:
        st.warning(get_localized_text("以下の列が数値型ではありません。分析する前に変換してください: ") + ", ".join(non_numeric_cols))


# --- データ分析ページ ---
def show_main_app():
    st.title(get_localized_text("📈 データ分析"))

    # データがロードされていない場合の警告
    if 'dfmain' not in st.session_state or st.session_state['dfmain'].empty:
        st.warning(get_localized_text("アップロードされたファイルは処理されていません。データ管理タブでファイルを処理してください。"))
        if st.button(get_localized_text("処理済みのデータをロード"), key="load_processed_data_button"):
            if 'current_data' in st.session_state and not st.session_state.current_data.empty:
                st.session_state['dfmain'] = st.session_state.current_data.copy()
                st.session_state['processed_data_available'] = True
                st.success(get_localized_text("処理済みデータのロードに成功しました。"))
                st.rerun()
            else:
                st.error(get_localized_text("処理済みのデータがありません。"))
        return # データがない場合はここで処理を中断

    # サイドバーのフィルター設定
    with st.sidebar:
        st.markdown(get_localized_text("## 🔍 フィルター設定"))
        st.markdown("---")

        dfmain_for_sidebar = st.session_state.get('dfmain')
        df_filtered = dfmain_for_sidebar.copy() # フィルター適用のためコピー

        # 日付フィルター
        if '開催日' in df_filtered.columns:
            try:
                # 日付列をdatetime型に変換
                df_filtered['開催日'] = pd.to_datetime(df_filtered['開催日'], errors='coerce')
                # 無効な日付（NaT）を除外
                df_filtered.dropna(subset=['開催日'], inplace=True)

                if not df_filtered['開催日'].empty:
                    min_date = df_filtered['開催日'].min().date()
                    max_date = df_filtered['開催日'].max().date()

                    if 'date_range' not in st.session_state:
                        st.session_state.date_range = (min_date, max_date)

                    st.subheader(get_localized_text("イベント日"))
                    start_date, end_date = st.date_input(
                        get_localized_text("日付範囲フィルター"),
                        value=st.session_state.date_range,
                        min_value=min_date,
                        max_value=max_date,
                        key="date_filter"
                    )
                    
                    st.session_state.date_range = (start_date, end_date)

                    df_filtered = df_filtered[(df_filtered['開催日'].dt.date >= start_date) & 
                                              (df_filtered['開催日'].dt.date <= end_date)]
                    
                    if st.button(get_localized_text("日付範囲をリセット"), key="reset_date_filter"):
                        st.session_state.date_range = (min_date, max_date)
                        st.rerun() # リセット後に再実行してフィルターを適用
                else:
                    st.info(get_localized_text("日付データがありません。"))
            except Exception as e:
                st.warning(f"{get_localized_text('日付列「開催日」の処理中にエラーが発生しました。日付形式を確認してください。')} {e}")
                st.info(get_localized_text("日付列が見つかりませんでした。"))
        else:
            st.info(get_localized_text("日付列が見つかりませんでした。"))

        # 担当チームフィルター
        if '担当チーム' in df_filtered.columns:
            teams = sorted(df_filtered['担当チーム'].dropna().unique())
            
            # selected_teams の初期値をセッションステートから取得、なければ全選択
            initial_selected_teams = st.session_state.get('selected_teams')
            if initial_selected_teams is None:
                initial_selected_teams = teams # 初回ロード時は全てのチームを選択

            # multiselect の default には、現在有効なチームリストに含まれるものだけを渡す
            current_valid_selection = [t for t in initial_selected_teams if t in teams]

            selected_teams_from_widget = st.multiselect(
                get_localized_text("👥 担当チーム"), 
                teams, 
                default=current_valid_selection,
                key="team_multiselect" # 明示的なキーを追加
            )

            # ウィジェットの選択が変更された場合のみ session_state を更新する
            if selected_teams_from_widget != st.session_state.get('selected_teams'):
                st.session_state.selected_teams = selected_teams_from_widget
                st.rerun() # 変更を即座に反映

            # 担当チームが何も選択されていない場合の動作変更
            if len(st.session_state.selected_teams) == 0: 
                st.warning(get_localized_text("担当チームが選択されていません。全ての担当チームのデータが表示されます。"))
            else:
                df_filtered = df_filtered[df_filtered['担当チーム'].isin(st.session_state.selected_teams)] 
        else:
            st.info(get_localized_text("「担当チーム」の列が見つかりませんでした。"))

        # 参加者層フィルター
        if '参加者層' in df_filtered.columns:
            participant_segments = sorted(df_filtered['参加者層'].dropna().unique())
            if 'selected_participant_segments' not in st.session_state:
                st.session_state.selected_participant_segments = participant_segments

            selected_segments = st.multiselect(
                get_localized_text("参加者属性"),
                participant_segments,
                default=st.session_state.selected_participant_segments,
                key="participant_segment_multiselect"
            )
            st.session_state.selected_participant_segments = selected_segments

            if len(st.session_state.selected_participant_segments) == 0:
                st.warning(get_localized_text("参加者層が選択されていません。全ての参加者層のデータが表示されます。"))
            else:
                df_filtered = df_filtered[df_filtered['参加者層'].isin(st.session_state.selected_participant_segments)]
        else:
            st.info(get_localized_text("「参加者層」の列が見つかりませんでした。"))

        # VRイベント名フィルター
        if 'VRイベント名' in df_filtered.columns:
            event_names = sorted(df_filtered['VRイベント名'].dropna().unique())
            if 'selected_event_names' not in st.session_state:
                st.session_state.selected_event_names = event_names
            
            selected_events = st.multiselect(
                get_localized_text("イベント名"),
                event_names,
                default=st.session_state.selected_event_names,
                key="event_name_multiselect"
            )
            st.session_state.selected_event_names = selected_events

            if len(st.session_state.selected_event_names) == 0:
                st.warning(get_localized_text("イベント名が選択されていません。全てのイベントのデータが表示されます。"))
            else:
                df_filtered = df_filtered[df_filtered['VRイベント名'].isin(st.session_state.selected_event_names)]
        else:
            st.info(get_localized_text("「イベント名」の列が見つかりませんでした。"))

    # フィルター適用後のデータが存在するか確認
    if df_filtered.empty:
        st.warning(get_localized_text("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。"))
        return

    # フィルタリングされたデータフレームをメインアプリで使用できるようにセッションステートに保存
    st.session_state['df_filtered'] = df_filtered

    # --- メインコンテンツ ---
    st.markdown("---")
    st.subheader(get_localized_text("データ概要"))
    
    # データ概要の表示
    num_unique_events = df_filtered['VRイベント名'].nunique() if 'VRイベント名' in df_filtered.columns else 0
    total_participants = df_filtered['参加者数'].sum() if '参加者数' in df_filtered.columns and pd.api.types.is_numeric_dtype(df_filtered['参加者数']) else 0
    
    # 平均滞在時間 (分)
    avg_stay_duration = 0
    if '合計滞在時間' in df_filtered.columns and pd.api.types.is_numeric_dtype(df_filtered['合計滞在時間']):
        # 時間が秒単位の場合、分に変換
        if df_filtered['合計滞在時間'].max() > 1440: # 適当な閾値（24時間*60秒）
             avg_stay_duration = df_filtered['合計滞在時間'].mean() / 60 
        else: # 分単位の場合
            avg_stay_duration = df_filtered['合計滞在時間'].mean()

    # VRデバイス平均利用率（%）
    avg_vr_device_usage_rate = 0
    if 'VRデバイス利用者数' in df_filtered.columns and '参加者数' in df_filtered.columns:
        if pd.api.types.is_numeric_dtype(df_filtered['VRデバイス利用者数']) and pd.api.types.is_numeric_dtype(df_filtered['参加者数']):
            # 参加者数が0でない場合にのみ計算
            if df_filtered['参加者数'].sum() > 0:
                avg_vr_device_usage_rate = (df_filtered['VRデバイス利用者数'].sum() / df_filtered['参加者数'].sum()) * 100
            else:
                avg_vr_device_usage_rate = 0 # 参加者数が0の場合は0%

    overview_cols = st.columns(4)
    with overview_cols[0]:
        st.metric(get_localized_text("ユニークなイベント数"), f"{num_unique_events:.0f}")
    with overview_cols[1]:
        st.metric(get_localized_text("合計参加者数"), f"{total_participants:.0f}")
    with overview_cols[2]:
        st.metric(get_localized_text("平均滞在時間（分）"), f"{avg_stay_duration:.2f}")
    with overview_cols[3]:
        st.metric(get_localized_text("VRデバイス平均利用率（%）"), f"{avg_vr_device_usage_rate:.2f}%")

    st.markdown("---")
    st.subheader(get_localized_text("相関分析のサマリー"))

    corr_summary_text = []

    # 「合計滞在時間」と「VRデバイス利用者数」の相関
    if '合計滞在時間' in df_filtered.columns and 'VRデバイス利用者数' in df_filtered.columns:
        df_corr = df_filtered[['合計滞在時間', 'VRデバイス利用者数']].dropna()
        if not df_corr.empty and pd.api.types.is_numeric_dtype(df_corr['合計滞在時間']) and pd.api.types.is_numeric_dtype(df_corr['VRデバイス利用者数']):
            corr1 = df_corr['合計滞在時間'].corr(df_corr['VRデバイス利用者数'])
            if pd.notna(corr1):
                corr_summary_text.append(get_localized_text(f"「合計滞在時間」と「VRデバイス利用者数」の相関: {corr1:.2f}"))
            else:
                corr_summary_text.append(get_localized_text("「合計滞在時間」と「VRデバイス利用者数」の相関は計算できませんでした（データ不足または定数）。"))
        else:
            corr_summary_text.append(get_localized_text("「合計滞在時間」または「VRデバイス利用者数」の列が数値型ではありません。"))
    else:
        if '合計滞在時間' not in df_filtered.columns:
            corr_summary_text.append(get_localized_text("「合計滞在時間」の列が見つかりませんでした。"))
        if 'VRデバイス利用者数' not in df_filtered.columns:
            corr_summary_text.append(get_localized_text("「VRデバイス利用者数」の列が見つかりませんでした。"))

    # 「参加者数」と「リアクション率」の相関
    if '参加者数' in df_filtered.columns and 'リアクション率' in df_filtered.columns:
        df_corr = df_filtered[['参加者数', 'リアクション率']].dropna()
        if not df_corr.empty and pd.api.types.is_numeric_dtype(df_corr['参加者数']) and pd.api.types.is_numeric_dtype(df_corr['リアクション率']):
            corr2 = df_corr['参加者数'].corr(df_corr['リアクション率'])
            if pd.notna(corr2):
                corr_summary_text.append(get_localized_text(f"「リアクション率」と「参加者数」の相関: {corr2:.2f}"))
            else:
                corr_summary_text.append(get_localized_text("「リアクション率」と「参加者数」の相関は計算できませんでした（データ不足または定数）。"))
        else:
            corr_summary_text.append(get_localized_text("「参加者数」または「リアクション率」の列が数値型ではありません。"))
    else:
        if '参加者数' not in df_filtered.columns:
            corr_summary_text.append(get_localized_text("「参加者数」の列が見つかりませんでした。"))
        if 'リアクション率' not in df_filtered.columns:
            corr_summary_text.append(get_localized_text("「リアクション率」の列が見つかりませんでした。"))
    
    for line in corr_summary_text:
        st.info(line)
        
    st.markdown("---")
    st.subheader(get_localized_text("データ可視化"))

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        get_localized_text("ヒートマップ"), 
        get_localized_text("ヒストグラム"), 
        get_localized_text("箱ひげ図"), 
        get_localized_text("相関行列"), 
        get_localized_text("集計テーブル")
    ])

    with tab1: # ヒートマップ
        st.subheader(get_localized_text("ヒートマップ"))
        numeric_cols = df_filtered.select_dtypes(include=np.number).columns.tolist()
        
        if not numeric_cols:
            st.warning(get_localized_text("選択されたデータで相関は計算できませんでした。"))
        else:
            heatmap_cols = st.multiselect(get_localized_text("選択された列"), numeric_cols, default=numeric_cols, key="heatmap_cols_multiselect")
            if heatmap_cols:
                fig, ax = plt.subplots(figsize=(10, 8))
                sns.heatmap(df_filtered[heatmap_cols].corr(), annot=True, cmap='coolwarm', ax=ax)
                st.pyplot(fig)
            else:
                st.info(get_localized_text("表示する列を選択してください"))

    with tab2: # ヒストグラム
        st.subheader(get_localized_text("ヒストグラム"))
        numeric_cols = df_filtered.select_dtypes(include=np.number).columns.tolist()
        
        if not numeric_cols:
            st.warning(get_localized_text("選択されたデータがありません。"))
        else:
            hist_column = st.selectbox(get_localized_text("選択された列"), numeric_cols, key="hist_column_select")
            if hist_column:
                bins = st.slider("Bin数", min_value=5, max_value=50, value=20, key="hist_bins_slider")
                fig, ax = plt.subplots()
                sns.histplot(df_filtered[hist_column].dropna(), bins=bins, kde=True, ax=ax)
                ax.set_title(f'{hist_column} のヒストグラム')
                st.pyplot(fig)

    with tab3: # 箱ひげ図
        st.subheader(get_localized_text("箱ひげ図"))
        numeric_cols = df_filtered.select_dtypes(include=np.number).columns.tolist()
        
        if not numeric_cols:
            st.warning(get_localized_text("選択されたデータがありません。"))
        else:
            box_column = st.selectbox(get_localized_text("選択された列"), numeric_cols, key="box_column_select")
            if box_column:
                fig, ax = plt.subplots()
                sns.boxplot(y=df_filtered[box_column].dropna(), ax=ax)
                ax.set_title(f'{box_column} の箱ひげ図')
                st.pyplot(fig)

    with tab4: # 相関行列
        st.subheader(get_localized_text("相関行列"))
        numeric_cols = df_filtered.select_dtypes(include=np.number).columns.tolist()
        
        if not numeric_cols:
            st.warning(get_localized_text("選択されたデータで相関は計算できませんでした。"))
        else:
            fig, ax = plt.subplots(figsize=(12, 10))
            corr_matrix = df_filtered[numeric_cols].corr()
            sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt=".2f", linewidths=.5, ax=ax)
            ax.set_title(get_localized_text("相関行列"))
            st.pyplot(fig)

    with tab5: # 集計テーブル
        st.subheader(get_localized_text("集計テーブル"))
        st.dataframe(df_filtered, use_container_width=True)

# --- アプリケーションのエントリポイント ---
def main():
    # Streamlitのページ設定は一度だけ行う
    st.set_page_config(page_title=get_localized_text("VRイベント分析ツール"), layout="wide")

    # セッションステートにlogged_inがなければ初期化（アプリケーション起動時にのみFalseに設定）
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    
    # セッションステートに 'page' がなければ 'login' に初期化
    if "page" not in st.session_state:
        st.session_state["page"] = "login"

    # 言語設定がなければ日本語をデフォルトにする
    if 'language' not in st.session_state:
        st.session_state['language'] = 'ja'

    if st.session_state.get("logged_in"):
        # ログイン済みの場合、ユーザー名を表示し、ログアウトボタンとメインアプリを表示
        st.sidebar.write(get_localized_text("ユーザー: ") + st.session_state.username)
        
        # 言語選択をサイドバーに移動
        language_choice = st.sidebar.radio(
            get_localized_text("言語設定"),
            ('ja', 'en'),
            format_func=lambda x: get_localized_text("日本語") if x == 'ja' else get_localized_text("英語"),
            key="main_app_language_radio"
        )
        if language_choice != st.session_state['language']:
            st.session_state['language'] = language_choice
            st.rerun() # 言語変更時にページを再描画

        # ページナビゲーション
        app_page = st.sidebar.radio(
            get_localized_text("データ読み込み"),
            [get_localized_text("データ分析"), get_localized_text("データ管理")],
            key="app_page_radio"
        )

        if app_page == get_localized_text("データ管理"):
            st.session_state["page"] = "data_management"
        elif app_page == get_localized_text("データ分析"):
            st.session_state["page"] = "data_analysis"

        if st.sidebar.button(get_localized_text("ログアウト"), key="logout_button"):
            st.session_state["logged_in"] = False
            st.session_state["username"] = ""
            st.session_state["page"] = "login" # ログアウト後、ログインページへ
            # セッションステートのデータをクリア
            for key in ['dfmain', 'df_filtered', 'current_data', 'uploaded_files_data', 'selected_files_to_process', 'processed_data_available', 'selected_teams', 'selected_participant_segments', 'selected_event_names', 'date_range']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        # 選択されたページを表示
        if st.session_state["page"] == "data_management":
            show_data_management_page()
        elif st.session_state["page"] == "data_analysis":
            show_main_app()

    else:
        # ログインしていない場合
        show_login_page()

if __name__ == "__main__":
    main()
