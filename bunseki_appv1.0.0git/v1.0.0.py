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
    st.sidebar.title("ログイン")
    st.sidebar.text_input("ユーザー名", key="username_input")
    st.sidebar.text_input("パスワード", type="password", key="password_input")

    username_input = st.session_state.get("username_input", "").strip().lower()
    password_input = st.session_state.get("password_input", "")

    if st.sidebar.button("ログイン"):
        for user in load_users_from_secrets():
            if user["username"].lower() == username_input:
                if verify_password(password_input, user["password_hash"]):
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = user["username"]
                    st.experimental_rerun()
                else:
                    st.sidebar.error("パスワードが違います")
                return
        st.sidebar.error("ユーザーが見つかりません")

# ログイン済みダッシュボード
def show_main_dashboard():
    st.title("🎉 ログイン成功！")
    st.write(f"こんにちは、{st.session_state.get('username')} さん！")

    if st.button("ログアウト"):
        # 安全にログアウト処理
        st.session_state.pop("logged_in", None)
        st.session_state.pop("username", None)
        st.session_state.pop("username_input", None)
        st.session_state.pop("password_input", None)
        st.experimental_rerun()


# メイン関数
def main():
    st.set_page_config(page_title="ログイン付きアプリ", layout="centered")

    if st.session_state.get("logged_in"):
        show_main_dashboard()
    else:
        login_form()

if __name__ == "__main__":
    main()
