# 必要なライブラリのインポート
# FlaskとSupabaseのインポート
from flask import Flask, make_response, render_template, request, abort, flash, redirect, url_for, session
from flask_session import Session
from datetime import datetime, timezone, timedelta
import os
from supabase import create_client, Client
from dotenv import load_dotenv
import requests
from pykakasi import kakasi
from gotrue.errors import AuthApiError, AuthWeakPasswordError
from dateutil.parser import isoparse

# ログ出力
import logging
from logging.handlers import RotatingFileHandler
# --- アクション記録デコレータ（例外もログに出す） ---
from functools import wraps

# AI生成に必要なライブラリ
import google.generativeai as genai
import re

# pdf作成に必要なライブラリ
import unicodedata
import io
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import purple, white, black, red, green, blue, yellow, navy
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
import textwrap
from reportlab.pdfbase import pdfmetrics



# 環境変数の読み込み
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# 管理者メールアドレスリストを取得
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "")
ADMIN_EMAIL_LIST = [email.strip() for email in ADMIN_EMAILS.split(",") if email.strip()]

# カスタムカラーの定義
navy = HexColor("#3B0997")  # 紺色を16進数カラーコードで定義

# Supabaseクライアントの作成
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1回だけ日本語フォントを登録（フォント名は自由に決められます）
pdfmetrics.registerFont(TTFont('IPAexGothic', 'static/fonts/ipaexg.ttf'))


# Flaskの設定
app = Flask(__name__)
app.secret_key = "your_secret_key"  # セッション用のシークレットキー


#  セッションの設定
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # 30分操作なしで自動ログアウト


# セッションの永続化を有効にする
@app.before_request
def before_request():
    session.permanent = True  # 永続的なセッション設定
    if 'user_id' in session:
        # セッションが存在している場合のみ更新
        session.modified = True
    else:
        # None チェックを先に
        if request.endpoint is None:
            return

        # ログイン不要なページを除外
        allowed_routes = ['home', 'login', 'signup', 'update_password_request', 'verify_otp', 'update_password_redirect','update_password_form', 'static']
        if request.endpoint in allowed_routes or request.endpoint.startswith('static'):
            return

        # セッション切れメッセージとリダイレクト
        flash("セッションが切れました。再度ログインしてください。", "warning")
        return redirect(url_for('home'))

#  セキュリティの強化設定
app.config['SESSION_COOKIE_SECURE'] = False     # HTTPSのみでクッキー送信 localhost環境のため一時出来にflase
app.config['SESSION_COOKIE_HTTPONLY'] = True   # JavaScriptからのアクセスを防止
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # クロスサイトのCSRF防止


# --- ログ出力先ディレクトリを作成 ---
LOG_DIR = os.path.abspath("logs")
os.makedirs(LOG_DIR, exist_ok=True)

# --- ログフォーマットを定義 ---
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s [%(pathname)s:%(lineno)d - %(funcName)s()] %(message)s'
)

# --- INFOレベルのみ info.txt に出力 ---
info_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'info.txt'),
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding='utf-8'
)
info_handler.setLevel(logging.INFO)
info_handler.addFilter(lambda record: record.levelno == logging.INFO)
info_handler.setFormatter(formatter)

# --- WARNING以上 error.txt に出力 ---
error_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'error.txt'),
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding='utf-8'
)
error_handler.setLevel(logging.WARNING)
error_handler.setFormatter(formatter)

# --- コンソール出力（DEBUG以上） ---
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

# --- ロガーにハンドラを設定 ---
app.logger.handlers.clear()
app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(info_handler)
app.logger.addHandler(error_handler)
app.logger.addHandler(console_handler)

# --- アクセスログのみ出力するデコレーター ---
def log_request_basic(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        app.logger.info(
            f"アクセス: {request.method} {request.path} IP={request.remote_addr} UA={request.user_agent}"
        )
        return func(*args, **kwargs)
    return wrapper


#  ホームページ (ログインかサインアップを選ぶ画面)
@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")


#  サインアップページ & 処理
@app.route("/signup", methods=["GET", "POST"])
@log_request_basic
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            user = supabase.auth.sign_up({"email": email, "password": password})
            app.logger.info(f"サインアップ成功: email={email}")
            return render_template("signup.html", success=f"{email} に確認リンクが送信されました。")
        except Exception as e:
            app.logger.warning(f"サインアップ失敗: email={email} エラー: {e}")
            return render_template("signup.html", error="サインアップに失敗しました。")

    return render_template("signup.html")


#  ログインページ & ログイン処理
@app.route("/login", methods=["GET", "POST"])
@log_request_basic
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
                session["access_token"] = user.session.access_token
                session["refresh_token"] = user.session.refresh_token
                session["user_id"] = user.user.id
                session["user_email"] = user.user.email

                app.logger.info(f"ログイン成功: email={email}")
                # ログイン成功後
                return redirect(url_for('dashboard'))

            else:
                app.logger.warning(f"ログイン失敗（未確認メール）: email={email}")
                return render_template("login.html", error="メールの確認が完了していません。")
        except Exception as e:
            app.logger.warning(f"ログイン失敗: email={email} エラー: {e}")
            return render_template("login.html", error="ログインに失敗しました。")

    return render_template("login.html")


# 最高管理者ログイン
@app.route("/super_admin_login", methods=["GET", "POST"])
def super_admin_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        try:
            result = supabase.auth.sign_in_with_password({"email": email, "password": password})
            user = result.user
            user_id = user.id

            # プロフィールからroleを確認
            profile = supabase.table("profile").select("role").eq("user_id", user_id).single().execute().data
            if profile and profile["role"] == "superadmin":
                session["super_admin"] = True
                session["user_id"] = user_id
                return redirect(url_for("super_admin_dashboard"))
            else:
                return "アクセス拒否：superadminではありません", 403
        except Exception as e:
            return f"ログイン失敗: {str(e)}", 401

    return render_template("super_admin_login.html")


def get_current_user_id():
    return session.get("user_id")

# 最高管理者用ダッシュボードページ
@app.route("/super_admin_dashboard", methods=["GET", "POST"])
def super_admin_dashboard():
    if not session.get("super_admin"):
        return redirect(url_for("super_admin_login"))

    if request.method == "POST":
        # 操作対象のユーザーIDを取得する
        user_id = request.form["user_id"]
        action = request.form["action"]

        # 昇格・降格処理
        if action == "promote":
            supabase.table("profile").update({"role": "admin"}).eq("user_id", user_id).execute()
        elif action == "demote":
            supabase.table("profile").update({"role": "user"}).eq("user_id", user_id).execute()
        elif action == "transfer_superadmin":
            # 1. 対象ユーザーをsuperadminに昇格
            supabase.table("profile").update({"role": "superadmin"}).eq("user_id", user_id).execute()
            # 2. 現在のsuperadmin（自分）をuserに降格
            current_user_id = get_current_user_id()  # トークンなどで取得
            supabase.table("profile").update({"role": "user"}).eq("user_id", current_user_id).execute()
            # 3. セッションからsuperadmin権限を削除し再ログインを促す
            session.pop("super_admin", None)
            session.pop("super_admin_email", None)
            return redirect(url_for("super_admin_login"))

        return redirect(url_for("super_admin_dashboard"))

    # プロフィール一覧取得
    profiles = supabase.table("profile").select("*").order("created_at", desc=True).execute().data
    return render_template("super_admin_dashboard.html", profiles=profiles)


# ユーザーのソフトデリート処理
@app.route("/soft_delete_user", methods=["POST"])
def soft_delete_user():
    if not session.get("super_admin"):
        return "許可されていません（最高管理者のみ実行可能）", 403

    user_id = request.form.get("user_id")
    app.logger.info(f"ソフトデリート処理開始 user_id={user_id}")

    if not user_id:
        app.logger.warning("user_idが指定されていません")
        return "ユーザーIDが必要です", 400

    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    app.logger.info(f"deleted_atに設定する日時: {now}")

    try:
        result = supabase.table("profile").update({"deleted_at": now}).eq("user_id", user_id).execute()
        if not result:
            app.logger.error("ソフトデリート失敗: 更新されたデータが空です")
            return "削除失敗", 500

        app.logger.info(f"ソフトデリート成功: user_id={user_id}")
        return redirect(url_for("super_admin_dashboard"))

    except Exception as e:
        app.logger.exception(f"ソフトデリート中に例外発生: {e}")
        return "内部エラー", 500


# ユーザーのハードデリート処理
@app.route("/hard_delete_user", methods=["POST"])
def hard_delete_user():
    if not session.get("super_admin"):
        return "アクセス拒否：最高管理者のみ実行可能", 403

    threshold = datetime.now(timezone.utc) - timedelta(seconds=5)
    app.logger.info(f"[閾値] {threshold.isoformat()}")

    try:
        response = supabase.table("profile").select("user_id, deleted_at").not_("deleted_at", "is", None).execute()

        if response.error:
            app.logger.error(f"[Supabaseエラー] 削除対象ユーザー取得失敗: {response.error}")
            return "削除対象ユーザー取得失敗", 500

        users = response.data or []
        app.logger.info(f"[取得件数] {len(users)} 件")

        for user in users:
            user_id = user.get("user_id")
            deleted_at_raw = user.get("deleted_at")

            if not deleted_at_raw:
                app.logger.info(f"[スキップ] user_id={user_id} は deleted_at 未設定")
                continue

            try:
                deleted_at = isoparse(deleted_at_raw)
            except Exception as e:
                app.logger.warning(f"[パース失敗] user_id={user_id} deleted_at={deleted_at_raw} → {e}")
                continue

            app.logger.info(f"[比較] user_id={user_id} deleted_at={deleted_at.isoformat()} vs threshold={threshold.isoformat()}")

            if deleted_at < threshold:
                app.logger.info(f"[削除対象] user_id={user_id}")

                # 関連データ削除
                supabase.table("project").delete().eq("user_id", user_id).execute()
                supabase.table("skillsheet").delete().eq("user_id", user_id).execute()
                supabase.table("profile").delete().eq("user_id", user_id).execute()

                # Supabase Auth ユーザー削除
                delete_url = f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}"
                headers = {
                    "apikey": SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
                    "Content-Type": "application/json"
                }
                res = requests.delete(delete_url, headers=headers)
                if res.status_code != 204:
                    app.logger.warning(f"[auth.users削除失敗] user_id={user_id} status={res.status_code} body={res.text}")
                else:
                    app.logger.info(f"[auth.users削除成功] user_id={user_id}")
            else:
                app.logger.info(f"[削除対象外] user_id={user_id}（まだ5秒経っていない）")

        return redirect(url_for("super_admin_dashboard"))

    except Exception as e:
        app.logger.exception(f"[例外発生] ハードデリート中にエラー: {e}")
        return "ハードデリート中にエラーが発生しました", 500


# 管理者ログイン
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin_login.html")

    email = request.form["email"]
    password = request.form["password"]

    try:
        result = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user = result.user
        user_id = user.id

        # profile.role をチェック
        profile = supabase.table("profile").select("role").eq("user_id", user_id).single().execute().data
        if profile and profile["role"] in ["admin", "superadmin"]:
            session["admin"] = True
            session["user_id"] = user_id
            return redirect(url_for("admin_dashboard"))
        else:
            return "アクセス拒否：管理者ではありません", 403
    except Exception as e:
        return render_template("admin_login.html", error=f"ログイン失敗：{str(e)}"), 401


# 管理者用ダッシュボードページ
@app.route("/admin_dashboard", methods=["GET"])
def admin_dashboard():
    # 認証チェック
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    query = request.args.get("q", "").strip().lower()

    # プロフィール取得
    profile_data = supabase.table("profile").select("*").order("created_at", desc=True).execute()
    profile = {}
    for p in profile_data.data:
        user_id = p["user_id"]
        if user_id not in profile:
            profile[user_id] = p

    # スキルシート取得
    skillsheet_data = supabase.table("skillsheet").select("*").order("created_at", desc=True).execute()
    skillsheet = {}
    for s in skillsheet_data.data:
        user_id = s["user_id"]
        if user_id not in skillsheet:
            skillsheet[user_id] = s

    # プロジェクト取得（複数件OK）
    project_data = supabase.table("project").select("*").order("created_at", desc=True).execute()
    projects_by_user = {}
    for proj in project_data.data:
        user_id = proj["user_id"]
        if user_id not in projects_by_user:
            projects_by_user[user_id] = []
        projects_by_user[user_id].append(proj)

    # 統合：ユーザーごとにまとめる
    users = []
    for user_id, profile in profile.items():
        name = profile.get("name", "")

        # 検索クエリに一致するか（名前かメール）
        if query and query not in name.lower():
            continue

        users.append({
            "user_id": user_id,
            "profile": profile,
            "skillsheet": skillsheet.get(user_id),
            "projects": projects_by_user.get(user_id, [])
        })

    return render_template("admin_dashboard.html", users=users, search_query=query)


# emailアドレス更新ページ & 処理
@app.route("/update_email", methods=["GET", "POST"])
@log_request_basic
def update_email():
    if 'access_token' not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        new_email = request.form.get("new_email")

        if not new_email:
            app.logger.warning("メール変更失敗: 入力なし")
            return render_template("update_email.html", error="新しいメールアドレスを入力してください。")

        try:
            supabase.auth.session = lambda: {"access_token": session["access_token"]}
            supabase.auth.update_user({"email": new_email})
            app.logger.info(f"メール変更リクエスト成功: email={new_email}")
            return render_template("update_email.html", success=f"{new_email} に確認メールを送信しました。")
        except Exception as e:
            app.logger.warning(f"メール変更失敗: email={new_email} エラー: {e}")
            return render_template("update_email.html", error="リンクの送信に失敗しました。")

    return render_template("update_email.html")


# 1. OTP送信フォーム
@app.route("/update_password_request", methods=["GET", "POST"])
@log_request_basic
def update_password_request():
    if request.method == "POST":
        email = request.form["email"]
        try:
            supabase.auth.sign_in_with_otp({"email": email})  # OTPを送信
            app.logger.info(f"OTP送信成功: email={email}")
            return redirect(url_for("verify_otp", email=email))
        except AuthApiError as e:
            if "only request this after" in str(e):
                error = "しばらくしてから再試行してください。"
            else:
                error = "エラーが発生しました。もう一度お試しください。"
            app.logger.warning(f"OTP送信失敗（APIエラー）: email={email} エラー: {e}")
            return render_template("update_password_request.html", error=error, email=email)
        except Exception as e:
            error = "予期しないエラーが発生しました。"
            app.logger.warning(f"OTP送信失敗（予期しないエラー）: email={email} エラー: {e}")
            return render_template("update_password_request.html", error=error, email=email)

    return render_template("update_password_request.html")


# 2. OTP検証フォーム
@app.route("/verify_otp", methods=["GET", "POST"])
@log_request_basic
def verify_otp():
    email = request.args.get("email")
    if request.method == "POST":
        otp = request.form["otp"]
        try:
            result = supabase.auth.verify_otp({
                "email": email,
                "token": otp,
                "type": "email"
            })
            session = result.session
            if session and session.access_token and session.refresh_token:
                app.logger.info(f"OTP検証成功: email={email}")
                return redirect(url_for("update_password_form",
                                        access_token=session.access_token,
                                        refresh_token=session.refresh_token))
            else:
                error = "セッション情報が取得できませんでした。"
                app.logger.warning(f"OTP検証失敗: email={email} 理由=セッションなし")
                return render_template("verify_otp.html", email=email, error=error)
        except Exception as e:
            error = f"OTP検証に失敗しました: {e}"
            app.logger.warning(f"OTP検証例外: email={email} エラー: {e}")
            return render_template("verify_otp.html", email=email, error=error)

    return render_template("verify_otp.html", email=email)



# 3. パスワード更新フォーム
@app.route("/update_password_form", methods=["GET", "POST"])
@log_request_basic
def update_password_form():
    access_token = request.args.get("access_token")
    refresh_token = request.args.get("refresh_token")

    if access_token and refresh_token:
        try:
            supabase.auth.set_session(access_token, refresh_token)
            app.logger.info("セッション設定成功（update_password_form）")
        except Exception as e:
            error = "セッションの設定に失敗しました。もう一度ログインし直してください。"
            app.logger.warning(f"セッション設定失敗: access_tokenあり エラー: {e}")
            return render_template("update_password_form.html", error=error)

    if request.method == "POST":
        password = request.form["password"]
        try:
            supabase.auth.update_user({"password": password})
            app.logger.info("パスワード更新成功")
            flash("パスワードを変更しました。ログインしてください。", "success")
            return redirect(url_for("login"))

        except AuthWeakPasswordError:
            error = (
                "パスワードは次のすべてを含める必要があります："
                "小文字・大文字・数字・記号（例: !@#$%^&*)"
            )
            app.logger.warning("パスワード更新失敗: 弱いパスワード")
            return render_template("update_password_form.html", error=error)

        except AuthApiError as e:
            error = "パスワードの変更に失敗しました。もう一度お試しください。"
            app.logger.warning(f"パスワード更新失敗（APIエラー）: {e}")
            return render_template("update_password_form.html", error=error)

    return render_template("update_password_form.html")


# 共通関数: Supabaseからデータを取得する
def get_supabase_data(table_name, user_id):
    try:
        response = supabase.table(table_name).select("*").eq("user_id", user_id).execute()
        data = response.data
        return data[0] if data else {}
    except Exception as e:
        print(f"{table_name} 取得エラー:", e)
        return {}


# ダッシュボード（ログイン後のページ）
@app.route("/dashboard")
@log_request_basic
def dashboard():
    if 'user_id' not in session:
        app.logger.info("未ログインアクセス: /dashboard")
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_email = session.get('user_email')

    # エラーメッセージを取得してセッションから削除
    error = session.pop('error', None)

    # 単一レコード取得用
    tables = {
        "profile": "profile",
        "skillsheet": "skillsheet",
    }

    # データ取得
    data = {}
    for table_name, var_name in tables.items():
        data[var_name] = get_supabase_data(table_name, user_id)

    # 複数レコードのprojectは個別取得
    try:
        response = supabase.table("project").select("*").eq("user_id", user_id).execute()
        projects = response.data if response.data else []
        app.logger.info(f"プロジェクト取得成功: user_id={user_id} 件数={len(projects)}")
    except Exception as e:
        projects = []
        app.logger.warning(f"プロジェクト取得失敗: user_id={user_id} エラー: {e}")

    #  custom_skillsの取得
    try:
        custom_res = supabase.table("custom_skills").select("*").eq("user_id", user_id).execute()
        custom_skills = custom_res.data if custom_res.data else []
        app.logger.info(f"カスタムスキル取得成功: user_id={user_id} 件数={len(custom_skills)}")
    except Exception as e:
        custom_skills = []
        app.logger.warning(f"カスタムスキル取得失敗: user_id={user_id} エラー: {e}")

    return render_template(
        "dashboard.html",
        user_id=user_id,
        user_email=user_email,
        profile=data["profile"],
        skillsheet=data["skillsheet"],
        projects=projects,
        custom_skills=custom_skills,
        error=error
    )


# プロフィール入力処理
@app.route("/profile_input", methods=["GET", "POST"])
@log_request_basic
def profile_input():
    if 'user_id' not in session:
        app.logger.info("未ログインアクセス: /profile_input")
        return redirect(url_for('login'))

    if request.method == 'POST':
        last_name = request.form.get("last_name")
        first_name = request.form.get("first_name")
        last_name_kana = request.form.get("last_name_kana")
        first_name_kana = request.form.get("first_name_kana")
        birth_date = request.form.get("birth_date")
        location = request.form.get("location")
        
        education = request.form.get("education")
        # certificationsは複数選択可能なチェックボックス、リスト化
        # 資格名と取得年月をペアで取得
        certifications = request.form.getlist("certifications[]")
        certification_dates = request.form.getlist("certification_dates[]")


        certifications_list = []
        for name, date in zip(certifications, certification_dates):
            if name.strip():
                if date:
                    # date は "YYYY-MM" 形式なので分割して日本語表記に変換
                    year, month = date.split('-')
                    formatted_date = f"{year}年{month}月"
                    certifications_list.append(f"{name.strip()}（{formatted_date}）")
                else:
                    certifications_list.append(f"{name.strip()}")


        certifications_str = "、".join(certifications_list)

        

        bio = request.form.get("bio")

        # 年齢計算
        if birth_date:
            birth_date = datetime.strptime(birth_date, '%Y-%m-%d')
            today = datetime.now()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        else:
            age = None

        # イニシャル生成
        def generate_initial(last_name_kana, first_name_kana):
            kana_to_romaji = {
                'ア': 'A', 'イ': 'I', 'ウ': 'U', 'エ': 'E', 'オ': 'O',
                'カ': 'K', 'キ': 'K', 'ク': 'K', 'ケ': 'K', 'コ': 'K',
                'サ': 'S', 'シ': 'S', 'ス': 'S', 'セ': 'S', 'ソ': 'S',
                'タ': 'T', 'チ': 'C', 'ツ': 'T', 'テ': 'T', 'ト': 'T',
                'ナ': 'N', 'ニ': 'N', 'ヌ': 'N', 'ネ': 'N', 'ノ': 'N',
                'ハ': 'H', 'ヒ': 'H', 'フ': 'F', 'ヘ': 'H', 'ホ': 'H',
                'マ': 'M', 'ミ': 'M', 'ム': 'M', 'メ': 'M', 'モ': 'M',
                'ヤ': 'Y', 'ユ': 'Y', 'ヨ': 'Y',
                'ラ': 'R', 'リ': 'R', 'ル': 'R', 'レ': 'R', 'ロ': 'R',
                'ワ': 'W', 'ヲ': 'O', 'ン': 'N',
                'ガ': 'G', 'ギ': 'G', 'グ': 'G', 'ゲ': 'G', 'ゴ': 'G',
                'ザ': 'Z', 'ジ': 'J', 'ズ': 'Z', 'ゼ': 'Z', 'ゾ': 'Z',
                'ダ': 'D', 'ヂ': 'J', 'ヅ': 'Z', 'デ': 'D', 'ド': 'D',
                'バ': 'B', 'ビ': 'B', 'ブ': 'B', 'ベ': 'B', 'ボ': 'B',
                'パ': 'P', 'ピ': 'P', 'プ': 'P', 'ペ': 'P', 'ポ': 'P',
                'ャ': 'Y', 'ュ': 'Y', 'ョ': 'Y', 'ッ': '',
            }
            last_initial = kana_to_romaji.get(last_name_kana[0], last_name_kana[0]) if last_name_kana else ''
            first_initial = kana_to_romaji.get(first_name_kana[0], first_name_kana[0]) if first_name_kana else ''
            return f"{last_initial}.{first_initial}"

        initial = generate_initial(last_name_kana, first_name_kana)
        full_name = f"{last_name} {first_name}"

        try:
            result = supabase.table("profile").upsert({
                "user_id": session['user_id'],
                "last_name": last_name,
                "first_name": first_name,
                "last_name_kana": last_name_kana,
                "first_name_kana": first_name_kana,
                "name": full_name,
                "birth_date": birth_date.strftime('%Y-%m-%d') if birth_date else None,
                "age": age,
                "location": location,
                
                "education": education,
                "certifications": certifications_str,
                "bio": bio,
                "initial": initial,
            }, on_conflict=["user_id"]).execute()

            if result.model_dump().get("error"):
                app.logger.warning(f"プロフィール保存失敗: user_id={session['user_id']} エラー={result.error}")
                profile_input = {
                    "last_name": last_name,
                    "first_name": first_name,
                    "last_name_kana": last_name_kana,
                    "first_name_kana": first_name_kana,
                    "birth_date": birth_date.strftime('%Y-%m-%d') if birth_date else None,
                    "location": location,
                    
                    "education": education,
                    "certifications": certifications_str,
                    "bio": bio,
                    "initial": initial,
                }
                return render_template("profile_input.html", error="保存に失敗しました。", profile=profile_input)

            app.logger.info(f"プロフィール保存成功: user_id={session['user_id']}")
            return redirect(url_for("dashboard"))

        except Exception as e:
            app.logger.warning(f"プロフィール保存中に例外発生: user_id={session['user_id']} エラー={e}")
            return render_template("profile_input.html", error="予期せぬエラーが発生しました。", profile={})

    user_id = session['user_id']
    profile_data = get_supabase_data("profile", user_id) or {}
    return render_template("profile_input.html", profile=profile_data)

            


# スキルシート作成ページ & 処理
@app.route("/skillsheet_input", methods=["GET", "POST"])
@log_request_basic
def skillsheet_input():
    if 'user_id' not in session:
        app.logger.info("未ログインアクセス: /skillsheet_input")
        return redirect(url_for('login'))

    user_id = session.get("user_id")

    # スキルカテゴリと選択肢
    categories = {
        "プログラミング言語": ["python", "ruby", "javascript", "shell", "c", "c++", "c#", "java", "html", "go", "css", "swift", "kotlin", "vba"],
        "フレームワーク": ["ruby_on_rails", "django", "flask", "laravel", "symfony", "cakephp", "php", "next_js", "nuxt_js", "vue_js", "spring_boot", "bottle", "react"],
        "開発環境": ["vscode", "eclipse", "pycharm", "jupyter_notebook", "android_studio", "atom", "xcode", "webstorm", "netbeans", "visual_studio"],
        "OS": ["windows", "windows_server", "macos", "linux", "unix", "solaris", "android", "ios", "chromeos", "centos", "ubuntu", "ms_dos", "watchos", "wear_os", "raspberrypi_os", "oracle_solaris", "z/os", "firefox_os", "blackberryos", "rhel", "kali_linux", "parrot_os", "whonix"],
        "クラウド": ["aws", "azure", "gcp", "oci"],
        "セキュリティ製品": ["splunk", "microsoft_sentinel", "microsoft_defender_for_endpoint", "cybereason", "crowdstrike_falcon", "vectra", "exabeam", "sep(symantecendpointprotection)", "tanium", "logstorage", "trellix", "fireeye_nx", "fireeye_hy", "fireeye_cm", "ivanti", "f5_big_ip", "paloalto_prisma", "tenable"],
        "ネットワーク環境": ["cisco_catalyst", "cisco_meraki", "cisco_nexus", "cisco_others", "allied_switch", "allied_others", "nec_ip8800_series", "nec_ix_series", "yamaha_rtx/nvr", "hpe_aruba_switch", "fortinet_fortiswitch", "fortinet_fortogate", "paloalto_pa_series", "panasonic_switch", "media_converter", "wireless_network"],
        "仮想化基盤": ["vmware_vsphere", "vmware_workstaion", "oracle_virtualbox", "vmware_fusion", "microsoft_hyper_v", "kvm(kernel_based_virtual_machine)", "docker", "kubernetes"],
        "AI": ["gemini", "chatgpt", "copilot", "perplexity", "grok", "azure_openai"],
        "サーバソフトウェア": ["apache_http_server", "nginx", "iis", "apache_tomcat", "oracle_weblogic", "adobe_coldfusion", "wildfly", "websphere", "jetty", "glassfish", "squid", "varnish", "sendmail", "postfix"],
        "データベース": ["mysql", "oracle", "postgresql", "sqlite", "mongodb", "casandra", "microsoft_sql_server", "amazon_aurora", "mariadb", "redis", "dynamodb", "elasticsearch", "amazon_rds"],
        "ツール類": ["wireshark", "owasp_zap", "burp_suite", "nessus", "openvas", "tera_term", "powershell", "cmd", "winscp", "tor", "kintone", "jira", "confluence", "servicenow", "sakura_editor", "power_automate", "automation_anywhere", "active_directory", "sap_erp", "salesforce"],
        "言語": ["japanese", "english", "chinese", "korean", "tagalog", "german", "spanish", "italian", "russian", "portugese", "french", "lithuanian", "malay", "romanian"],
        "セキュリティ調査ツール": ["shodan", "censys", "greynoise", "ibm_x_force", "urlsan.io", "abuselpdb", "virustotal", "cyberchef", "any.run", "hybrid_analysis", "wappalyzer", "wireshark"],
    }

    # GET時：現在のデータを取得
    skillsheet_data = get_supabase_data("skillsheet", user_id)

    #  カスタムスキルを取得しておく（POST後にも使うため） カスタムスキルの編集時の表示のため
    try:
        response = supabase.table("custom_skills").select("*").eq("user_id", user_id).execute()
        custom_skills = response.data or []
    except Exception as e:
        custom_skills = []
        app.logger.warning(f"カスタムスキル取得失敗: {e}")

    if request.method == "POST":
        try:
            # フォームからの標準スキル入力を収集
            data = {field: request.form.get(field) for fields in categories.values() for field in fields}
            data["user_id"] = user_id
            data["updated_at"] = datetime.now(timezone.utc).isoformat()

            # skillsheet テーブルにアップサート
            result = supabase.table("skillsheet").upsert(data, on_conflict=["user_id"]).execute()

            if result.model_dump().get("error"):
                app.logger.warning(f"スキルシート保存失敗: user_id={user_id} エラー={result.error}")
                return render_template("skillsheet_input.html", categories=categories, skillsheet=skillsheet_data, custom_skills=custom_skills, error="保存に失敗しました")  

            # ---  カスタムスキル保存処理（insertのみ） ---

            # 1. 既存のカスタムスキル削除（必要な場合のみ）
            del_res = supabase.table("custom_skills").delete().eq("user_id", user_id).execute()
            app.logger.info(f"custom_skills delete result: {del_res.model_dump()}") 

            # 2. フォームから値を取得
            custom_categories = request.form.getlist("custom_category[]")
            custom_names = request.form.getlist("custom_skill_name[]")
            custom_levels = request.form.getlist("custom_skill_level[]")


             # 2-1. ログ出力で中身を確認
            app.logger.info(f"custom_category: {custom_categories}")  # 【追加】
            app.logger.info(f"custom_skill_name: {custom_names}")    # 【追加】
            app.logger.info(f"custom_skill_level: {custom_levels}")  # 【追加】

            # 3. 複数件のカスタムスキルを一括insert
            custom_records = []
            for cat, name, level in zip(custom_categories, custom_names, custom_levels):
                if name.strip() == "" or level.strip() == "":
                    continue  # 空欄スキップ

                custom_records.append({
                    "user_id": user_id,
                    "custom_category": cat,
                    "custom_skill_name": name.strip(),
                    "custom_skill_level": level
                })


            if custom_records:
                supabase.table("custom_skills").insert(custom_records).execute()

                #  保存完了後に再取得して再表示用データ更新
                skillsheet_data = get_supabase_data("skillsheet", user_id)
                response = supabase.table("custom_skills").select("*").eq("user_id", user_id).execute()
                custom_skills = response.data or []



            app.logger.info(f"スキルシート保存成功: user_id={user_id}")
            return redirect(url_for("dashboard")) 

        except Exception as e:
            app.logger.warning(f"スキルシート保存時に例外発生: user_id={user_id} エラー={e}")
            return render_template("skillsheet_input.html", categories=categories, skillsheet=skillsheet_data, custom_skills=custom_skills, error="エラーが発生しました")  

    # GET時
    return render_template("skillsheet_input.html", categories=categories, skillsheet=skillsheet_data, custom_skills=custom_skills) 


# プロジェクト入力ページ & 処理
@app.route("/project_input", methods=["GET", "POST"])
@log_request_basic
def project_input():
    if 'user_id' not in session:
        app.logger.info("未ログインアクセス: /project_input")
        return redirect(url_for('login'))

    if request.method == "POST":
        action = request.form.get("action")
        name = request.form.get("name")
        description = request.form.get("description")
        start_at = request.form.get("start_at") or None
        end_at = request.form.get("end_at") or None
        technologies = request.form.get("technologies", "")


        if action == "generate":
            prompt = f"""
            # あなたはSES事業の営業担当者です。  
            自社のエンジニアをお客様先に推薦するため、  
            以下のエンジニアの過去参画プロジェクト説明をもとに、  
            お客様向けに簡潔かつ具体的な箇条書き形式の職務経歴文を作成してください。  

            # 目的  
            - クライアントにエンジニアの実務能力や経験を的確に伝える  
            - 採用担当者が「ぜひ採用したい」と感じる表現にする  

            # 出力条件  
            - 箇条書き形式で7～10項目程度
            - 業務内容、使用技術、貢献成果が分かる具体的な表現
            - 成果や貢献を必ず含める  
            - 専門用語は適度に使いながら、分かりやすさも重視する  
            - 敬体（です・ます調）で、正式かつ読みやすい文体にする  
            - 全体の文字数は400～500文字程度

            # 入力情報  
            プロジェクト名: {name}  
            プロジェクト説明: {description}  

            # 以上を踏まえて、職務経歴の箇条書き文を作成してください。  

            """
            try:
                model = genai.GenerativeModel(model_name="gemini-2.0-flash-lite")
                response = model.generate_content(prompt)
                text = response.text

                cleaned = re.sub(r'^##+\s*', '', text, flags=re.MULTILINE)
                cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
                cleaned = re.sub(r'^[\*\-\+]\s+', '', cleaned, flags=re.MULTILINE)
                cleaned = re.sub(r'^\*\s+', '', cleaned, flags=re.MULTILINE)
                cleaned = re.sub(r'\*(\S.*?)\*', r'\1', cleaned)
                cleaned = cleaned.replace('*', '')

                session['generated_summary'] = cleaned
                app.logger.info(f"AI生成成功: user_id={session['user_id']} プロジェクト名={name}")
            except Exception as e:
                session['generated_summary'] = "AI生成に失敗しました。"
                app.logger.warning(f"AI生成失敗: user_id={session['user_id']} エラー={e}")

            project = {
                "name": name,
                "description": description,
                "start_at": start_at,
                "end_at": end_at,
                "technologies": technologies,
            }
            return render_template("project_input.html", project=project, generated_summary=session['generated_summary'])

        elif action == "save":
            try:
                if not name or not description:
                    app.logger.warning(f"保存失敗（必須項目不足）: user_id={session['user_id']}")
                    return render_template("project_input.html", error="プロジェクト名と説明は必須です。")

                result = supabase.table("project").insert({
                    "user_id": session['user_id'],
                    "name": name,
                    "description": description,
                    "start_at": start_at,
                    "end_at": end_at,
                    "technologies": technologies,
                }).execute()

                if not result.data:
                    app.logger.warning(f"保存失敗（dataなし）: user_id={session['user_id']} 結果={result.model_dump()}")
                    return render_template("project_input.html", error="プロジェクトの保存に失敗しました。")

                app.logger.info(f"プロジェクト保存成功: user_id={session['user_id']} プロジェクト名={name}")
                return redirect(url_for("dashboard"))

            except Exception as e:
                app.logger.warning(f"プロジェクト保存時に例外発生: user_id={session['user_id']} エラー={e}")
                return render_template("project_input.html", error="予期せぬエラーが発生しました。")

    generated_summary = session.pop('generated_summary', "")
    return render_template("project_input.html", generated_summary=generated_summary)


# プロジェクト削除ページ
@app.route("/project_delete/<project_id>", methods=["POST"])
def project_delete(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        result = supabase.table("project").delete().eq("id", project_id).eq("user_id", session['user_id']).execute()

        if result.model_dump().get("error"):
            print("削除エラー:", result.error)
            return redirect(url_for("dashboard", error="削除に失敗しました。"))

        return redirect(url_for("dashboard"))

    except Exception as e:
        print("削除例外:", e)
        return redirect(url_for("dashboard"))



# プロジェクト編集ページ
@app.route("/project_edit/<project_id>", methods=["GET", "POST"])
@log_request_basic
def project_edit(project_id):
    if 'user_id' not in session:
        app.logger.info("未ログインアクセス: /project_edit")
        return redirect(url_for('login'))

    if request.method == "POST":
        action = request.form.get("action")
        name = request.form.get("name")
        description = request.form.get("description")
        start_at = request.form.get("start_at") or None
        end_at = request.form.get("end_at") or None
        technologies = request.form.get("technologies", "")


        if action == "generate":
            prompt = f"""
            # あなたはSES事業の営業担当者です。  
            自社のエンジニアをお客様先に推薦するため、  
            以下のエンジニアの過去参画プロジェクト説明をもとに、  
            お客様向けに簡潔かつ具体的な箇条書き形式の職務経歴文を作成してください。  

            # 目的  
            - クライアントにエンジニアの実務能力や経験を的確に伝える  
            - 採用担当者が「ぜひ採用したい」と感じる表現にする  

            # 出力条件  
            - 箇条書き形式で8点程度に整理   
            - 具体的な業務内容や使用技術を明記する  
            - 成果や貢献を必ず含める  
            - 専門用語は適度に使いながら、分かりやすさも重視する  
            - 敬体（です・ます調）で、正式かつ読みやすい文体にする  
            - 全体で300～400字程度  

            # 入力情報  
            プロジェクト名: {name}  
            プロジェクト説明: {description}  

            # 以上を踏まえて、職務経歴の箇条書き文を作成してください。  
            
            """
            try:
                model = genai.GenerativeModel(model_name="gemini-2.0-flash-lite")
                response = model.generate_content(prompt)
                text = response.text

                cleaned = re.sub(r'^##+\s*', '', text, flags=re.MULTILINE)
                cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned, flags=re.DOTALL)
                cleaned = re.sub(r'^[\*\-\+]\s+', '', cleaned, flags=re.MULTILINE)
                cleaned = re.sub(r'^\*\s+', '', cleaned, flags=re.MULTILINE)
                cleaned = re.sub(r'\*(\S.*?)\*', r'\1', cleaned)
                cleaned = cleaned.replace('*', '')

                session['generated_summary'] = cleaned
                app.logger.info(f"AI生成成功（編集）: user_id={session['user_id']} project_id={project_id}")
            except Exception as e:
                session['generated_summary'] = "AI生成に失敗しました。"
                app.logger.warning(f"AI生成失敗（編集）: user_id={session['user_id']} project_id={project_id} エラー={e}")

            project = {
                "id": project_id,
                "name": name,
                "description": description,
                "start_at": start_at,
                "end_at": end_at,
                "technologies": technologies,
            }

            return render_template("project_edit.html", project=project, generated_summary=session['generated_summary'])

        elif action == "save":
            try:
                result = supabase.table("project").update({
                    "name": name,
                    "description": description,
                    "start_at": start_at,
                    "end_at": end_at,
                    "technologies": technologies,
                }).eq("id", project_id).eq("user_id", session['user_id']).execute()

                app.logger.info(f"プロジェクト更新成功: user_id={session['user_id']} project_id={project_id}")
                return redirect(url_for("dashboard"))

            except Exception as e:
                app.logger.warning(f"プロジェクト更新失敗: user_id={session['user_id']} project_id={project_id} エラー={e}")
                return render_template("project_edit.html", error="更新に失敗しました。")

    else:
        try:
            response = supabase.table("project").select("*").eq("id", project_id).eq("user_id", session['user_id']).maybe_single().execute()
            project = response.data

            if not project:
                app.logger.warning(f"プロジェクトが見つかりません: user_id={session['user_id']} project_id={project_id}")
                return redirect(url_for("dashboard"))

            return render_template("project_edit.html", project=project)

        except Exception as e:
            app.logger.warning(f"プロジェクト取得失敗: user_id={session['user_id']} project_id={project_id} エラー={e}")
            return redirect(url_for("dashboard"))



# PDF作成ページ
# PDF関数定義
def sanitize_text(text):
    # 不可視文字や制御文字を除去
    text = unicodedata.normalize('NFKC', text)  # 全角→半角などの正規化
    text = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)  # ゼロ幅スペースなど削除
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # 改行統一
    return text

# --- 折り返し描画用ヘルパー関数 ---
def draw_wrapped_text(canvas, text, x, y, max_width,
                    font_name="IPAexGothic", font_size=10, leading=14):
    canvas.setFont(font_name, font_size)
    lines = []
    for paragraph in text.split('\n'):
        current_line = ""
        for char in paragraph:
            test_line = current_line + char
            test_width = pdfmetrics.stringWidth(test_line, font_name, font_size)
            if test_width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
    for i, line in enumerate(lines):
        canvas.drawString(x, y - i * leading, line)
    return len(lines)


 # --- 日付を安全にパースする関数 ---
def format_date(date_str):
    if not date_str:
        return ""
    try:
        # 例: ISO形式 '2002-05-07T00:00:00' をdatetimeに変換
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        # 好みの表示形式に変換（例: 2002年5月7日）
        # Windows環境など%-mが使えない場合は%#mを試してください
        return dt.strftime("%Y年%m月%d日").replace(" 0", " ")
    except Exception as e:
        print(f"format_date parse error: {e} with input: {date_str}")
        return date_str
            
            
@app.route("/create_pdf", methods=["GET"])
@log_request_basic
def create_pdf():
    user_id = session.get('user_id')
    if not user_id:
        app.logger.info("未ログインアクセス: /create_pdf")
        return redirect(url_for("login"))

    try:
        app.logger.info(f"PDF作成開始: user_id={user_id}")

        # データ取得
        profile_res = supabase.from_("profile").select("*").eq("user_id", user_id).execute()
        skillsheet_res = supabase.from_("skillsheet").select("*").eq("user_id", user_id).execute()
        custom_res = supabase.from_("custom_skills").select("*").eq("user_id", user_id).execute()
        projects_res = supabase.from_("project").select("*").eq("user_id", user_id).execute()

        for name, res in [("profile", profile_res), ("skillsheet", skillsheet_res),("custom_skills", custom_res), ("projects", projects_res)]:
            if res is None or (hasattr(res, "error") and res.error):
                app.logger.error(f"{name}取得失敗: user_id={user_id} エラー={getattr(res, 'error', 'None')}")
                session['error'] = f"{name}のデータ取得に失敗しました。"
                return redirect(url_for('dashboard'))

        # ───  data 部分が None の場合は「レコードなし」として扱う ───
        profile = profile_res.data[0] if profile_res.data else {}
        skillsheet = skillsheet_res.data[0] if skillsheet_res.data else {}
        custom_skills = custom_res.data or []
        projects = projects_res.data or []

        # プロフィールデータが空の場合は、ダッシュボードにリダイレクト
        if not profile:
            app.logger.warning(f"プロフィール未登録: user_id={user_id}")
            session['error'] = "プロフィールデータが登録されていません。"
            return redirect(url_for('dashboard'))

        
         # PDF初期化Add commentMore actions
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 50

        # ========== 紺色の背景ブロック ==========
        block_width = 180
        block_height = 250
        p.setFillColor(navy)
        p.rect(0, height - block_height, block_width, block_height, fill=True, stroke=0)

        # ========== 画像挿入 ==========
        try:
            image_path = "./static/images/tom_3.png"
            p.drawImage(image_path, 30, height - 120, width=120, height=60, mask='auto')
        except Exception as e:
            print("画像読み込みエラー:", e)

        # ========== タイトル（ブロック内に） ==========
        p.setFillColorRGB(1, 1, 1)  # 白文字
        p.setFont("IPAexGothic", 12)
        p.drawString(35, height - 160, "TECHNICAL SHEET")

        # ========== テキストを黒に戻す ==========
        p.setFillColor(black)

        # プロフィール表示位置（ブロックの右端より右側）
        profile_x = block_width + 30
        profile_y = height - 50

        # ========== プロフィール情報の描画 ==========
        p.setFont("IPAexGothic", 16)
        p.drawString(profile_x, profile_y, f"氏名：{profile.get('initial', '')}")

        p.setFont("IPAexGothic", 12)
        p.drawString(profile_x, profile_y - 25, f"年齢: {profile.get('age', '')}")

        next_y = profile_y - 25  # 年齢の下

        if profile.get('location'):
            p.drawString(profile_x, next_y - 20, f"最寄り駅: {profile.get('location', '')}")
            next_y -= 20

        if profile.get('education'):
            p.drawString(profile_x, next_y - 20, f"学歴: {profile.get('education', '')}")
            next_y -= 20

        # y_cursorは最後に描画した位置からスタート
        y_cursor = next_y - 30

        # ========== 資格（カンマ区切りで縦並び表示） ==========
        if profile.get('certifications'):

             # 先に「資格:」ラベルを描画（ラベルのフォントサイズは少し大きめ）
            label_font_size = 12
            p.setFont("IPAexGothic", label_font_size)
            p.drawString(profile_x, y_cursor, "資格:")
            y_cursor -= label_font_size + 6  # ラベルの高さ＋少し余白を下げる
            
            certs = profile.get('certifications')

            # 文字列ならカンマで分割
            if isinstance(certs, str):
                # 半角カンマ・全角カンマ両方対応
                certs_list = [c.strip() for c in re.split(r'[、,]', certs) if c.strip()]
            # リスト型ならそのまま
            elif isinstance(certs, list):
                certs_list = [str(c).strip() for c in certs if str(c).strip()]
            else:
                certs_list = [str(certs)]

            # テキスト整形
            certs_list = [sanitize_text(c) for c in certs_list]

            # フォント設定
            font_size = 10
            line_height = 14
            p.setFont("IPAexGothic", font_size)

            # デバッグ用：中身確認
            print("資格リスト：", certs_list)

            # 1行ずつ描画
            for cert in certs_list:
                p.drawString(profile_x, y_cursor, cert)
                y_cursor -= line_height

            y_cursor -= 10  # 余白


            # ========== 自己紹介（折り返し） ==========
            
            if profile.get('bio'):
                bio_label = "自己紹介:"
                bio_body = profile.get('bio', '')
                
                # ラベルを12ptで描画（目立たせる）
                p.setFont("IPAexGothic", 12)
                p.drawString(profile_x, y_cursor, bio_label)
                
                label_width = p.stringWidth(bio_label, "IPAexGothic", 12)
                bio_x_start = profile_x + label_width + 5  # ラベルのすぐ右に本文開始位置
                
                bio_text = sanitize_text(bio_body)
                bio_max_width = width - bio_x_start - 50  # 右余白考慮

                # 本文を10ptで折り返し描画
                p.setFont("IPAexGothic", 10)
                lines_drawn = draw_wrapped_text(p, bio_text, bio_x_start, y_cursor, bio_max_width,
                                                font_name="IPAexGothic", font_size=10, leading=14)
                y_cursor -= lines_drawn * 14 + 10



        # ========== スキルシートの描画 ==========

        # --- ここで新しいページ ---
        p.showPage()
        y = height - 50  # 新しいページの上から再スタート

        # ========== スキル一覧 ==========
        p.setFillColor(navy)
        p.rect(50, y - 5, width - 100, 1, fill=True, stroke=0)  # 下線のみ
        p.setFillColor(black)
        
        p.setFont("IPAexGothic", 14)
        p.drawString(60, y, "■ スキル一覧")
        y -= 40

         # スキルレベルの判断基準を追加
        p.setFont("IPAexGothic", 12)
        p.setFillColor(navy)
        p.drawString(60, y, "【スキルレベルの判断基準】")
        p.setFillColor(black)
        y -= 25

        # スキルレベルの判断基準をリストで表示
        criteria = [
            "S: 専門家レベル - その分野のエキスパートとして、複雑な問題解決や指導が可能",
            "A: 上級レベル - 実務経験が豊富で、独力でプロジェクトを遂行可能",
            "B: 中級レベル - 基本的な実務経験があり、チーム内で活躍可能",
            "C: 初級レベル - 基礎知識があり、サポート業務が可能",
            "D: 学習中 - 現在学習中のスキル"
        ]

        for criterion in criteria:
            p.setFont("IPAexGothic", 10)
            p.drawString(70, y, criterion)
            y -= 20

        y -= 20  # スキル一覧との間隔を確保

        # スキルをカテゴリごとに分類
        categories = {
            "プログラミング言語": ["python", "ruby", "javascript", "shell", "c", "c++", "c#", "java", "html", "go", "css", "swift", "kotlin", "vba"],
            "フレームワーク": ["ruby_on_rails", "django", "flask", "laravel", "symfony", "cakephp", "php", "next_js", "nuxt_js", "vue_js", "spring_boot", "bottle", "react"],
            "開発環境": ["vscode", "eclipse", "pycharm", "jupyter_notebook", "android_studio", "atom", "xcode", "webstorm", "netbeans", "visual_studio"],
            "OS": ["windows", "windows_server", "macos", "linux", "unix", "solaris", "android", "ios", "chromeos", "centos", "ubuntu", "ms_dos", "watchos", "wear_os", "raspberrypi_os", "oracle_solaris", "z/os", "firefox_os", "blackberryos", "rhel", "kali_linux", "parrot_os", "whonix"],
            "クラウド": ["aws", "azure", "gcp", "oci"],
            "セキュリティ製品": ["splunk", "microsoft_sentinel", "microsoft_defender_for_endpoint", "cybereason", "crowdstrike_falcon", "vectra", "exabeam", "sep(symantecendpointprotection)", "tanium", "logstorage", "trellix", "fireeye_nx", "fireeye_hy", "fireeye_cm", "ivanti", "f5_big_ip", "paloalto_prisma", "tenable"],
            "ネットワーク環境": ["cisco_catalyst", "cisco_meraki", "cisco_nexus", "cisco_others", "allied_switch", "allied_others", "nec_ip8800_series", "nec_ix_series", "yamaha_rtx/nvr", "hpe_aruba_switch", "fortinet_fortiswitch", "fortinet_fortogate", "paloalto_pa_series", "panasonic_switch", "media_converter", "wireless_network", "other_network_devices"],
            "仮想化基盤": ["vmware_vsphere", "vmware_workstaion", "oracle_virtualbox", "vmware_fusion", "microsoft_hyper_v", "kvm(kernel_based_virtual_machine)", "docker", "kubernetes"],
            "AI": ["gemini", "chatgpt", "copilot", "perplexity", "grok", "azure_openai"],
            "サーバソフトウェア": ["apache_http_server", "nginx", "iis", "apache_tomcat", "oracle_weblogic", "adobe_coldfusion", "wildfly", "websphere", "jetty", "glassfish", "squid", "varnish", "sendmail", "postfix"],
            "データベース": ["mysql", "oracle", "postgresql", "sqlite", "mongodb", "casandra", "microsoft_sql_server", "amazon_aurora", "mariadb", "redis", "dynamodb", "elasticsearch", "amazon_rds"],
            "ツール類": ["wireshark", "owasp_zap", "burp_suite", "nessus", "openvas", "tera_term", "powershell", "cmd", "winscp", "tor", "kintone", "jira", "confluence", "servicenow", "sakura_editor", "power_automate", "automation_anywhere", "active_directory", "sap_erp", "salesforce"],
            "言語": ["english", "chinese", "korean", "tagalog", "german", "spanish", "italian", "russian", "portugese", "french", "lithuanian", "malay", "romanian"],
            "セキュリティ調査ツール": ["shodan", "censys", "greynoise", "ibm_x_force", "urlsan.io", "abuselpdb", "virustotal", "cyberchef", "any.run", "hybrid_analysis", "wappalyzer", "wireshark"]
        }

        # スキルを3列に分けて表示
        col1_x = 50  # 左端の余白を60から50に調整
        col2_x = width / 3 + 10  # 列間の余白を調整
        col3_x = (width / 3) * 2 + 10  # 列間の余白を調整
        col1_y = y
        col2_y = y
        col3_y = y
        current_col = 1

        def draw_level_bar(x, y, level):
            # バーの基本設定
            bar_height = 1.2  # バーの高さを0.8から1.2に増加
            bar_width = 70  # バーの幅を50から70に増加
            bar_y = y - 1
            
            # レベルに応じたバーの長さを計算
            if level == 'S':
                fill_width = bar_width
            elif level == 'A':
                fill_width = bar_width * 0.8
            elif level == 'B':
                fill_width = bar_width * 0.6
            elif level == 'C':
                fill_width = bar_width * 0.4
            elif level == 'D':
                fill_width = 0
            else:
                fill_width = 0

            # レベル表示（バーの下）
            p.setFont("IPAexGothic", 8)
            # 各レベルの位置を計算
            level_positions = {
                'S': x + bar_width,
                'A': x + bar_width * 0.8,
                'B': x + bar_width * 0.6,
                'C': x + bar_width * 0.4,
                'D': x + bar_width * 0.2
            }
            
            # 背景のバー（薄いグレー）
            p.setFillColorRGB(0.9, 0.9, 0.9)
            p.rect(x, bar_y, bar_width, bar_height, fill=True, stroke=0)
            
            # 塗りつぶしバー（紺色）
            p.setFillColor(navy)
            p.rect(x, bar_y, fill_width, bar_height, fill=True, stroke=0)
            
            # 現在のレベル位置に●を表示
            current_pos = level_positions.get(level, 0)
            p.setFillColor(navy)
            p.circle(current_pos, bar_y + bar_height/2, 2.5, fill=True)  # 円のサイズを2から2.5に増加
            
            # レベル表示（バーの下）
            for lvl, pos in level_positions.items():
                p.setFillColor(black)
                p.drawString(pos - 3, y - 10, lvl)
            
            # テキストを黒に戻す
            p.setFillColor(black)
            p.setFont("IPAexGothic", 4)

        # カテゴリごとにスキルを表示
        for category, skills in categories.items():
            # カテゴリ内のスキルをフィルタリング（Dレベルのスキルを除外）
            category_skills = {skill: skillsheet.get(skill) for skill in skills if skillsheet.get(skill) and skillsheet.get(skill) != 'D'}
            
            if category_skills:  # カテゴリにスキルがある場合のみ表示
                # カテゴリタイトルを表示
                if current_col == 1:
                    p.setFont("IPAexGothic", 12)
                    p.setFillColor(navy)
                    p.drawString(col1_x, col1_y, f"【{category}】")
                    p.setFillColor(black)
                    col1_y -= 30
                elif current_col == 2:
                    p.setFont("IPAexGothic", 12)
                    p.setFillColor(navy)
                    p.drawString(col2_x, col2_y, f"【{category}】")
                    p.setFillColor(black)
                    col2_y -= 30
                else:
                    p.setFont("IPAexGothic", 12)
                    p.setFillColor(navy)
                    p.drawString(col3_x, col3_y, f"【{category}】")
                    p.setFillColor(black)
                    col3_y -= 30

                # カテゴリ内のスキルを表示
                for skill, level in category_skills.items():
                    if current_col == 1:
                        # スキル名を表示（線の上に小さく）
                        p.setFont("IPAexGothic", 7)
                        p.drawString(col1_x, col1_y + 8, f"・{skill.replace('_', ' ').title()}")
                        # レベルバーを描画
                        draw_level_bar(col1_x + 60, col1_y, level)  # 左に移動（90から60に）
                        col1_y -= 25
                        if col1_y < 100:
                            current_col = 2
                            col1_y = y
                    elif current_col == 2:
                        # スキル名を表示（線の上に小さく）
                        p.setFont("IPAexGothic", 7)
                        p.drawString(col2_x, col2_y + 8, f"・{skill.replace('_', ' ').title()}")
                        # レベルバーを描画
                        draw_level_bar(col2_x + 60, col2_y, level)  # 左に移動（90から60に）
                        col2_y -= 25
                        if col2_y < 100:
                            current_col = 3
                            col2_y = y
                    else:
                        # スキル名を表示（線の上に小さく）
                        p.setFont("IPAexGothic", 7)
                        p.drawString(col3_x, col3_y + 8, f"・{skill.replace('_', ' ').title()}")
                        # レベルバーを描画
                        draw_level_bar(col3_x + 60, col3_y, level)  # 左に移動（90から60に）
                        col3_y -= 25
                        if col3_y < 100:
                            p.showPage()
                            y = height - 50
                            col1_y = y
                            col2_y = y
                            col3_y = y
                            current_col = 1
                            p.setFont("IPAexGothic", 4)

                # カテゴリ間の余白
                if current_col == 1:
                    col1_y -= 10  # カテゴリ間の余白を増加
                elif current_col == 2:
                    col2_y -= 10  # カテゴリ間の余白を増加
                else:
                    col3_y -= 10  # カテゴリ間の余白を増加




        
       # ========== カスタムスキル一覧 ==========

        # 新しいページに移動
        p.showPage()
        y = height - 50  # ページ上部から開始


        # ヘッダーの装飾
        p.setFillColor(navy)
        p.rect(50, y - 5, width - 100, 1, fill=True, stroke=0)
        p.setFillColor(black)   

        # タイトル
        p.setFont("IPAexGothic", 14)
        p.setFillColor(black)
        p.drawString(50, y, "■ カスタムスキル一覧")
        y -= 30

        # カスタムスキル描画ループ
        p.setFont("IPAexGothic", 10)
        p.setFillColor(black)

        for skill in custom_skills:
            text = f"【{skill.get('custom_category', '')}】{skill.get('custom_skill_name', '')} - レベル: {skill.get('custom_skill_level', '')}"
            p.drawString(60, y, text)
            y -= 20
            if y < 100:
                p.showPage()
                y = height - 50



        # --- プロジェクト履歴ページ ---

        

        # --- プロジェクト履歴の描画開始 ---
        sorted_projects = sorted(projects, key=lambda p: p.get("start_at") or "", reverse=True)

        # 新しいページにプロジェクト履歴を描画
        p.showPage()
        y = height - 50

        # ヘッダーの装飾
        p.setFillColor(navy)
        p.rect(50, y - 5, width - 100, 1, fill=True, stroke=0)
        p.setFillColor(black)

        # タイトル
        p.setFont("IPAexGothic", 16)
        p.drawString(60, y, "■ プロジェクト履歴")
        y -= 50

        for i, project in enumerate(sorted_projects):
            # 改ページ判定
            if y < 150:
                p.showPage()
                y = height - 50
                p.setFillColor(navy)
                p.rect(50, y - 5, width - 100, 1, fill=True, stroke=0)
                p.setFillColor(black)
                p.setFont("IPAexGothic", 16)
                p.drawString(60, y, "■ プロジェクト履歴")
                y -= 50

            print(f"{i+1}件目: {project.get('name')}, y={y}")

            timeline_x = 60
            detail_x = timeline_x + 20
            detail_y = y - 15
            max_width = width - detail_x - 50

            # プロジェクト名
            p.setFont("IPAexGothic", 12)
            p.setFillColor(navy)
            p.drawString(detail_x, y + 5, f"・{project.get('name', '')}")
            p.setFillColor(black)

            # 横線装飾
            p.setFillColor(navy)
            p.rect(detail_x - 5, detail_y - 2, width - detail_x - 50, 1, fill=True, stroke=0)
            p.setFillColor(black)

            # 期間
            if project.get("start_at") or project.get("end_at"):
                p.setFont("IPAexGothic", 10)
                start_disp = format_date(project.get("start_at", ""))
                end_disp = format_date(project.get("end_at", ""))
                p.drawString(
                    detail_x,
                    detail_y,
                    f"期間: {start_disp} ～ {end_disp}"
                )
                detail_y -= 20


            # 説明（折り返し対応）
            if project.get("description"):
                p.setFont("IPAexGothic", 10)
                description_text = sanitize_text(f"説明: {project.get('description')}")
                num_lines = draw_wrapped_text(
                    p,
                    description_text,
                    detail_x,
                    detail_y,
                    max_width,
                    font_name="IPAexGothic",
                    font_size=10,
                    leading=14
                )

                
                detail_y -= (num_lines * 14)

            # 技術（折り返し＋重複除去）
            if project.get("technologies"):
                p.setFont("IPAexGothic", 10)
                tech_list = project["technologies"]
                if isinstance(tech_list, list):
                    techs = list(dict.fromkeys(tech_list))
                    tech_text = f"技術: {', '.join(techs)}"
                else:
                    tech_text = f"技術: {str(tech_list)}"

                max_width = width - detail_x - 50
                num_lines = draw_wrapped_text(
                    p,
                    tech_text,
                    detail_x,
                    detail_y,
                    max_width,
                    font_name="IPAexGothic",
                    font_size=10,
                    leading=14
                )
                detail_y -= (num_lines * 14)

            # 次のプロジェクト描画位置を更新
            y = detail_y - 40



        # ========== フッター ==========

        # フッター
        p.setFillColor(navy)
        p.rect(0, 30, width, 1, fill=True, stroke=0)
        p.setFillColor(black)
        p.setFont("IPAexGothic", 9)
        p.drawString(50, 20, f"作成日: {datetime.now().strftime('%Y/%m/%d')}")

        p.showPage()
        p.save()
        buffer.seek(0)
        
        # PDFを一時ファイルとして保存

        temp_pdf_path = f"static/temp/{user_id}_skillsheet.pdf"
        os.makedirs("static/temp", exist_ok=True)
        with open(temp_pdf_path, "wb") as f:
            f.write(buffer.getvalue())

        app.logger.info(f"PDF作成完了: user_id={user_id} 保存先={temp_pdf_path}")
        return redirect(url_for('view_pdf'))

    except Exception as e:
        app.logger.exception(f"PDF作成中にエラー発生: user_id={user_id} エラー={e}")
        session['error'] = f"PDFの作成に失敗しました: {str(e)}"
        return redirect(url_for('dashboard'))


# PDF作成処理
    except Exception as e:
        print(f"PDF作成エラー: {e}")
        session['error'] = f"PDFの作成に失敗しました: {str(e)}"
        return redirect(url_for('dashboard'))



@app.route("/view_pdf")
@log_request_basic
def view_pdf():
    if 'user_id' not in session:
        app.logger.info("未ログインアクセス: /view_pdf")
        return redirect(url_for("login"))
    
    user_id = session['user_id']
    pdf_path = f"static/temp/{user_id}_skillsheet.pdf"

    if not os.path.exists(pdf_path):
        app.logger.warning(f"PDFファイル未検出: user_id={user_id} path={pdf_path} → /create_pdfへリダイレクト")
        return redirect(url_for('create_pdf'))

    try:
        # Supabaseからデータ取得
        profile_res = supabase.from_("profile").select("*").eq("user_id", user_id).execute()
        skillsheet_res = supabase.from_("skillsheet").select("*").eq("user_id", user_id).execute()
        projects_res = supabase.from_("project").select("*").eq("user_id", user_id).execute()

        profile = profile_res.data if profile_res and profile_res.data else {}
        skillsheet = skillsheet_res.data if skillsheet_res and skillsheet_res.data else {}
        projects = projects_res.data if projects_res and projects_res.data else []

        app.logger.info(f"PDF表示ページ読み込み成功: user_id={user_id} プロジェクト件数={len(projects)}")
        return render_template(
            "view_pdf.html",
            pdf_path=pdf_path,
            profile=profile,
            skillsheet=skillsheet,
            projects=projects
        )

    except Exception as e:
        app.logger.exception(f"PDF表示ページでデータ取得中に例外発生: user_id={user_id} エラー={e}")
        session['error'] = "PDF表示に失敗しました。"
        return redirect(url_for('dashboard'))


#  ログアウト処理
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('home'))


# アプリの実行
if __name__ == "__main__":
    app.run(debug=True)
