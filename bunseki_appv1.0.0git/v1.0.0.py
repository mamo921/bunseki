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

# 相対パスで指定（Streamlit Cloudでも通る）
font_path = "bunseki_appv1.0.0git/static/NotoSansJP-VariableFont_wght.otf"
font_prop = fm.FontProperties(fname=font_path)

font_prop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = font_prop.get_name()


# matplotlibのフォント設定
# 負の記号が文字化けするのを防ぐ
plt.rcParams['axes.unicode_minus'] = False

# 日本語フォントの設定をより堅牢にする
# 一般的にStreamlit Cloudで利用可能なフォントを優先
japanese_font_available = False
try:
    # Noto Sans CJK JP を試す
    fm.findfont('Noto Sans CJK JP', fallback_to_default=False)
    plt.rcParams['font.family'] = 'Noto Sans CJK JP'
    plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP']
    japanese_font_available = True
except Exception:
    try:
        # IPAexGothic を試す
        fm.findfont('IPAexGothic', fallback_to_default=False)
        plt.rcParams['font.family'] = 'IPAexGothic'
        plt.rcParams['font.sans-serif'] = ['IPAexGothic']
        japanese_font_available = True
    except Exception:
        # 日本語フォントが見つからない場合の警告
        st.warning("日本語フォントが見つかりませんでした。グラフのラベルは英語で表示されます。")
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans'] # 一般的なフォールバック

# 全体的なフォントサイズを設定（必要に応じて調整）
plt.rcParams['font.size'] = 10

# Helper function for localization (UI elements always in Japanese)
def get_localized_text(jp_text, en_text):
    return jp_text

# Helper function for graph localization (graphs switch to English if Japanese font not available)
def get_graph_text(jp_text, en_text):
    return jp_text


# ページ設定
st.set_page_config(page_title=get_localized_text("VRイベント分析ツール", "VR Event Analysis Tool"), layout="wide")

# --- 認証関連の関数 ---
# パスワードの検証
def verify_password(password, hashed_password):
    return bcrypt.checkpw(password.encode(), hashed_password.encode())

# secrets.tomlからユーザー情報を読み込み
def load_users_from_secrets():
    users = []
    try:
        for _, user in st.secrets["users"].items():
            # valueは辞書またはJSON文字列の場合があるので対応
            if isinstance(user, str):
                user = json.loads(user)
            users.append(user)
    except Exception as e:
        st.error(get_localized_text(f"ユーザー情報の読み込みに失敗しました: {e}", f"Failed to load user information: {e}"))
        st.stop()
    return users

# ログインフォームの表示
def login_form():
    st.subheader(get_localized_text("ログイン", "Login"))

    user_data = load_users_from_secrets()

    with st.form("login_form"):
        username_input = st.text_input(get_localized_text("ユーザー名", "Username"))
        password_input = st.text_input(get_localized_text("パスワード", "Password"), type="password")
        submitted = st.form_submit_button(get_localized_text("ログイン", "Login"))

    if submitted:
        found_user = False
        for user in user_data:
            if username_input == user["username"]:
                found_user = True
                if verify_password(password_input, user["password_hash"]):
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = user["username"]
                    st.success(get_localized_text("ログイン成功！", "Login successful!"))
                    st.rerun()
                else:
                    st.error(get_localized_text("パスワードが違います。", "Incorrect password."))
                break
        if not found_user:
            st.error(get_localized_text("ユーザーが見つかりません。", "User not found."))

# --- アプリ本体のクラスと関数 (v1.0.0.py からの移行) ---

class SessionManager:
    @staticmethod
    def initialize():
        session_vars = {
            'upload_files': [],
            'template_store': [],
            'analysis_log': [],
            'comparison_template': {},
            'current_data': None,
            'selected_teams': None, # フィルターの状態を保持するためにNoneを許容
            'date_range': [None, None],
            'analysis_count': 0,
            'heatmap_count': 0,
            'trend_count': 0,
            'ranking_count': 0,
            'dfmain': None,
            'uploaded_file_processed': False,
            'num_uploaders': 1,
            'previous_files_hash': None
        }
        
        for var, default in session_vars.items():
            if var not in st.session_state:
                st.session_state[var] = default

class DataProcessor:
    @staticmethod
    def safe_read_csv(file):
        try:
            df = pd.read_csv(
                file,
                encoding='utf-8-sig',
                on_bad_lines='warn',
            )
            return df, None
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(
                    file,
                    encoding='cp932',
                    on_bad_lines='warn',
                )
                return df, None
            except Exception as e:
                return None, get_localized_text(f"読み込みエラー: {str(e)}", f"Read error: {str(e)}")
        except Exception as e:
            return None, get_localized_text(f"読み込みエラー: {str(e)}", f"Read error: {str(e)}")

    @staticmethod
    def process_dataframe(df):
        if df is None:
            return None
            
        if '実施日' in df.columns:
            # 実施日列の変換とNaNチェックを追加
            initial_nan_count = df['実施日'].isnull().sum()
            df['実施日'] = pd.to_datetime(df['実施日'], errors='coerce')
            # 時間部分を削除し、日付のみにする（.dt.normalize()を追加）
            df['実施日'] = df['実施日'].dt.normalize().dt.date 

            nan_after_coerce = df['実施日'].isnull().sum()
            
            if nan_after_coerce > initial_nan_count:
                newly_coerced_nan_percentage = (nan_after_coerce - initial_nan_count) / len(df) * 100
                if newly_coerced_nan_percentage > 10: # 例えば10%以上の値が無効になった場合に警告
                    st.warning(get_localized_text(
                        f"「実施日」列の{newly_coerced_nan_percentage:.1f}%が日付として認識できませんでした。元のデータ形式を確認してください。",
                        f"{newly_coerced_nan_percentage:.1f}% of '実施日' column could not be recognized as dates. Please check the original data format."
                    ))

        numeric_cols = ['申込数', '参加者数', 'リアクション数', '宣伝回数', '満足回答']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce') 
        
        if all(col in df.columns for col in ['参加者数', '申込数']):
            df['参加率(%)'] = (df['参加者数'] / df['申込数']) * 100
        if all(col in df.columns for col in ['満足回答', '参加者数']):
            df['満足率(%)'] = (df['満足回答'] / df['参加者数']) * 100
        if all(col in df.columns for col in ['リアクション数', '参加者数']):
            df['リアクション率'] = df['リアクション数'] / df['参加者数']
        
        return df

    @staticmethod
    def expand_time_slots(df):
        if '時間帯' in df.columns:
            df['時間帯'] = df['時間帯'].astype(str)
            df['時間帯スロット'] = df['時間帯'].str.split('・')
            df = df.explode('時間帯スロット').reset_index(drop=True) # インデックスのリセットを追加
            df['時間帯スロット'] = df['時間帯スロット'].str.strip()
        return df

# メインダッシュボードの表示 (v1.0.0.py の main 関数を show_main_app にリネーム)
def show_main_app():
    st.markdown("""
    <style>
    @font-face {
    font-family: 'Noto Sans JP';
    src: url('/static/NotoSansJP-Thin.woff2') format('woff2');
    }
    body, div, p, span, input, label {
    font-family: 'Noto Sans JP', sans-serif !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title(get_localized_text("VRイベント分析アプリ", "VR Event Analysis App"))

    SessionManager.initialize()

    with st.sidebar:
        st.markdown(get_localized_text("## 🔍 フィルター設定", "## 🔍 Filter Settings"))
        st.markdown("---")

        dfmain_for_sidebar = st.session_state.get('dfmain')

        if dfmain_for_sidebar is not None and not dfmain_for_sidebar.empty:
            df_filtered = dfmain_for_sidebar.copy()

            if '担当チーム' in df_filtered.columns:
                teams = sorted(df_filtered['担当チーム'].dropna().unique())
                
                # selected_teams の初期値をセッションステートから取得、なければ全選択
                initial_selected_teams = st.session_state.get('selected_teams')
                # selected_teams がNoneの場合、全チームを選択状態にする
                if initial_selected_teams is None:
                    initial_selected_teams = teams
                
                selected_teams = st.multiselect(
                    get_localized_text("👥 担当チーム", "👥 Responsible Teams"), 
                    teams, 
                    default=[t for t in initial_selected_teams if t in teams] # 存在しないチームがdefaultに含まれないようにフィルタ
                )
                st.session_state.selected_teams = selected_teams # セッションステートに選択を保存

                # 担当チームが何も選択されていない場合の動作変更
                if len(selected_teams) == 0:
                    st.warning(get_localized_text("担当チームが選択されていません。全ての担当チームのデータが表示されます。", "No teams selected. Data for all teams will be displayed."))
                    # df_filtered はこのブロックに入る前の状態（dfmain_for_sidebar）のまま使用
                else:
                    df_filtered = df_filtered[df_filtered['担当チーム'].isin(selected_teams)]

            if '実施日' in df_filtered.columns:
                # dt.dateに変換されているため、そのまま使用
                valid_dates = df_filtered['実施日'].dropna()
                if not valid_dates.empty:
                    # Pythonのdateオブジェクトはmin()/max()で直接比較可能
                    min_date = min(valid_dates)
                    max_date = max(valid_dates)
                    
                    default_date_range = [min_date, max_date] if min_date <= max_date else [min_date, min_date]
                    date_range = st.date_input(get_localized_text("📅 実施日の範囲", "📅 Date Range"), value=default_date_range)
                    
                    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                        start, end = date_range[0], date_range[1]
                        df_filtered = df_filtered[
                            (df_filtered['実施日'] >= start) & 
                            (df_filtered['実施日'] <= end)
                        ]
                else:
                    st.warning(get_localized_text("日付データがありません。", "No date data available."))
            
            st.session_state.current_data = df_filtered

        else:
            st.info(get_localized_text("データをアップロードしてください", "Please upload data."))

    tabs = st.tabs([
        get_localized_text("📊 データ管理", "📊 Data Management"),
        get_localized_text("📈 分析・比較", "📈 Analysis & Comparison"),
        get_localized_text("📊 クロス集計", "📊 Cross Tabulation"),
        get_localized_text("🕒 ヒートマップ", "🕒 Heatmap"),
        get_localized_text("📉 時系列", "📉 Time Series"),
        get_localized_text("🏆 ランキング", "🏆 Ranking"),
        get_localized_text("📋 自動レポート", "📋 Automatic Report")
    ])

    with tabs[0]:
        st.header(get_localized_text("📁 分析対象CSVファイルのアップロード", "📁 Upload CSV File for Analysis"))
        
        col1, col2 = st.columns([2, 1])
        with col1:
            all_uploaded_files_current_run = [] 
            uploader_objects = [] 
            last_uploaded_idx = -1 

            for i in range(st.session_state.num_uploaders):
                label = get_localized_text("CSVファイル (必須)", "CSV File (Required)") if i == 0 else get_localized_text(f"追加のCSVファイル (オプション {i})", f"Additional CSV File (Optional {i})")
                file_obj = st.file_uploader(
                    label,
                    type="csv",
                    key=f"csv_upload_{i}"
                )
                uploader_objects.append(file_obj)
                
                if file_obj is not None:
                    last_uploaded_idx = i
                    all_uploaded_files_current_run.append(file_obj)

            new_num_uploaders = st.session_state.num_uploaders

            if last_uploaded_idx != -1:
                target_num_uploaders = last_uploaded_idx + 2
                new_num_uploaders = max(new_num_uploaders, target_num_uploaders)
            else:
                new_num_uploaders = 1
            
            if last_uploaded_idx != -1 and st.session_state.num_uploaders > (last_uploaded_idx + 2):
                new_num_uploaders = last_uploaded_idx + 2
            elif last_uploaded_idx == -1 and st.session_state.num_uploaders > 1:
                new_num_uploaders = 1

            if new_num_uploaders != st.session_state.num_uploaders:
                st.session_state.num_uploaders = new_num_uploaders
                st.rerun()

            current_files_hash = hash(tuple((f.name, f.size) for f in all_uploaded_files_current_run if f is not None))
            previous_files_hash = st.session_state.get('previous_files_hash', None)

            files_changed = (current_files_hash != previous_files_hash)
            
            if files_changed and all_uploaded_files_current_run:
                st.session_state.upload_files = all_uploaded_files_current_run
                st.session_state.uploaded_file_processed = False
                st.session_state.previous_files_hash = current_files_hash
                st.rerun()

            if st.session_state.upload_files and not st.session_state.uploaded_file_processed:
                uploaded_dfs_temp = []
                for f in st.session_state.upload_files:
                    f.seek(0)
                    df_t, error = DataProcessor.safe_read_csv(f)
                    if error:
                        st.error(get_localized_text(f"ファイル {f.name}: {error}", f"File {f.name}: {error}"))
                    else:
                        df_t = DataProcessor.process_dataframe(df_t)
                        if df_t is not None:
                            uploaded_dfs_temp.append(df_t)

                if uploaded_dfs_temp:
                    df_combined = pd.concat(uploaded_dfs_temp, ignore_index=True).drop_duplicates()
                    df_combined = DataProcessor.expand_time_slots(df_combined)
                    st.session_state['dfmain'] = df_combined
                    st.session_state.current_data = df_combined
                    st.session_state.uploaded_file_processed = True

                    numeric_cols_for_check = ['申込数', '参加者数', 'リアクション数', '宣伝回数', '満足回答']
                    high_nan_cols = []
                    for col in numeric_cols_for_check:
                        if col in df_combined.columns:
                            nan_percentage = df_combined[col].isnull().sum() / len(df_combined) * 100
                            if nan_percentage > 50: 
                                high_nan_cols.append(f"{col} ({nan_percentage:.1f}%)")
                    if high_nan_cols:
                        st.warning(get_localized_text(
                            f"以下の数値列で高い欠損率が検出されました: {', '.join(high_nan_cols)}。\n"
                            "これは、元のCSVファイルの該当列に数値以外のデータが多く含まれている可能性があります。"
                            "データの正確性を確認してください。",
                            f"High missing values detected in the following numeric columns: {', '.join(high_nan_cols)}.\n"
                            "This may indicate that the original CSV file contains non-numeric data in these columns. Please verify data accuracy."
                        ))
                else:
                    st.session_state['dfmain'] = None
                    st.session_state.current_data = None
                    st.session_state.uploaded_file_processed = True
            
        df_display = st.session_state.get('current_data')
        if df_display is None or df_display.empty:
            st.warning(get_localized_text("データがアップロードされていないか、フィルターによってデータがありません。", "No data uploaded or no data after filtering."))
        else:
            if st.session_state.upload_files:
                with col2:
                    st.markdown(get_localized_text("### 📊 ファイル情報", "### 📊 File Information"))
                    for i, f in enumerate(all_uploaded_files_current_run, 1):
                        if f is not None:
                            display_name = f.name if hasattr(f, 'name') else get_localized_text(f"ファイル {i}", f"File {i}")
                            st.info(get_localized_text(f"ファイル {i}: {display_name}", f"File {i}: {display_name}"))

                if len(st.session_state.upload_files) > 1: 
                    st.markdown(get_localized_text("### 🔄 データ統合結果", "### 🔄 Data Integration Result"))
                    total_rows_before = 0
                    for f in st.session_state.upload_files:
                        f.seek(0)
                        temp_df, _ = DataProcessor.safe_read_csv(f)
                        if temp_df is not None:
                            total_rows_before += len(temp_df)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(get_localized_text("アップロードされた全てのデータ数", "Total Uploaded Rows"), f"{total_rows_before}{get_localized_text('行', ' rows')}")
                    with col2:
                        st.metric(get_localized_text("統合後のデータ数", "Total Integrated Rows"), f"{len(df_display)}{get_localized_text('行', ' rows')}")
                    with col3:
                        removed_rows = total_rows_before - len(df_display)
                        if removed_rows > 0:
                            st.metric(get_localized_text("重複削除", "Duplicates Removed"), f"{removed_rows}{get_localized_text('行', ' rows')}")
                            st.info(get_localized_text(
                                f"※ {removed_rows}行の重複（全ての列が完全に一致する行）を削除しました。",
                                f"※ {removed_rows} duplicate rows (all columns perfectly matching) were removed."
                            ))
                else:
                    st.info(get_localized_text(f"単一ファイル（{len(df_display)}行）を処理します", f"Processing single file ({len(df_display)} rows)"))

            st.markdown(get_localized_text("### 📋 データプレビュー", "### 📋 Data Preview"))
            preview_rows = st.number_input(
                get_localized_text("表示する行数（0で全行表示）", "Number of rows to display (0 for all)"),
                min_value=0,
                max_value=len(df_display),
                value=5
            )
            
            if preview_rows == 0:
                st.dataframe(df_display, use_container_width=True)
            else:
                st.dataframe(df_display.head(preview_rows), use_container_width=True)

            st.markdown(get_localized_text("### 📋 列情報", "### 📋 Column Information"))
            col_info = pd.DataFrame({
                get_localized_text('データ型', 'Data Type'): df_display.dtypes,
                get_localized_text('欠損値数', 'Missing Count'): df_display.isnull().sum(),
                get_localized_text('欠損率(%)', 'Missing Rate (%)'): (df_display.isnull().sum() / len(df_display) * 100).round(2),
                get_localized_text('ユニーク値数', 'Unique Count'): df_display.nunique(),
            })
            st.dataframe(col_info)

            st.markdown(get_localized_text("### 📊 基本統計量", "### 📊 Basic Statistics"))
            numeric_cols = df_display.select_dtypes(include=['int64', 'float64']).columns
            if not numeric_cols.empty:
                stats_df = df_display[numeric_cols].describe().T

                rename_map = {
                    "count": get_localized_text("データ数", "Count"),
                    "mean": get_localized_text("平均", "Mean"),
                    "std": get_localized_text("標準偏差", "Std Dev"),
                    "min": get_localized_text("最小値", "Min"),
                    "25%": "25%",
                    "50%": get_localized_text("中央値", "Median"),
                    "75%": "75%",
                    "max": get_localized_text("最大値", "Max")
                }

                stats_df = stats_df.rename(columns=rename_map)
                st.dataframe(stats_df)


            st.markdown(get_localized_text("### 📊 カテゴリ列の内訳", "### 📊 Category Column Breakdown"))
            category_cols = df_display.select_dtypes(include=['object']).columns
            if not category_cols.empty:
                selected_col = st.selectbox(get_localized_text("確認する列を選択", "Select column to check"), category_cols)
                value_counts = df_display[selected_col].value_counts()
                
                fig, ax = plt.subplots(figsize=(10, 5))
                value_counts.plot(kind='bar', ax=ax)
                
                title_font = {'fontfamily': plt.rcParams['font.family'], 'fontsize': 12}
                ax.set_title(get_graph_text(f"{selected_col}の値カウント", f"Value Counts of {selected_col}", fontproperties=font_prop), fontproperties=font_prop, **title_font)
                ax.set_xlabel(get_graph_text(selected_col, selected_col, fontproperties=font_prop), fontproperties=font_prop)
                ax.set_ylabel(get_graph_text("カウント", "Count", fontproperties=font_prop), fontproperties=font_prop)
                
                for label in ax.get_xticklabels():
                    label.set_fontfamily(plt.rcParams['font.family'])
                for label in ax.get_yticklabels():
                    label.set_fontfamily(plt.rcParams['font.family'])
                
                plt.xticks(rotation=45)
                plt.tight_layout()
                st.pyplot(fig)

    with tabs[1]:
        st.header(get_localized_text("📈 分析・比較", "📈 Analysis & Comparison"))
        
        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()
            
            col1, col2 = st.columns(2)
            with col1:
                num_cols = df.select_dtypes(include='number').columns.tolist()
                cat_cols = df.select_dtypes(include='object').columns.tolist()
                
                if not num_cols:
                    st.warning(get_localized_text("数値列がありません。", "No numeric columns found."))
                    st.stop()
                if not cat_cols:
                    st.warning(get_localized_text("カテゴリ列がありません。", "No categorical columns found."))
                    st.stop()

                target_num = st.selectbox(get_localized_text("分析対象（数値）", "Analysis Target (Numeric)"), num_cols)
                group_col = st.selectbox(get_localized_text("グループ化（カテゴリ）", "Group By (Category)"), cat_cols)

            with col2:
                agg_options = [
                    get_localized_text('平均', 'Mean'),
                    get_localized_text('合計', 'Sum'),
                    get_localized_text('中央値', 'Median'),
                    get_localized_text('最大', 'Max'),
                    get_localized_text('最小', 'Min'),
                    get_localized_text('データ数', 'Count')
                ]
                selected_aggs_display = st.multiselect(
                    get_localized_text("表示する統計指標", "Select Statistical Metrics to Display"),
                    agg_options,
                    default=agg_options
                )
                exclude_outliers = st.checkbox(get_localized_text("外れ値を除外", "Exclude Outliers"))

            try:
                analysis_df = df.copy()
                
                if exclude_outliers and target_num in analysis_df.columns and analysis_df[target_num].std() > 0:
                    z_scores = np.abs((analysis_df[target_num] - analysis_df[target_num].mean()) / 
                                    analysis_df[target_num].std())
                    analysis_df = analysis_df[z_scores < 3]
                elif exclude_outliers: # std=0の場合
                    st.info(get_localized_text(
                        f"'{target_num}'のデータにばらつきがないため、外れ値除外は適用されませんでした。",
                        f"Outlier exclusion was not applied as '{target_num}' data has no variance."
                    ))


                agg_map_internal = {
                    get_localized_text('平均', 'Mean'): 'mean',
                    get_localized_text('合計', 'Sum'): 'sum',
                    get_localized_text('中央値', 'Median'): 'median',
                    get_localized_text('最大', 'Max'): 'max',
                    get_localized_text('最小', 'Min'): 'min',
                    get_localized_text('データ数', 'Count'): 'count'
                }
                
                agg_funcs_list = [agg_map_internal[a] for a in selected_aggs_display if a in agg_map_internal] 

                if group_col in analysis_df.columns and target_num in analysis_df.columns:
                    grouped_df = analysis_df.groupby(group_col)[target_num].agg(agg_funcs_list)
                    
                    # 存在するカラムのみリネーム
                    rename_dict = {agg_map_internal[a]: f"{target_num}_{a}" for a in selected_aggs_display if agg_map_internal[a] in grouped_df.columns}
                    grouped_df.rename(columns=rename_dict, inplace=True)

                else:
                    st.error(get_localized_text("選択された列がデータフレームに存在しません。", "Selected columns do not exist in the dataframe."))
                    grouped_df = pd.DataFrame()

                if not grouped_df.empty:
                    st.markdown(get_localized_text("### 📊 グループ別集計結果", "### 📊 Grouped Aggregation Results"))
                    st.dataframe(grouped_df.round(2), use_container_width=True)

                    if selected_aggs_display:
                        st.markdown(get_localized_text("### 📈 統計指標別グラフ", "### 📈 Graphs by Statistical Metric"))
                        cols = st.columns(2)
                        for i, metric_display_name in enumerate(selected_aggs_display):
                            col_name_for_plot = f"{target_num}_{metric_display_name}" 
                            if col_name_for_plot in grouped_df.columns:
                                with cols[i % 2]:
                                    fig, ax = plt.subplots(figsize=(8, 4))
                                    grouped_df[col_name_for_plot].plot(kind='bar', ax=ax)
                                    ax.set_ylabel(get_graph_text(f"{target_num}の{metric_display_name}", f"{metric_display_name} of {target_num}", fontproperties=font_prop), fontfamily=plt.rcParams['font.family'])
                                    ax.set_title(get_graph_text(f"{group_col}ごとの{target_num}（{metric_display_name}）", f"{metric_display_name} of {target_num} by {group_col}", fontproperties=font_prop), fontfamily=plt.rcParams['font.family'])
                                    plt.xticks(rotation=45)
                                    plt.tight_layout()
                                    st.pyplot(fig)

                                    buf = io.BytesIO()
                                    fig.savefig(buf, format='png')
                                    st.download_button(
                                        get_localized_text(f"📥 {metric_display_name}のグラフを保存", f"📥 Save {metric_display_name} Graph"),
                                        buf.getvalue(),
                                        f"analysis_{metric_display_name}.png",
                                        "image/png"
                                    )
                else:
                    st.warning(get_localized_text("集計結果がありません。フィルター設定またはデータを確認してください。", "No aggregation results. Please check filter settings or data."))

            except Exception as e:
                st.error(get_localized_text(f"分析エラー: {e}", f"Analysis error: {e}"))
        else:
            st.warning(get_localized_text("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。", "No data uploaded or no data after filtering. Please upload files in the Data Management tab."))

    with tabs[2]:
        st.header(get_localized_text("📊 クロス集計", "📊 Cross Tabulation"))

        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()

            cat_cols = df.select_dtypes(include='object').columns.tolist()
            num_cols = df.select_dtypes(include='number').columns.tolist()

            if len(cat_cols) < 2:
                st.warning(get_localized_text("クロス集計には2つ以上のカテゴリ列が必要です。", "Cross tabulation requires at least two categorical columns."))
                st.stop()
            if not num_cols:
                st.warning(get_localized_text("数値列がありません。", "No numeric columns found."))
                st.stop()

            col1 = st.selectbox(get_localized_text("行カテゴリ", "Row Category"), cat_cols, key="cross_row")
            col2_options = [c for c in cat_cols if c != col1]
            if not col2_options:
                st.warning(get_localized_text(f"'{col1}' 以外のカテゴリ列がありません。", f"No categorical columns other than '{col1}' found."))
                st.stop()
            col2 = st.selectbox(get_localized_text("列カテゴリ", "Column Category"), col2_options, key="cross_col")
            
            num_col = st.selectbox(get_localized_text("数値項目", "Numeric Item"), num_cols, key="cross_num")
            agg_method_display = st.selectbox(get_localized_text("集計方法", "Aggregation Method"), [
                get_localized_text('平均', 'Mean'),
                get_localized_text('合計', 'Sum'),
                get_localized_text('中央値', 'Median'),
                get_localized_text('最大', 'Max'),
                get_localized_text('最小', 'Min'),
                get_localized_text('データ数', 'Count')
            ], key="cross_agg")

            if st.button(get_localized_text("クロス集計を実行", "Execute Cross Tabulation"), key="cross_execute"):
                try:
                    agg_map_internal = {
                        get_localized_text('平均', 'Mean'): 'mean',
                        get_localized_text('合計', 'Sum'): 'sum',
                        get_localized_text('中央値', 'Median'): 'median',
                        get_localized_text('最大', 'Max'): 'max',
                        get_localized_text('最小', 'Min'): 'min',
                        get_localized_text('データ数', 'Count'): 'count'
                    }

                    if col1 in df.columns and col2 in df.columns and num_col in df.columns:
                        cross_table = pd.pivot_table(
                            df,
                            values=num_col,
                            index=col1,
                            columns=col2,
                            aggfunc=agg_map_internal[agg_method_display]
                        )
                        if isinstance(cross_table.columns, pd.MultiIndex):
                            cross_table.columns = cross_table.columns.droplevel(0)

                        st.dataframe(cross_table)

                        fig, ax = plt.subplots(figsize=(10, 5))
                        cross_table.plot(kind='bar', ax=ax)
                        ax.set_ylabel(get_graph_text(num_col, num_col, fontproperties=font_prop), fontfamily=plt.rcParams['font.family']) # Column name is fine
                        ax.set_title(get_graph_text(f"{col1} × {col2} の {agg_method_display}", f"{agg_method_display} of {num_col} by {col1} x {col2}", fontproperties=font_prop), fontfamily=plt.rcParams['font.family'])
                        plt.xticks(rotation=45)
                        plt.tight_layout()
                        st.pyplot(fig)

                        csv = cross_table.to_csv(encoding='utf-8-sig').encode('utf-8-sig')
                        st.download_button(
                            get_localized_text("📥 クロス集計結果をCSVで保存", "📥 Save Cross Tabulation Result as CSV"),
                            csv,
                            file_name="cross_table.csv",
                            mime='text/csv',
                            key="cross_download"
                        )
                    else:
                        st.error(get_localized_text("選択された列がデータフレームに存在しません。", "Selected columns do not exist in the dataframe."))

                except Exception as e:
                    st.error(get_localized_text(f"クロス集計の実行に失敗しました: {e}", f"Failed to execute cross tabulation: {e}"))
        else:
            st.warning(get_localized_text("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。", "No data uploaded or no data after filtering. Please upload files in the Data Management tab."))


    with tabs[3]:
        st.header(get_localized_text("🟥 ヒートマップ", "🟥 Heatmap"))

        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()

            df = DataProcessor.expand_time_slots(df)

            if '時間帯スロット' not in df.columns or '曜日' not in df.columns:
                st.warning(get_localized_text("ヒートマップを作成するには「時間帯」と「曜日」の列が必要です。", "Time slot and weekday columns are required to create a heatmap."))
                st.stop()
            
            if not all(col in df.columns for col in ['時間帯スロット', '曜日']):
                st.warning(get_localized_text("ヒートマップの作成に必要な列（時間帯スロット、曜日）がデータに存在しません。", "Required columns for heatmap (Time Slot, Weekday) do not exist in the data."))
                st.stop()


            numeric_cols = df.select_dtypes(include='number').columns.tolist()
            if not numeric_cols:
                st.warning(get_localized_text("数値列がありません。ヒートマップは数値データに基づいています。", "No numeric columns found. Heatmap is based on numeric data."))
                st.stop()

            col1, col2 = st.columns(2)
            with col1:
                heat_metric = st.selectbox(
                    get_localized_text("集計する指標", "Metric to Aggregate"),
                    numeric_cols,
                    key="heat_metric"
                )
                agg_method_display = st.selectbox(
                    get_localized_text("集計方法", "Aggregation Method"),
                    [get_localized_text('平均', 'Mean'), get_localized_text('合計', 'Sum'), get_localized_text('データ数', 'Count')],
                    key="heat_agg"
                )

            with col2:
                color_scale = st.selectbox(
                    get_localized_text("カラースケール", "Color Scale"),
                    ['YlOrRd', 'viridis', 'coolwarm'],
                    key="heat_color"
                )
                normalize = st.checkbox(get_localized_text("データを正規化", "Normalize Data"), value=True, key="heat_normalize")

            if st.button(get_localized_text("ヒートマップを生成", "Generate Heatmap"), key="heat_execute"):
                try:
                    heat_df = df.copy()

                    agg_map_internal = {
                        get_localized_text('平均', 'Mean'): 'mean',
                        get_localized_text('合計', 'Sum'): 'sum',
                        get_localized_text('データ数', 'Count'): 'count'
                    }
                    pivot_table = pd.pivot_table(
                        heat_df,
                        values=heat_metric,
                        index='時間帯スロット',
                        columns='曜日',
                        aggfunc=agg_map_internal[agg_method_display]
                        )

                    weekdays = ['月', '火', '水', '木', '金', '土', '日']
                    existing_weekdays = [day for day in weekdays if day in pivot_table.columns]
                    pivot_table = pivot_table.reindex(columns=existing_weekdays)
                    
                    try:
                        pivot_table = pivot_table.reindex(sorted(pivot_table.index))
                    except Exception:
                        pass

                    if normalize and not pivot_table.empty and pivot_table.std().std() > 0:
                        pivot_table = (pivot_table - pivot_table.mean().mean()) / pivot_table.std().std()
                    elif normalize and not pivot_table.empty: # 標準偏差が0の場合
                        st.info(get_localized_text("データにばらつきがないため、ヒートマップの正規化はスキップされました。", "Heatmap normalization skipped as data has no variance."))


                    fig, ax = plt.subplots(figsize=(12, 8))
                    sns.heatmap(
                        pivot_table,
                        cmap=color_scale,
                        annot=True,
                        fmt='.2f',
                        linewidths=.5,
                        linecolor='black',
                        ax=ax
                    )

                    ax.set_title(get_graph_text(f"時間帯×曜日の{heat_metric}（{agg_method_display}）", f"{agg_method_display} of {heat_metric} by Time Slot x Weekday", fontproperties=font_prop), fontfamily=plt.rcParams['font.family'], fontsize=16)
                    ax.set_xlabel(get_graph_text("曜日", "Weekday", fontproperties=font_prop), fontfamily=plt.rcParams['font.family'], fontsize=12)
                    ax.set_ylabel(get_graph_text("時間帯スロット", "Time Slot", fontproperties=font_prop), fontfamily=plt.rcParams['font.family'], fontsize=12)

                    for label in ax.get_xticklabels():
                        label.set_fontfamily(plt.rcParams['font.family'])
                    for label in ax.get_yticklabels():
                        label.set_fontfamily(plt.rcParams['font.family'])

                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig)

                    csv = pivot_table.to_csv(encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        get_localized_text("📥 ヒートマップデータをCSVで保存", "📥 Save Heatmap Data as CSV"),
                        csv,
                        file_name="heatmap_data.csv",
                        mime='text/csv',
                        key="heat_download"
                    )

                    st.subheader(get_localized_text("📊 特徴的なパターン", "📊 Characteristic Patterns"))

                    if not pivot_table.empty:
                        max_val_series = pivot_table.max()
                        if not max_val_series.empty:
                            max_val = max_val_series.max()
                        else:
                            max_val = np.nan

                        min_val_series = pivot_table.min()
                        if not min_val_series.empty:
                            min_val = min_val_series.min()
                        else:
                            min_val = np.nan

                        if not np.isnan(max_val) and not pivot_table[pivot_table == max_val].empty:
                            max_pos_df = pivot_table[pivot_table == max_val].stack().index[0]
                            st.info(get_localized_text(
                                f"🔺 最も{heat_metric}が高い時間帯: {max_pos_df[0]}の{max_pos_df[1]}曜日 ({max_val:.2f})",
                                f"🔺 Highest {heat_metric} time: {max_pos_df[0]} on {max_pos_df[1]} ({max_val:.2f})"
                            ))
                        else:
                            st.info(get_localized_text("🔺 最も高い値のパターンを特定できませんでした。", "🔺 Could not identify the highest value pattern."))

                        if not np.isnan(min_val) and not pivot_table[pivot_table == min_val].empty:
                            min_pos_df = pivot_table[pivot_table == min_val].stack().index[0]
                            st.info(get_localized_text(
                                f"🔻 最も{heat_metric}が低い時間帯: {min_pos_df[0]}の{min_pos_df[1]}曜日 ({min_val:.2f})",
                                f"🔻 Lowest {heat_metric} time: {min_pos_df[0]} on {min_pos_df[1]} ({min_val:.2f})"
                            ))
                        else:
                            st.info(get_localized_text("🔻 最も低い値のパターンを特定できませんでした。", "🔻 Could not identify the lowest value pattern."))
                    else:
                        st.info(get_localized_text("ヒートマップデータが空のため、特徴的なパターンを特定できません。", "Heatmap data is empty, cannot identify characteristic patterns."))


                except Exception as e:
                    st.error(get_localized_text(f"ヒートマップ生成中にエラーが発生: {e}", f"An error occurred during heatmap generation: {e}"))
        else:
            st.warning(get_localized_text("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。", "No data uploaded or no data after filtering. Please upload files in the Data Management tab."))


    with tabs[4]:
        st.header(get_localized_text("📉 時系列分析", "📉 Time Series Analysis"))

        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()

            if '実施日' not in df.columns:
                st.warning(get_localized_text("時系列分析には「実施日」の列が必要です。", "The '実施日' (Date) column is required for time series analysis."))
                st.stop()
            
            # 実施日がPythonのdateオブジェクトになっているため、そのままdropna
            df = df.dropna(subset=['実施日'])

            if df.empty:
                st.warning(get_localized_text("有効な日付データがありません。", "No valid date data available."))
                st.stop()

            # DatetimeIndexの作成用に、dateオブジェクトをTimestampに変換
            df['実施日_timestamp'] = pd.to_datetime(df['実施日'])


            cat_cols = df.select_dtypes(include='object').columns.tolist()
            numeric_cols = df.select_dtypes(include='number').columns.tolist()

            if not numeric_cols:
                st.warning(get_localized_text("数値列がありません。時系列分析は数値データに基づいています。", "No numeric columns found. Time series analysis is based on numeric data."))
                st.stop()

            col1, col2 = st.columns(2)
            with col1:
                trend_metric = st.selectbox(
                    get_localized_text("分析する指標", "Metric to Analyze"),
                    numeric_cols,
                    key="trend_metric"
                )
                trend_group = st.selectbox(
                    get_localized_text("グループ化（オプション）", "Group By (Optional)"),
                    ['なし'] + cat_cols,
                    key="trend_group"
                )

            with col2:
                agg_period_display = st.selectbox(
                    get_localized_text("集計期間", "Aggregation Period"),
                    [get_localized_text('日次', 'Daily'), get_localized_text('週次', 'Weekly'), get_localized_text('月次', 'Monthly')],
                    key="trend_period"
                )
                moving_avg = st.number_input(
                    get_localized_text("移動平均期間", "Moving Average Period"), 
                    min_value=1,
                    max_value=30,
                    value=7,
                    key="trend_ma"
                )

            try:
                trend_df = df.copy()
                
                period_map_internal = {
                    get_localized_text('日次', 'Daily'): 'D',
                    get_localized_text('週次', 'Weekly'): 'W',
                    get_localized_text('月次', 'Monthly'): 'M'
                }

                fig, ax = plt.subplots(figsize=(12, 6))
                has_data_to_plot = False 

                if trend_group == 'なし':
                    resampled = trend_df.set_index('実施日_timestamp')[trend_metric].resample(period_map_internal[agg_period_display]).mean()
                    
                    if not resampled.empty:
                        resampled.plot(ax=ax, label=get_graph_text(f'{agg_period_display}平均', f'{agg_period_display} Average'))
                        moving = resampled.rolling(window=moving_avg, min_periods=1).mean() 
                        if not moving.empty:
                            moving.plot(ax=ax, label=get_graph_text(f'{moving_avg}{agg_period_display[0]}移動平均', f'{moving_avg}{agg_period_display[0]} Moving Average'), style='--') 
                        else:
                            st.info(get_localized_text("移動平均を計算する十分なデータがありません。", "Insufficient data to calculate moving average."))
                        has_data_to_plot = True
                    else:
                        st.warning(get_localized_text("集計データが空のため、時系列グラフを生成できませんでした。", "Time series graph could not be generated as aggregation data is empty."))
                    
                    if not resampled.empty:
                        st.subheader(get_localized_text("📊 時系列の特徴", "📊 Time Series Characteristics"))
                        latest_val = resampled.iloc[-1]
                        prev_val = resampled.iloc[-2] if len(resampled) > 1 else None

                        st.info(get_localized_text(f"最新の{agg_period_display}平均: {latest_val:.2f}", f"Latest {agg_period_display} average: {latest_val:.2f}"))
                        if prev_val is not None and prev_val != 0:
                            change = ((latest_val - prev_val) / prev_val * 100)
                            st.info(get_localized_text(f"直近の{agg_period_display}からの変化率: {change:.1f}%", f"Change from previous {agg_period_display}: {change:.1f}%"))
                        else:
                            st.info(get_localized_text("直近の変化率を計算するデータがありません。", "No data to calculate recent change rate."))
                    else:
                        st.info(get_localized_text("集計データが空のため、特徴を抽出できません。", "Aggregation data is empty, cannot extract characteristics."))

                    if not resampled.empty:
                        csv = resampled.to_csv(encoding='utf-8-sig').encode('utf-8-sig')
                        st.download_button(
                            get_localized_text("📥 時系列データをCSVで保存", "📥 Save Time Series Data as CSV"),
                            csv,
                            file_name="trend_data.csv",
                            mime='text/csv',
                            key="trend_download"
                        )

                else:
                    if trend_group in trend_df.columns:
                        groups = trend_df[trend_group].dropna().unique()
                        if len(groups) > 0:
                            for group in groups:
                                if pd.notna(group) and str(group).strip() != '':
                                    group_data = trend_df[trend_df[trend_group] == group]
                                    if not group_data.empty:
                                        resampled = group_data.set_index('実施日_timestamp')[trend_metric].resample(period_map_internal[agg_period_display]).mean()
                                        if not resampled.empty:
                                            resampled.plot(ax=ax, label=str(group)) # Group name is data, keep as is
                                            moving = resampled.rolling(window=moving_avg, min_periods=1).mean()
                                            if not moving.empty:
                                                moving.plot(ax=ax, label=get_graph_text(f'{str(group)} ({moving_avg}{agg_period_display[0]}移動平均)', f'{str(group)} ({moving_avg}{agg_period_display[0]} Moving Average)'), style='--') 
                                            else:
                                                st.info(get_localized_text(f"グループ '{group}' の移動平均を計算する十分なデータがありません。", f"Insufficient data to calculate moving average for group '{group}'."))
                                            has_data_to_plot = True
                                        else:
                                            st.warning(get_localized_text(f"グループ '{group}' のデータが不足しているため、時系列グラフを生成できませんでした。", f"Time series graph could not be generated for group '{group}' due to insufficient data."))
                                    else:
                                        st.warning(get_localized_text(f"グループ '{group}' のデータがありません。", f"No data for group '{group}'."))
                            
                            if not has_data_to_plot:
                                st.warning(get_localized_text("選択されたグループのいずれも時系列データをプロットできませんでした。", "No time series data could be plotted for any of the selected groups."))
                        else:
                            st.warning(get_localized_text(f"選択されたグループ列 '{trend_group}' に有効な値がありません。", f"No valid values in selected group column '{trend_group}'."))
                    else:
                        st.error(get_localized_text(f"選択されたグループ列 '{trend_group}' がデータフレームに存在しません。", f"Selected group column '{trend_group}' does not exist in the dataframe."))

                if has_data_to_plot:
                    ax.set_title(get_graph_text(
                        f"{trend_metric}の時系列 ({'全体' if trend_group == 'なし' else trend_group}別, fontproperties=font_prop)",
                        f"Time Series of {trend_metric} (by {'Overall' if trend_group == 'なし' else trend_group})"
                    ), fontfamily=plt.rcParams['font.family'], fontsize=16)
                    ax.set_xlabel(get_graph_text("実施日", "Date", fontproperties=font_prop), fontfamily=plt.rcParams['font.family'], fontsize=12)
                    ax.set_ylabel(get_graph_text(f"{trend_metric} ({agg_period_display}平均, fontproperties=font_prop)", f"{trend_metric} ({agg_period_display} Average)"), fontfamily=plt.rcParams['font.family'], fontsize=12)
                    ax.legend(prop={'family':plt.rcParams['font.family']}, fontproperties=font_prop)
                    plt.tight_layout()
                    st.pyplot(fig)
                else:
                    plt.close(fig) 


            except Exception as e:
                st.error(get_localized_text(f"時系列分析中にエラーが発生: {e}", f"An error occurred during time series analysis: {e}"))
        else:
            st.warning(get_localized_text("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。", "No data uploaded or no data after filtering. Please upload files in the Data Management tab."))


    with tabs[5]:
        st.header(get_localized_text("🏆 ランキング分析", "🏆 Ranking Analysis"))

        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()

            numeric_cols = df.select_dtypes(include='number').columns.tolist()
            cat_cols = df.select_dtypes(include='object').columns.tolist()

            if not numeric_cols:
                st.warning(get_localized_text("数値列がありません。", "No numeric columns found."))
                st.stop()
            if not cat_cols:
                st.warning(get_localized_text("カテゴリ列がありません。", "No categorical columns found."))
                st.stop()

            col1, col2 = st.columns(2)
            with col1:
                rank_metric = st.selectbox(
                    get_localized_text("ランキング対象の指標", "Metric for Ranking"), 
                    numeric_cols,
                    key="rank_metric"
                )
                rank_group = st.selectbox(
                    get_localized_text("グループ化", "Group By"),
                    cat_cols,
                    key="rank_group"
                )

            with col2:
                top_n = st.number_input(
                    get_localized_text("表示件数", "Number of Items to Display"),
                    min_value=1,
                    max_value=50,
                    value=10,
                    key="rank_topn"
                )
                ascending_option = st.radio(
                    get_localized_text("並び順", "Sort Order"),
                    [get_localized_text("降順（大きい順）", "Descending (Largest First)"), get_localized_text("昇順（小さい順）", "Ascending (Smallest First)")],
                    index=0,
                    key="rank_order"
                )

            if st.button(get_localized_text("ランキングを表示", "Show Ranking"), key="rank_execute"):
                try:
                    if rank_group not in df.columns or rank_metric not in df.columns:
                        st.error(get_localized_text("選択された列がデータフレームに存在しません。", "Selected columns do not exist in the dataframe."))
                        st.stop()

                    rank_df = df.groupby(rank_group)[rank_metric].agg(['mean', 'count']).round(2)
                    rank_df.columns = [get_localized_text('平均値', 'Mean Value'), get_localized_text('データ数', 'Data Count')]
                    rank_df = rank_df.sort_values(
                        get_localized_text('平均値', 'Mean Value'),
                        ascending=(ascending_option == get_localized_text("昇順（小さい順）", "Ascending (Smallest First)"))
                    )

                    st.subheader(get_localized_text("📊 ランキング結果", "📊 Ranking Results"))
                    rank_display = rank_df.head(top_n).copy()
                    rank_display.index.name = rank_group
                    st.dataframe(rank_display)

                    fig, ax = plt.subplots(figsize=(10, max(5, top_n * 0.3)))
                    rank_display[get_localized_text('平均値', 'Mean Value')].plot(kind='barh', ax=ax)
                    ax.set_title(get_graph_text(f"{rank_group}別 {rank_metric}のランキング", f"Ranking of {rank_metric} by {rank_group}", fontproperties=font_prop), fontfamily=plt.rcParams['font.family'], fontsize=16)
                    ax.set_xlabel(get_graph_text(f"{rank_metric} 平均値", f"{rank_metric} Mean Value", fontproperties=font_prop), fontfamily=plt.rcParams['font.family'], fontsize=12)
                    ax.set_ylabel(get_graph_text(rank_group, rank_group, fontproperties=font_prop), fontfamily=plt.rcParams['font.family'], fontsize=12) # Group name is data, keep as is
                    
                    for label in ax.get_xticklabels():
                        label.set_fontfamily(plt.rcParams['font.family'])
                    for label in ax.get_yticklabels():
                        label.set_fontfamily(plt.rcParams['font.family'])

                    plt.tight_layout()
                    st.pyplot(fig)

                    csv = rank_display.to_csv(encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        get_localized_text("📥 ランキングデータをCSVで保存", "📥 Save Ranking Data as CSV"),
                        csv,
                        file_name="ranking_data.csv",
                        mime='text/csv',
                        key="rank_download"
                    )

                    st.subheader(get_localized_text("📈 特徴的なデータ", "📈 Characteristic Data"))

                    if not rank_display.empty:
                        top_item = rank_display.index[0]
                        top_val = rank_display.loc[top_item, get_localized_text('平均値', 'Mean Value')]
                        st.info(get_localized_text(
                            f"🏆 トップの{rank_group}: {top_item} ({top_val:.2f})",
                            f"🏆 Top {rank_group}: {top_item} ({top_val:.2f})"
                        ))

                        if len(rank_display) > 1:
                            second_item = rank_display.index[1]
                            second_val = rank_display.loc[second_item, get_localized_text('平均値', 'Mean Value')]
                            if pd.notna(top_val) and pd.notna(second_val):
                                diff = top_val - second_val
                                if second_val != 0:
                                    st.info(get_localized_text(
                                        f"2位との差: {diff:.2f} ({(diff/second_val*100):.1f}%)",
                                        f"Difference from 2nd place: {diff:.2f} ({(diff/second_val*100):.1f}%)"
                                    ))
                                else:
                                    st.info(get_localized_text(
                                        f"2位との差: {diff:.2f} (2位の値が0のため変化率を計算できません)",
                                        f"Difference from 2nd place: {diff:.2f} (Cannot calculate percentage change as 2nd place value is 0)"
                                    ))
                            else:
                                st.info(get_localized_text("トップまたは2位の値が欠損しているため、差を計算できません。", "Cannot calculate difference as top or second place value is missing."))
                    else:
                        st.info(get_localized_text("ランキングデータが空のため、特徴的なデータを特定できません。", "Ranking data is empty, cannot identify characteristic data."))

                except Exception as e:
                    st.error(get_localized_text(f"ランキング分析中にエラーが発生: {e}", f"An error occurred during ranking analysis: {e}"))
        else:
            st.warning(get_localized_text("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。", "No data uploaded or no data after filtering. Please upload files in the Data Management tab."))

    with tabs[6]:
        st.header(get_localized_text("📋 自動レポート", "📋 Automatic Report"))

        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()

            if '参加率(%)' not in df.columns and '申込数' in df.columns and '参加者数' in df.columns:
                df['参加率(%)'] = (df['参加者数'] / df['申込数']) * 100
            if '満足率(%)' not in df.columns and '満足回答' in df.columns and '参加者数' in df.columns:
                df['満足率(%)'] = (df['満足回答'] / df['参加者数']) * 100
            # 修正: 'not in in' を 'not in' に変更
            if 'リアクション率' not in df.columns and '参加者数' in df.columns:
                df['リアクション率'] = df['リアクション数'] / df['参加者数']

            df = DataProcessor.expand_time_slots(df)

            st.subheader(get_localized_text("📣 参加者数を増やすためのデータ分析", "📣 Data Analysis for Increasing Participants"))

            def append_section_to_report(title_jp, df_to_use):
                title_en = ""
                if title_jp == "参加者数が多いチーム":
                    title_en = "Teams with High Participants"
                elif title_jp == "曜日別の参加者数":
                    title_en = "Participants by Day of Week"
                elif title_jp == "時間帯別の参加者数":
                    title_en = "Participants by Time Slot"
                elif title_jp == "参加率が高いイベント":
                    title_en = "Events with High Participation Rate"
                elif title_jp == "満足度が高いイベント":
                    title_en = "Events with High Satisfaction Rate"
                elif title_jp == "参加者数が少ない曜日":
                    title_en = "Weekdays with Low Participants"
                
                st.markdown(get_localized_text(f"#### {title_jp}", f"#### {title_en}"))
                st.dataframe(df_to_use, use_container_width=True) # use_container_width=True を追加


            st.markdown(get_localized_text("### 🏆 ランキングまとめ", "### 🏆 Ranking Summary"))
            if '担当チーム' in df.columns and '参加者数' in df.columns:
                team_avg = df.groupby("担当チーム")["参加者数"].mean().sort_values(ascending=False).reset_index()
                append_section_to_report("参加者数が多いチーム", team_avg)
            else:
                st.info(get_localized_text("「担当チーム」または「参加者数」の列がありません。", "The '担当チーム' (Responsible Team) or '参加者数' (Participants) column is missing."))

            if '曜日' in df.columns and '参加者数' in df.columns:
                weekday_avg = df.groupby("曜日")["参加者数"].mean().sort_values(ascending=False).reindex(index=['月', '火', '水', '木', '金', '土', '日']).dropna().reset_index()
                append_section_to_report("曜日別の参加者数", weekday_avg)
            else:
                st.info(get_localized_text("「曜日」または「参加者数」の列がありません。", "The '曜日' (Weekday) or '参加者数' (Participants) column is missing."))

            if '時間帯スロット' in df.columns and '参加者数' in df.columns:
                time_avg = df.groupby("時間帯スロット")["参加者数"].mean().sort_values(ascending=False).reset_index()
                append_section_to_report("時間帯別の参加者数", time_avg)
            else:
                st.info(get_localized_text("「時間帯スロット」または「参加者数」の列がありません。", "The '時間帯スロット' (Time Slot) or '参加者数' (Participants) column is missing."))


            if '参加率(%)' in df.columns:
                cols_for_top_rate = [col for col in ["イベント名", "曜日", "時間帯スロット", "参加率(%)"] if col in df.columns]
                top_rate = df.sort_values("参加率(%)", ascending=False).head(5)[cols_for_top_rate].reset_index(drop=True)
                top_rate.index += 1
                append_section_to_report("参加率が高いイベント", top_rate)
            else:
                st.info(get_localized_text("「参加率(%)」の列がありません。", "The '参加率(%)' (Participation Rate (%)) column is missing."))

            if '満足率(%)' in df.columns:
                cols_for_top_satisfaction = [col for col in ["イベント名", "曜日", "時間帯スロット", "満足率(%)"] if col in df.columns]
                top_satisfaction = df.sort_values("満足率(%)", ascending=False).head(5)[cols_for_top_satisfaction].reset_index(drop=True)
                top_satisfaction.index += 1
                append_section_to_report("満足度が高いイベント", top_satisfaction)
            else:
                st.info(get_localized_text("「満足率(%)」の列がありません。", "The '満足率(%)' (Satisfaction Rate (%)) column is missing."))

            if '曜日' in df.columns and '参加者数' in df.columns:
                low_participation_raw = df.groupby("曜日")["参加者数"].mean().sort_values().reset_index()
                low_participation = low_participation_raw.head(3).copy()
                low_participation.index += 1
                append_section_to_report("参加者数が少ない曜日", low_participation)
            else:
                st.info(get_localized_text("「曜日」または「参加者数」の列がありません。", "The '曜日' (Weekday) or '参加者数' (Participants) column is missing."))

            st.markdown(get_localized_text("### 💡 宣伝・リアクションと参加者数の関係", "### 💡 Relationship between Promotion/Reactions and Participants"))
            
            corr_summary_text = []
            if '宣伝回数' in df.columns and '参加者数' in df.columns:
                corr1 = df['参加者数'].corr(df['宣伝回数'])
                if pd.notna(corr1):
                    corr_summary_text.append(get_localized_text(f"「宣伝回数」と「参加者数」の相関: {corr1:.2f}", f"Correlation between '宣伝回数' (Promotion Count) and '参加者数' (Participants): {corr1:.2f}"))
                else:
                    corr_summary_text.append(get_localized_text("「宣伝回数」と「参加者数」の相関は計算できませんでした（データ不足または定数）。", "Correlation between '宣伝回数' (Promotion Count) and '参加者数' (Participants) could not be calculated (insufficient data or constant)."))
            else:
                corr_summary_text.append(get_localized_text("「宣伝回数」の列が見つかりませんでした。", "The '宣伝回数' (Promotion Count) column was not found."))

            if 'リアクション率' in df.columns and '参加者数' in df.columns:
                corr2 = df['参加者数'].corr(df['リアクション率'])
                if pd.notna(corr2):
                    corr_summary_text.append(get_localized_text(f"「リアクション率」と「参加者数」の相関: {corr2:.2f}", f"Correlation between 'リアクション率' (Reaction Rate) and '参加者数' (Participants): {corr2:.2f}"))
                else:
                    corr_summary_text.append(get_localized_text("「リアクション率」と「参加者数」の相関は計算できませんでした（データ不足または定数）。", "Correlation between 'リアクション率' (Reaction Rate) and '参加者数' (Participants) could not be calculated (insufficient data or constant)."))
            else:
                st.info(get_localized_text("「リアクション率」の列が見つかりませんでした。", "The 'リアクション率' (Reaction Rate) column was not found."))
            
            for line in corr_summary_text:
                st.info(line)


        else:
            st.warning(get_localized_text("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。", "No data uploaded or no data after filtering. Please upload files in the Data Management tab."))


# --- アプリケーションのエントリポイント ---
def main():
    # Streamlitのページ設定は一度だけ行う
    st.set_page_config(page_title=get_localized_text("VRイベント分析ツール", "VR Event Analysis Tool"), layout="wide")

    # セッションステートにlogged_inがなければ初期化（アプリケーション起動時にのみFalseに設定）
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if st.session_state.get("logged_in"):
        # ログイン済みの場合、ユーザー名を表示し、ログアウトボタンとメインアプリを表示
        st.sidebar.markdown(get_localized_text(f"**ようこそ、{st.session_state.get('username')} さん！**", f"**Welcome, {st.session_state.get('username')}!**"))
        if st.sidebar.button(get_localized_text("ログアウト", "Logout")):
            # ログアウト処理
            for key in ["logged_in", "username", "num_uploaders"]: # num_uploadersもクリア
                st.session_state.pop(key, None)
            st.rerun()
        show_main_app()
    else:
        # 未ログインの場合、ログインフォームを表示
        login_form()

if __name__ == "__main__":
    main()
