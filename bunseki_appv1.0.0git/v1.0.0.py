import streamlit as st
import bcrypt

# 認証用の関数
def verify_password(password, hashed_password):
    return bcrypt.checkpw(password.encode(), hashed_password.encode())

# secrets.toml からユーザー情報を読み込み
def load_users_from_secrets():
    users = []
    try:
        for _, user in st.secrets["users"].items():
            users.append(user)
    except Exception as e:
        st.error("ユーザー情報の読み込みに失敗しました")
        st.stop()
    return users

# ログインフォームを表示
def login_form():
    st.subheader("ログイン")

    # 🔐 secrets からユーザー情報読み取り
    user_data = []
    for key, value in st.secrets["users"].items():
        # value は辞書 or JSON文字列 の場合があるので対応
        if isinstance(value, str):
            import json
            value = json.loads(value)
        user_data.append({
            "username": value["username"],
            "password_hash": value["password_hash"]
        })

    # フォーム定義
    with st.form("login_form"):
        username_input = st.text_input("ユーザー名")
        password_input = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン")

    # フォーム外で処理（← rerun するためにここでやる）
    if submitted:
        for user in user_data:
            if username_input == user["username"]:
                if verify_password(password_input, user["password_hash"]):
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = user["username"]
                    st.success("ログイン成功！")
                    st.rerun()
                else:
                    st.error("パスワードが違います。")
                break
        else:
            st.error("ユーザーが見つかりません。")



# ログイン済みダッシュボード
def show_main_dashboard():
    st.title("🎉 ログイン成功！")
    st.write(f"こんにちは、{st.session_state.get('username')} さん！")

    if st.button("ログアウト"):
        # 安全なログアウト処理（個別にキー削除）
        for key in ["logged_in", "username", "username_input", "password_input"]:
            st.session_state.pop(key, None)

        # rerun せず return（処理中断）
        return

# メイン関数
def main():
    st.set_page_config(page_title="ログイン付きアプリ", layout="centered")

    if st.session_state.get("logged_in"):
        show_main_dashboard()
    else:
        login_form()

if __name__ == "__main__":
    main()
