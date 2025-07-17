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

plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['IPAexGothic', 'Noto Sans CJK JP', 'MS Gothic', 'Yu Gothic', 'Meiryo']

st.set_page_config(page_title="VRイベント分析ツール", layout="wide")

class SessionManager:
    @staticmethod
    def initialize():
        session_vars = {
            'upload_files': [],
            'template_store': [],
            'analysis_log': [],
            'comparison_template': {},
            'current_data': None,
            'selected_teams': None,
            'date_range': [None, None],
            'analysis_count': 0,
            'heatmap_count': 0,
            'trend_count': 0,
            'ranking_count': 0,
            'dfmain': None,
            'uploaded_file_processed': False,
            'num_uploaders': 1,
            'previous_files_hash': None,
            'logged_in': False,
            'username': None
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
                return None, f"読み込みエラー: {str(e)}"
        except Exception as e:
            return None, f"読み込みエラー: {str(e)}"

    @staticmethod
    def process_dataframe(df):
        if df is None:
            return None
            
        if '実施日' in df.columns:
            initial_nan_count = df['実施日'].isnull().sum()
            df['実施日'] = pd.to_datetime(df['実施日'], errors='coerce')
            df['実施日'] = df['実施日'].dt.normalize().dt.date 

            nan_after_coerce = df['実施日'].isnull().sum()
            
            if nan_after_coerce > initial_nan_count:
                newly_coerced_nan_percentage = (nan_after_coerce - initial_nan_count) / len(df) * 100
                if newly_coerced_nan_percentage > 10:
                    st.warning(f"「実施日」列の{newly_coerced_nan_percentage:.1f}%が日付として認識できませんでした。元のデータ形式を確認してください。")

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
            df = df.explode('時間帯スロット').reset_index(drop=True)
            df['時間帯スロット'] = df['時間帯スロット'].str.strip()
        return df

# ユーザー情報をStreamlit secretsからロードする関数
def load_users_from_secrets():
    users_data = []
    if 'users' in st.secrets:
        # デバッグ行：st.secrets.usersの型と内容を表示
        st.write("デバッグ: st.secrets.users の型:", type(st.secrets.users))
        st.write("デバッグ: st.secrets.users の内容:", st.secrets.users)

        # AttrDictはkeys()メソッドを持つため、直接ループしてアクセスします
        # isinstance(st.secrets.users, dict) のチェックは不要です
        for username_key in st.secrets.users.keys():
            if username_key.startswith("user_"):
                raw_value = st.secrets.users[username_key]

                # secrets.toml内で文字列（JSON）として登録されている場合はデコードする
                if isinstance(raw_value, str):
                    try:
                        user_info = json.loads(raw_value)
                    except json.JSONDecodeError:
                        st.error(f"{username_key} のJSONデコードに失敗しました")
                        continue
                else:
                    user_info = raw_value  # すでに辞書形式の場合はそのまま使う

                if 'username' in user_info and 'password_hash' in user_info:
                    users_data.append(user_info)
                else:
                    st.warning(f"{username_key} のデータ形式が不正です")
            else:
                st.warning(f"予期しないキー '{username_key}' が users にあります")

    
    # ユーザーが一人もロードされなかった場合の最終エラーチェック
    if not users_data:
        st.error("Streamlit secretsにユーザー情報が設定されていないか、形式が不正です。")
    # デバッグ行：最終的にロードされたユーザーデータを表示
    st.write("デバッグ: ロードされたユーザーデータ:", users_data)

    return users_data

# パスワードをハッシュ化する関数
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# パスワードを検証する関数
def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def main():
    st.title("VRイベント分析アプリ")

    SessionManager.initialize()

    if not st.session_state.logged_in:
        st.sidebar.header("ログイン")
        username_input = st.sidebar.text_input("ユーザー名")
        password_input = st.sidebar.text_input("パスワード", type="password")

        st.write("デバッグ: ユーザー名比較", "user側:", user['username'], "| 入力:", username_input)

        if st.sidebar.button("ログイン"):
            # --- ここから追加 ---
            st.write("デバッグ: 入力されたユーザー名:", username_input)
            st.write("デバッグ: 入力されたパスワード（ハッシュ化前）:", password_input) # !!! 注意: デバッグ後必ず削除 !!!
            # --- ここまで追加 ---

            users = load_users_from_secrets() # secretsからユーザー情報をロード
            user_found = False
            for user in users:
                # --- ここから追加 ---
                st.write("デバッグ: secretsから取得したユーザー情報:", user['username'], user.get('password_hash', 'ハッシュなし')) # パスワードハッシュを直接表示しない
                # --- ここまで追加 ---

                if user['username'] == username_input:
                    user_found = True
                    password_match = verify_password(password_input, user['password_hash'])
                
                    st.write("デバッグ: パスワード一致した？", password_match)
                
                    if password_match:
                        st.session_state.logged_in = True
                        st.session_state.username = username_input
                        st.sidebar.success(f"ようこそ、{username_input}さん！")
                        st.experimental_rerun()
                    else:
                        st.sidebar.error("パスワードが間違っています。")
                    break



                    break
            if not user_found:
                st.sidebar.error("ユーザー名が見つかりません。")

            st.info("ログインするとアプリケーションの機能が利用できます。")
            return

    with st.sidebar:
        st.markdown(f"**ログイン中:** {st.session_state.username}")
        if st.button("ログアウト"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.selected_teams = None
            st.session_state.dfmain = None
            st.session_state.current_data = None
            st.session_state.upload_files = []
            st.session_state.uploaded_file_processed = False
            st.session_state.num_uploaders = 1
            st.session_state.previous_files_hash = None
            st.experimental_rerun()


    with st.sidebar:
        st.markdown("## 🔍 フィルター設定")
        st.markdown("---")

        dfmain_for_sidebar = st.session_state.get('dfmain')

        if dfmain_for_sidebar is not None and not dfmain_for_sidebar.empty:
            df_filtered = dfmain_for_sidebar.copy()

            if '担当チーム' in df_filtered.columns:
                teams = sorted(df_filtered['担当チーム'].dropna().unique())
                
                initial_selected_teams = st.session_state.get('selected_teams')
                if initial_selected_teams is None:
                    initial_selected_teams = teams
                
                selected_teams = st.multiselect(
                    "👥 担当チーム", 
                    teams, 
                    default=[t for t in initial_selected_teams if t in teams]
                )
                st.session_state.selected_teams = selected_teams

                if len(selected_teams) == 0:
                    st.warning("担当チームが選択されていません。全ての担当チームのデータが表示されます。")
                else:
                    df_filtered = df_filtered[df_filtered['担当チーム'].isin(selected_teams)]

            if '実施日' in df_filtered.columns:
                valid_dates = df_filtered['実施日'].dropna()
                if not valid_dates.empty:
                    min_date = min(valid_dates)
                    max_date = max(valid_dates)
                    
                    default_date_range = [min_date, max_date] if min_date <= max_date else [min_date, min_date]
                    date_range = st.date_input("📅 実施日の範囲", value=default_date_range)
                    
                    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                        start, end = date_range[0], date_range[1]
                        df_filtered = df_filtered[
                            (df_filtered['実施日'] >= start) & 
                            (df_filtered['実施日'] <= end)
                        ]
                else:
                    st.warning("日付データがありません。")
            
            st.session_state.current_data = df_filtered

        else:
            st.info("データをアップロードしてください")

    tabs = st.tabs(["📊 データ管理", "📈 分析・比較", "📊 クロス集計", "🕒 ヒートマップ", "📉 時系列", "🏆 ランキング", "📋 自動レポート"])

    with tabs[0]:
        st.header("📁 分析対象CSVファイルのアップロード")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            all_uploaded_files_current_run = [] 
            uploader_objects = [] 
            last_uploaded_idx = -1 

            for i in range(st.session_state.num_uploaders):
                label = "CSVファイル (必須)" if i == 0 else f"追加のCSVファイル (オプション {i})"
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
                        st.error(f"ファイル {f.name}: {error}")
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
                        st.warning(f"以下の数値列で高い欠損率が検出されました: {', '.join(high_nan_cols)}。\n"
                                   "これは、元のCSVファイルの該当列に数値以外のデータが多く含まれている可能性があります。"
                                   "データの正確性を確認してください。")
                else:
                    st.session_state['dfmain'] = None
                    st.session_state.current_data = None
                    st.session_state.uploaded_file_processed = True
            
        df_display = st.session_state.get('current_data')
        if df_display is None or df_display.empty:
            st.warning("データがアップロードされていないか、フィルターによってデータがありません。")
        else:
            if st.session_state.upload_files:
                with col2:
                    st.markdown("### 📊 ファイル情報")
                    for i, f in enumerate(all_uploaded_files_current_run, 1):
                        if f is not None:
                            display_name = f.name if hasattr(f, 'name') else f"ファイル {i}"
                            st.info(f"ファイル {i}: {display_name}")

                if len(st.session_state.upload_files) > 1: 
                    st.markdown("### 🔄 データ統合結果")
                    total_rows_before = 0
                    for f in st.session_state.upload_files:
                        f.seek(0)
                        temp_df, _ = DataProcessor.safe_read_csv(f)
                        if temp_df is not None:
                            total_rows_before += len(temp_df)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("アップロードされた全てのデータ数", f"{total_rows_before}行")
                    with col2:
                        st.metric("統合後のデータ数", f"{len(df_display)}行")
                    with col3:
                        removed_rows = total_rows_before - len(df_display)
                        if removed_rows > 0:
                            st.metric("重複削除", f"{removed_rows}行")
                            st.info(f"※ {removed_rows}行の重複（全ての列が完全に一致する行）を削除しました。")
                else:
                    st.info(f"単一ファイル（{len(df_display)}行）を処理します")

            st.markdown("### 📋 データプレビュー")
            preview_rows = st.number_input(
                "表示する行数（0で全行表示）",
                min_value=0,
                max_value=len(df_display),
                value=5
            )
            
            if preview_rows == 0:
                st.dataframe(df_display, use_container_width=True)
            else:
                st.dataframe(df_display.head(preview_rows), use_container_width=True)

            st.markdown("### 📋 列情報")
            col_info = pd.DataFrame({
                'データ型': df_display.dtypes,
                '欠損値数': df_display.isnull().sum(),
                '欠損率(%)': (df_display.isnull().sum() / len(df_display) * 100).round(2),
                'ユニーク値数': df_display.nunique(),
            })
            st.dataframe(col_info)

            st.markdown("### 📊 基本統計量")
            numeric_cols = df_display.select_dtypes(include=['int64', 'float64']).columns
            if not numeric_cols.empty:
                stats_df = df_display[numeric_cols].describe().T

                rename_map = {
                    "count": "データ数",
                    "mean": "平均",
                    "std": "標準偏差",
                    "min": "最小値",
                    "25%": "25%",
                    "50%": "中央値",
                    "75%": "75%",
                    "max": "最大値"
                }

                stats_df = stats_df.rename(columns=rename_map)
                st.dataframe(stats_df)


            st.markdown("### 📊 カテゴリ列の内訳")
            category_cols = df_display.select_dtypes(include=['object']).columns
            if not category_cols.empty:
                selected_col = st.selectbox("確認する列を選択", category_cols)
                value_counts = df_display[selected_col].value_counts()
                
                fig, ax = plt.subplots(figsize=(10, 5))
                value_counts.plot(kind='bar', ax=ax)
                
                title_font = {'fontfamily': 'MS Gothic', 'fontsize': 12}
                ax.set_title(f"{selected_col}の値カウント", **title_font)
                ax.set_xlabel(selected_col, fontfamily='MS Gothic')
                ax.set_ylabel("カウント", fontfamily='MS Gothic')
                
                for label in ax.get_xticklabels():
                    label.set_fontfamily('MS Gothic')
                for label in ax.get_yticklabels():
                    label.set_fontfamily('MS Gothic')
                
                plt.xticks(rotation=45)
                plt.tight_layout()
                st.pyplot(fig)

    with tabs[1]:
        st.header("📈 分析・比較")
        
        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()
            
            col1, col2 = st.columns(2)
            with col1:
                num_cols = df.select_dtypes(include='number').columns.tolist()
                cat_cols = df.select_dtypes(include='object').columns.tolist()
                
                if not num_cols:
                    st.warning("数値列がありません。")
                    st.stop()
                if not cat_cols:
                    st.warning("カテゴリ列がありません。")
                    st.stop()

                target_num = st.selectbox("分析対象（数値）", num_cols)
                group_col = st.selectbox("グループ化（カテゴリ）", cat_cols)

            with col2:
                agg_options = ['平均', '合計', '中央値', '最大', '最小', 'データ数']
                selected_aggs = st.multiselect(
                    "表示する統計指標",
                    agg_options,
                    default=agg_options
                )
                exclude_outliers = st.checkbox("外れ値を除外")

            try:
                analysis_df = df.copy()
                
                if exclude_outliers and target_num in analysis_df.columns and analysis_df[target_num].std() > 0:
                    z_scores = np.abs((analysis_df[target_num] - analysis_df[target_num].mean()) / 
                                    analysis_df[target_num].std())
                    analysis_df = analysis_df[z_scores < 3]
                elif exclude_outliers:
                    st.info(f"'{target_num}'のデータにばらつきがないため、外れ値除外は適用されませんでした。")


                agg_map = {
                    '平均': 'mean', '合計': 'sum', '中央値': 'median',
                    '最大': 'max', '最小': 'min', 'データ数': 'count'
                }
                
                if not selected_aggs:
                    selected_aggs = agg_options

                agg_funcs_list = [agg_map[a] for a in selected_aggs if a in agg_map] 

                if group_col in analysis_df.columns and target_num in analysis_df.columns:
                    grouped_df = analysis_df.groupby(group_col)[target_num].agg(agg_funcs_list)
                    
                    rename_dict = {agg_map[a]: f"{target_num}_{a}" for a in selected_aggs if a in agg_map}
                    filtered_rename_dict = {k: v for k, v in rename_dict.items() if k in grouped_df.columns}
                    grouped_df.rename(columns=filtered_rename_dict, inplace=True)

                else:
                    st.error("選択された列がデータフレームに存在しません。")
                    grouped_df = pd.DataFrame()

                if not grouped_df.empty:
                    st.markdown("### 📊 グループ別集計結果")
                    st.dataframe(grouped_df.round(2), use_container_width=True)

                    if selected_aggs:
                        st.markdown("### 📈 統計指標別グラフ")
                        cols = st.columns(2)
                        for i, metric in enumerate(selected_aggs):
                            col_name_for_plot = f"{target_num}_{metric}" 
                            if col_name_for_plot in grouped_df.columns:
                                with cols[i % 2]:
                                    fig, ax = plt.subplots(figsize=(8, 4))
                                    grouped_df[col_name_for_plot].plot(kind='bar', ax=ax)
                                    ax.set_ylabel(f"{target_num}の{metric}")
                                    ax.set_title(f"{group_col}ごとの{target_num}（{metric}）")
                                    plt.xticks(rotation=45)
                                    plt.tight_layout()
                                    st.pyplot(fig)

                                    buf = io.BytesIO()
                                    fig.savefig(buf, format='png')
                                    st.download_button(
                                        f"📥 {metric}のグラフを保存",
                                        buf.getvalue(),
                                        f"analysis_{metric}.png",
                                        "image/png"
                                    )
                else:
                    st.warning("集計結果がありません。フィルター設定またはデータを確認してください。")

            except Exception as e:
                st.error(f"分析エラー: {e}")
        else:
            st.warning("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。")

    with tabs[2]:
        st.header("📊 クロス集計")

        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()

            cat_cols = df.select_dtypes(include='object').columns.tolist()
            num_cols = df.select_dtypes(include='number').columns.tolist()

            if len(cat_cols) < 2:
                st.warning("クロス集計には2つ以上のカテゴリ列が必要です。")
                st.stop()
            if not num_cols:
                st.warning("数値列がありません。")
                st.stop()

            col1 = st.selectbox("行カテゴリ", cat_cols, key="cross_row")
            col2_options = [c for c in cat_cols if c != col1]
            if not col2_options:
                st.warning(f"'{col1}' 以外のカテゴリ列がありません。")
                st.stop()
            col2 = st.selectbox("列カテゴリ", col2_options, key="cross_col")
            
            num_col = st.selectbox("数値項目", num_cols, key="cross_num")
            agg_method = st.selectbox("集計方法", ['平均', '合計', '中央値', '最大', '最小', 'データ数'], key="cross_agg")

            if st.button("クロス集計を実行", key="cross_execute"):
                try:
                    agg_map = {
                        '平均': 'mean',
                        '合計': 'sum',
                        '中央値': 'median',
                        '最大': 'max',
                        '最小': 'min',
                        'データ数': 'count'
                    }

                    if col1 in df.columns and col2 in df.columns and num_col in df.columns:
                        cross_table = pd.pivot_table(
                            df,
                            values=num_col,
                            index=col1,
                            columns=col2,
                            aggfunc=agg_map[agg_method]
                        )
                        if isinstance(cross_table.columns, pd.MultiIndex):
                            cross_table.columns = cross_table.columns.droplevel(0)

                        st.dataframe(cross_table)

                        fig, ax = plt.subplots(figsize=(10, 5))
                        cross_table.plot(kind='bar', ax=ax)
                        ax.set_ylabel(num_col)
                        ax.set_title(f"{col1} × {col2} の {agg_method}")
                        plt.xticks(rotation=45)
                        plt.tight_layout()
                        st.pyplot(fig)

                        csv = cross_table.to_csv(encoding='utf-8-sig').encode('utf-8-sig')
                        st.download_button(
                            "📥 クロス集計結果をCSVで保存",
                            csv,
                            file_name="cross_table.csv",
                            mime='text/csv',
                            key="cross_download"
                        )
                    else:
                        st.error("選択された列がデータフレームに存在しません。")

                except Exception as e:
                    st.error(f"クロス集計の実行に失敗しました: {e}")
        else:
            st.warning("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。")


    with tabs[3]:
        st.header("🟥 ヒートマップ")

        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()

            df = DataProcessor.expand_time_slots(df)

            if '時間帯スロット' not in df.columns or '曜日' not in df.columns:
                st.warning("ヒートマップを作成するには「時間帯」と「曜日」の列が必要です。")
                st.stop()
            
            if not all(col in df.columns for col in ['時間帯スロット', '曜日']):
                st.warning("ヒートマップの作成に必要な列（時間帯スロット、曜日）がデータに存在しません。")
                st.stop()


            numeric_cols = df.select_dtypes(include='number').columns.tolist()
            if not numeric_cols:
                st.warning("数値列がありません。ヒートマップは数値データに基づいています。")
                st.stop()

            col1, col2 = st.columns(2)
            with col1:
                heat_metric = st.selectbox(
                    "集計する指標",
                    numeric_cols,
                    key="heat_metric"
                )
                agg_method = st.selectbox(
                    "集計方法",
                    ['平均', '合計', 'データ数'],
                    key="heat_agg"
                )

            with col2:
                color_scale = st.selectbox(
                    "カラースケール",
                    ['YlOrRd', 'viridis', 'coolwarm'],
                    key="heat_color"
                )
                normalize = st.checkbox("データを正規化", value=True, key="heat_normalize")

            if st.button("ヒートマップを生成", key="heat_execute"):
                try:
                    heat_df = df.copy()

                    agg_map = {'平均': 'mean', '合計': 'sum', 'データ数': 'count'}
                    pivot_table = pd.pivot_table(
                        heat_df,
                        values=heat_metric,
                        index='時間帯スロット',
                        columns='曜日',
                        aggfunc=agg_map[agg_method]
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
                    elif normalize and not pivot_table.empty:
                        st.info("データにばらつきがないため、ヒートマップの正規化はスキップされました。")


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

                    ax.set_title(f"時間帯×曜日の{heat_metric}（{agg_method}）", fontfamily='MS Gothic', fontsize=16)
                    ax.set_xlabel("曜日", fontfamily='MS Gothic', fontsize=12)
                    ax.set_ylabel("時間帯スロット", fontfamily='MS Gothic', fontsize=12)

                    for label in ax.get_xticklabels():
                        label.set_fontfamily('MS Gothic')
                    for label in ax.get_yticklabels():
                        label.set_fontfamily('MS Gothic')

                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig)

                    csv = pivot_table.to_csv(encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        "📥 ヒートマップデータをCSVで保存",
                        csv,
                        file_name="heatmap_data.csv",
                        mime='text/csv',
                        key="heat_download"
                    )

                    st.subheader("📊 特徴的なパターン")

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
                            st.info(f"🔺 最も{heat_metric}が高い時間帯: "
                                    f"{max_pos_df[0]}の{max_pos_df[1]}曜日"
                                    f" ({max_val:.2f})")
                        else:
                            st.info("🔺 最も高い値のパターンを特定できませんでした。")

                        if not np.isnan(min_val) and not pivot_table[pivot_table == min_val].empty:
                            min_pos_df = pivot_table[pivot_table == min_val].stack().index[0]
                            st.info(f"🔻 最も{heat_metric}が低い時間帯: "
                                    f"{min_pos_df[0]}の{min_pos_df[1]}曜日"
                                    f" ({min_val:.2f})")
                        else:
                            st.info("🔻 最も低い値のパターンを特定できませんでした。")
                    else:
                        st.info("ヒートマップデータが空のため、特徴的なパターンを特定できません。")


                except Exception as e:
                    st.error(f"ヒートマップ生成中にエラーが発生: {e}")
        else:
            st.warning("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。")


    with tabs[4]:
        st.header("📉 時系列分析")

        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()

            if '実施日' not in df.columns:
                st.warning("時系列分析には「実施日」の列が必要です。")
                st.stop()
            
            df = df.dropna(subset=['実施日'])

            if df.empty:
                st.warning("有効な日付データがありません。")
                st.stop()

            df['実施日_timestamp'] = pd.to_datetime(df['実施日'])


            cat_cols = df.select_dtypes(include='object').columns.tolist()
            numeric_cols = df.select_dtypes(include='number').columns.tolist()

            if not numeric_cols:
                st.warning("数値列がありません。時系列分析は数値データに基づいています。")
                st.stop()

            col1, col2 = st.columns(2)
            with col1:
                trend_metric = st.selectbox(
                    "分析する指標",
                    numeric_cols,
                    key="trend_metric"
                )
                trend_group = st.selectbox(
                    "グループ化（オプション）",
                    ['なし'] + cat_cols,
                    key="trend_group"
                )

            with col2:
                agg_period = st.selectbox(
                    "集計期間",
                    ['日次', '週次', '月次'],
                    key="trend_period"
                )
                moving_avg = st.number_input(
                    "移動平均期間", 
                    min_value=1,
                    max_value=30,
                    value=7,
                    key="trend_ma"
                )

            try:
                trend_df = df.copy()
                
                period_map = {'日次': 'D', '週次': 'W', '月次': 'M'}

                fig, ax = plt.subplots(figsize=(12, 6))
                has_data_to_plot = False 

                if trend_group == 'なし':
                    resampled = trend_df.set_index('実施日_timestamp')[trend_metric].resample(period_map[agg_period]).mean()
                    
                    if not resampled.empty:
                        resampled.plot(ax=ax, label=f'{agg_period}平均')
                        moving = resampled.rolling(window=moving_avg, min_periods=1).mean() 
                        if not moving.empty:
                            moving.plot(ax=ax, label=f'{moving_avg}{agg_period[0]}移動平均', style='--') 
                        else:
                            st.info("移動平均を計算する十分なデータがありません。")
                        has_data_to_plot = True
                    else:
                        st.warning("集計データが空のため、時系列グラフを生成できませんでした。")
                    
                    if not resampled.empty:
                        st.subheader("📊 時系列の特徴")
                        latest_val = resampled.iloc[-1]
                        prev_val = resampled.iloc[-2] if len(resampled) > 1 else None

                        st.info(f"最新の{agg_period}平均: {latest_val:.2f}")
                        if prev_val is not None and prev_val != 0:
                            change = ((latest_val - prev_val) / prev_val * 100)
                            st.info(f"直近の{agg_period}からの変化率: {change:.1f}%")
                        else:
                            st.info("直近の変化率を計算するデータがありません。")
                    else:
                        st.info("集計データが空のため、特徴を抽出できません。")

                    if not resampled.empty:
                        csv = resampled.to_csv(encoding='utf-8-sig').encode('utf-8-sig')
                        st.download_button(
                            "📥 時系列データをCSVで保存",
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
                                        resampled = group_data.set_index('実施日_timestamp')[trend_metric].resample(period_map[agg_period]).mean()
                                        if not resampled.empty:
                                            resampled.plot(ax=ax, label=str(group))
                                            moving = resampled.rolling(window=moving_avg, min_periods=1).mean()
                                            if not moving.empty:
                                                moving.plot(ax=ax, label=f'{str(group)} ({moving_avg}{agg_period[0]}移動平均)', style='--') 
                                            else:
                                                st.info(f"グループ '{group}' の移動平均を計算する十分なデータがありません。")
                                            has_data_to_plot = True
                                        else:
                                            st.warning(f"グループ '{group}' のデータが不足しているため、時系列グラフを生成できませんでした。")
                                    else:
                                        st.warning(f"グループ '{group}' のデータがありません。")
                            
                            if not has_data_to_plot:
                                st.warning("選択されたグループのいずれも時系列データをプロットできませんでした。")
                        else:
                            st.warning(f"選択されたグループ列 '{trend_group}' に有効な値がありません。")
                    else:
                        st.error(f"選択されたグループ列 '{trend_group}' がデータフレームに存在しません。")

                if has_data_to_plot:
                    ax.set_title(f"{trend_metric}の時系列 ({'全体' if trend_group == 'なし' else trend_group}別)", fontfamily='MS Gothic', fontsize=16)
                    ax.set_xlabel("実施日", fontfamily='MS Gothic', fontsize=12)
                    ax.set_ylabel(f"{trend_metric} ({agg_period}平均)", fontfamily='MS Gothic', fontsize=12)
                    ax.legend(prop={'family':'MS Gothic'})
                    plt.tight_layout()
                    st.pyplot(fig)
                else:
                    plt.close(fig) 


            except Exception as e:
                st.error(f"時系列分析中にエラーが発生: {e}")
        else:
            st.warning("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。")


    with tabs[5]:
        st.header("🏆 ランキング分析")

        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()

            numeric_cols = df.select_dtypes(include='number').columns.tolist()
            cat_cols = df.select_dtypes(include='object').columns.tolist()

            if not numeric_cols:
                st.warning("数値列がありません。")
                st.stop()
            if not cat_cols:
                st.warning("カテゴリ列がありません。")
                st.stop()

            col1, col2 = st.columns(2)
            with col1:
                rank_metric = st.selectbox(
                    "ランキング対象の指標", 
                    numeric_cols,
                    key="rank_metric"
                )
                rank_group = st.selectbox(
                    "グループ化",
                    cat_cols,
                    key="rank_group"
                )

            with col2:
                top_n = st.number_input(
                    "表示件数",
                    min_value=1,
                    max_value=50,
                    value=10,
                    key="rank_topn"
                )
                ascending = st.radio(
                    "並び順",
                    ["降順（大きい順）", "昇順（小さい順）"],
                    index=0,
                    key="rank_order"
                )

            if st.button("ランキングを表示", key="rank_execute"):
                try:
                    if rank_group not in df.columns or rank_metric not in df.columns:
                        st.error("選択された列がデータフレームに存在しません。")
                        st.stop()

                    rank_df = df.groupby(rank_group)[rank_metric].agg(['mean', 'count']).round(2)
                    rank_df.columns = ['平均値', 'データ数']
                    rank_df = rank_df.sort_values(
                        '平均値',
                        ascending=(ascending == "昇順（小さい順）")
                    )

                    st.subheader("📊 ランキング結果")
                    rank_display = rank_df.head(top_n).copy()
                    rank_display.index.name = rank_group
                    st.dataframe(rank_display)

                    fig, ax = plt.subplots(figsize=(10, max(5, top_n * 0.3)))
                    rank_display['平均値'].plot(kind='barh', ax=ax)
                    ax.set_title(f"{rank_group}別 {rank_metric}のランキング", fontfamily='MS Gothic', fontsize=16)
                    ax.set_xlabel(f"{rank_metric} 平均値", fontfamily='MS Gothic', fontsize=12)
                    ax.set_ylabel(rank_group, fontfamily='MS Gothic', fontsize=12)
                    
                    for label in ax.get_xticklabels():
                        label.set_fontfamily('MS Gothic')
                    for label in ax.get_yticklabels():
                        label.set_fontfamily('MS Gothic')

                    plt.tight_layout()
                    st.pyplot(fig)

                    csv = rank_display.to_csv(encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        "📥 ランキングデータをCSVで保存",
                        csv,
                        file_name="ranking_data.csv",
                        mime='text/csv',
                        key="rank_download"
                    )

                    st.subheader("📈 特徴的なデータ")

                    if not rank_display.empty:
                        top_item = rank_display.index[0]
                        top_val = rank_display.loc[top_item, '平均値']
                        st.info(f"🏆 トップの{rank_group}: {top_item} ({top_val:.2f})")

                        if len(rank_display) > 1:
                            second_item = rank_display.index[1]
                            second_val = rank_display.loc[second_item, '平均値']
                            if pd.notna(top_val) and pd.notna(second_val):
                                diff = top_val - second_val
                                if second_val != 0:
                                    st.info(f"2位との差: {diff:.2f} ({(diff/second_val*100):.1f}%)")
                                else:
                                    st.info(f"2位との差: {diff:.2f} (2位の値が0のため変化率を計算できません)")
                            else:
                                st.info("トップまたは2位の値が欠損しているため、差を計算できません。")
                    else:
                        st.info("ランキングデータが空のため、特徴的なデータを特定できません。")

                except Exception as e:
                    st.error(f"ランキング分析中にエラーが発生: {e}")
        else:
            st.warning("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。")

    with tabs[6]:
        st.header("📋 自動レポート")

        if 'current_data' in st.session_state and st.session_state.current_data is not None and not st.session_state.current_data.empty:
            df = st.session_state.current_data.copy()

            if '参加率(%)' not in df.columns and '申込数' in df.columns and '参加者数' in df.columns:
                df['参加率(%)'] = (df['参加者数'] / df['申込数']) * 100
            if '満足率(%)' not in df.columns and '満足回答' in df.columns and '参加者数' in df.columns:
                df['満足率(%)'] = (df['満足回答'] / df['参加者数']) * 100
            if 'リアクション率' not in df.columns and '参加者数' in df.columns:
                df['リアクション率'] = df['リアクション数'] / df['参加者数']

            df = DataProcessor.expand_time_slots(df)

            st.subheader("📣 参加者数を増やすためのデータ分析")

            def append_section_to_report(title, df_to_use):
                st.markdown(f"#### {title}")
                st.dataframe(df_to_use, use_container_width=True)


            st.markdown("### 🏆 ランキングまとめ")
            if '担当チーム' in df.columns and '参加者数' in df.columns:
                team_avg = df.groupby("担当チーム")["参加者数"].mean().sort_values(ascending=False).reset_index()
                append_section_to_report("参加者数が多いチーム", team_avg)
            else:
                st.info("「担当チーム」または「参加者数」の列がありません。")

            if '曜日' in df.columns and '参加者数' in df.columns:
                weekday_avg = df.groupby("曜日")["参加者数"].mean().sort_values(ascending=False).reindex(index=['月', '火', '水', '木', '金', '土', '日']).dropna().reset_index()
                append_section_to_report("曜日別の参加者数", weekday_avg)
            else:
                st.info("「曜日」または「参加者数」の列がありません。")

            if '時間帯スロット' in df.columns and '参加者数' in df.columns:
                time_avg = df.groupby("時間帯スロット")["参加者数"].mean().sort_values(ascending=False).reset_index()
                append_section_to_report("時間帯別の参加者数", time_avg)
            else:
                st.info("「時間帯スロット」または「参加者数」の列がありません。")


            if '参加率(%)' in df.columns:
                cols_for_top_rate = [col for col in ["イベント名", "曜日", "時間帯スロット", "参加率(%)"] if col in df.columns]
                top_rate = df.sort_values("参加率(%)", ascending=False).head(5)[cols_for_top_rate].reset_index(drop=True)
                top_rate.index += 1
                append_section_to_report("参加率が高いイベント", top_rate)
            else:
                st.info("「参加率(%)」の列がありません。")

            if '満足率(%)' in df.columns:
                cols_for_top_satisfaction = [col for col in ["イベント名", "曜日", "時間帯スロット", "満足率(%)"] if col in df.columns]
                top_satisfaction = df.sort_values("満足率(%)", ascending=False).head(5)[cols_for_top_satisfaction].reset_index(drop=True)
                top_satisfaction.index += 1
                append_section_to_report("満足度が高いイベント", top_satisfaction)
            else:
                st.info("「満足率(%)」の列がありません。")

            if '曜日' in df.columns and '参加者数' in df.columns:
                low_participation_raw = df.groupby("曜日")["参加者数"].mean().sort_values().reset_index()
                low_participation = low_participation_raw.head(3).copy()
                low_participation.index += 1
                append_section_to_report("参加者数が少ない曜日", low_participation)
            else:
                st.info("「曜日」または「参加者数」の列がありません。")

            st.markdown("### 💡 宣伝・リアクションと参加者数の関係")
            
            corr_summary_text = []
            if '宣伝回数' in df.columns and '参加者数' in df.columns:
                corr1 = df['参加者数'].corr(df['宣伝回数'])
                if pd.notna(corr1):
                    corr_summary_text.append(f"「宣伝回数」と「参加者数」の相関: {corr1:.2f}")
                else:
                    corr_summary_text.append("「宣伝回数」と「参加者数」の相関は計算できませんでした（データ不足または定数）。")
            else:
                corr_summary_text.append("「宣伝回数」の列が見つかりませんでした。")

            if 'リアクション率' in df.columns and '参加者数' in df.columns:
                corr2 = df['参加者数'].corr(df['リアクション率'])
                if pd.notna(corr2):
                    corr_summary_text.append(f"「リアクション率」と「参加者数」の相関: {corr2:.2f}")
                else:
                    corr_summary_text.append("「リアクション率」と「参加者数」の相関は計算できませんでした（データ不足または定数）。")
            else:
                corr_summary_text.append("「リアクション率」の列が見つかりませんでした。")
            
            for line in corr_summary_text:
                st.info(line)


        else:
            st.warning("データがアップロードされていないか、フィルターによってデータがありません。データ管理タブでファイルをアップロードしてください。")

if __name__ == "__main__":
    main()
