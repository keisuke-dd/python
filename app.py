from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
from datetime import timedelta
import os
from supabase import create_client, Client
from dotenv import load_dotenv
import requests

# 環境変数の読み込み
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Supabaseクライアントの作成
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Flaskの設定
app = Flask(__name__)
app.secret_key = "your_secret_key"  # セッション用のシークレットキー

#  セッションの設定
# app.config['SESSION_TYPE'] = 'filesystem'
# app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # 30分で自動ログアウト
# Session(app)

#  セキュリティの強化設定
app.config['SESSION_COOKIE_SECURE'] = False     # HTTPSのみでクッキー送信 localhost環境のため一時出来にflase
app.config['SESSION_COOKIE_HTTPONLY'] = True   # JavaScriptからのアクセスを防止
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # クロスサイトのCSRF防止

#  ホームページ (ログインかサインアップを選ぶ画面)
@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")


#  サインアップページ & 処理
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            # サインアップを実行
            user = supabase.auth.sign_up({"email": email, "password": password})
            print(f"サインアップ成功: {user}")
            # 確認リンクの送信完了メッセージを表示
            return render_template("signup.html", success=f"{email} に確認リンクが送信されました。")
        except Exception as e:
            print(f"サインアップ失敗: {e}")
            return render_template("signup.html", error="サインアップに失敗しました。")
    return render_template("signup.html")


#  ログインページ & ログイン処理
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            user = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            if user.user.email_confirmed_at:
                # セッションにユーザーIDとメールアドレスを保存
                session['user_id'] = user.user.id
                session['user_email'] = user.user.email
                print(f"ログイン成功！ユーザーID: {email}")
                return redirect(url_for('dashboard'))
            else:
                return render_template("login.html", error="メールの確認が完了していません。")
        except Exception as e:
            print(f"ログイン失敗: {e}")
            return render_template("login.html", error="ログインに失敗しました。")
    return render_template("login.html")




#  プロフィール入力処理
@app.route("/profile_input", methods=["GET", "POST"])
def profile_input():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get("name")
        age = request.form.get("age")
        location = request.form.get("location")
        occupation = request.form.get("occupation")
        education = request.form.get("education")
        certifications = request.form.get("certifications")
        bio = request.form.get("bio")

        # supabaseのtableにデータを追加
        try:
            result = supabase.table("profile").upsert({
                "user_id": session['user_id'],  # ユーザーID
                "name": name,
                "age": age,
                "location": location,
                "occupation": occupation,
                "education": education,
                "certifications": certifications,
                "bio": bio,
            }, on_conflict=["user_id"]).execute()

            # レスポンスのステータスコードを確認
            if result.model_dump().get("error"):
                print("保存エラー:", result.error)
                return render_template("profile_input.html", error="保存に失敗しました。")

            # 成功の場合
            return redirect(url_for("profile_output"))

        except Exception as e:
            # 例外処理
            print(f"エラー: {e}")
            return render_template("profile_input.html", error="予期せぬエラーが発生しました。")

    return render_template("profile_input.html")
            


# プロフィールアウトプット表示
@app.route("/profile_output", methods=["GET"])
def profile_output():
    if 'user_id' in session:
        user_id = session['user_id']

        try:
            response = supabase.table("profile").select("*").eq("user_id", user_id).execute()

            # デバッグ出力
            print("取得結果:", response.data)

            if response.data and len(response.data) > 0:
                # 最初のデータを渡す
                return render_template("profile_output.html", profile=response.data[0])
            else:
                return render_template("profile_output.html", error="プロフィールが見つかりません。")

        except Exception as e:
            print(f"プロフィール取得に失敗しました。エラー内容: {e}")
            return render_template("profile_output.html", error="プロフィールの取得に失敗しました。")
    else:
        return redirect(url_for('login'))
    

#  ダッシュボード（ログイン後のページ）
@app.route("/dashboard")
def dashboard():
    if 'user_id' in session:
        return render_template("dashboard.html", user_id=session['user_id'], user_email=session['user_email'])
    else:
        return redirect(url_for('login'))


#  スキルシート作成ページ
@app.route("/skillsheet_input")
def skillsheet_input():
    return render_template("skillsheet_input.html")


# 🔹 プロジェクト入力ページ表示
@app.route("/project_input")
def project_input():
    return render_template("project_input.html")
    
    
#  ログアウト処理
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('home'))


# アプリの実行
if __name__ == "__main__":
    app.run(debug=True)
