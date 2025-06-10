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

# ログ出力
import logging
from logging.handlers import RotatingFileHandler

# AI生成に必要なライブラリ
import google.generativeai as genai
import re

# pdf作成に必要なライブラリ
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
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # 15分操作なしで自動ログアウト


# セッションの永続化を有効にする
@app.before_request
def before_request():
    session.permanent = True  # 永続的なセッション設定
    if 'user_id' in session:
        # セッションが存在している場合のみ更新
        session.modified = True


#  セキュリティの強化設定
app.config['SESSION_COOKIE_SECURE'] = False     # HTTPSのみでクッキー送信 localhost環境のため一時出来にflase
app.config['SESSION_COOKIE_HTTPONLY'] = True   # JavaScriptからのアクセスを防止
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # クロスサイトのCSRF防止


# --- ログディレクトリ設定 ---
LOG_DIR = os.path.abspath("logs")
os.makedirs(LOG_DIR, exist_ok=True)

# --- ログフォーマット ---
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s [%(pathname)s:%(lineno)d - %(funcName)s()] %(message)s'
)


# --- Flaskロガーの初期化 ---
app.logger.handlers.clear()
app.logger.setLevel(logging.DEBUG)

# --- INFOログ（INFOのみをinfo.txtに保存） ---
info_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'info.txt'), maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
info_handler.setLevel(logging.INFO)
info_handler.addFilter(lambda record: record.levelno == logging.INFO)
info_handler.setFormatter(formatter)

# --- WARNING以上ログ（WARNING, ERROR, CRITICALをerror.txtに保存） ---
warning_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'error.txt'), maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
warning_handler.setLevel(logging.WARNING)
warning_handler.setFormatter(formatter)

# --- コンソールログ（DEBUG以上） ---
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

# --- ハンドラー登録 ---
app.logger.addHandler(info_handler)
app.logger.addHandler(warning_handler)
app.logger.addHandler(console_handler)


#  ホームページ (ログインかサインアップを選ぶ画面)
@app.route("/", methods=["GET"])
def home():
    # ログ出力
    app.logger.debug("DEBUG ログ")
    app.logger.info("INFO ログ")
    app.logger.warning("WARNING ログ")
    app.logger.error("ERROR ログ")
    app.logger.critical("CRITICAL ログ")
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
                session["access_token"] = user.session.access_token
                session["refresh_token"] = user.session.refresh_token
                session["user_id"] = user.user.id
                session["user_email"] = user.user.email

                print(f"ログイン成功！ユーザーID: {email}")
                return redirect(url_for('dashboard'))
            else:
                return render_template("login.html", error="メールの確認が完了していません。")
        except Exception as e:
            print(f"ログイン失敗: {e}")
            return render_template("login.html", error="ログインに失敗しました。")

    return render_template("login.html")


# emailアドレス更新ページ & 処理
@app.route("/update_email", methods=["GET", "POST"])
def update_email():
    if 'access_token' not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        new_email = request.form.get("new_email")

        if not new_email:
            return render_template("update_email.html", error="新しいメールアドレスを入力してください。")

        try:
            # メール変更とリダイレクトURLを指定
            supabase.auth.session = lambda: {"access_token": session["access_token"]}
            supabase.auth.update_user({
                "email": new_email
            })

            return render_template("update_email.html", success=f"{new_email} に確認メールを送信しました。")
        except Exception as e:
            print("❌ メールアドレス変更失敗:", e)
            return render_template("update_email.html", error="リンクの送信に失敗しました。")

    return render_template("update_email.html")


# 1. OTP送信フォーム
@app.route("/update_password_request", methods=["GET", "POST"])
@log_action("パスワード更新リクエスト")
def update_password_request():
    if request.method == "POST":
        email = request.form["email"]
        try:
            supabase.auth.sign_in_with_otp({"email": email})  # OTPを送信
            return redirect(url_for("verify_otp", email=email))
        except AuthApiError as e:
            if "only request this after" in str(e):
                error = "しばらくしてから再試行してください。"
            else:
                error = "エラーが発生しました。もう一度お試しください。"
            return render_template("update_password_request.html", error=error, email=email)
        except Exception:
            error = "予期しないエラーが発生しました。"
            return render_template("update_password_request.html", error=error, email=email)

    return render_template("update_password_request.html")


# 2. OTP検証フォーム
@app.route("/verify_otp", methods=["GET", "POST"])
@log_action("OTP検証")
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
                # ✅ トークン付きでリダイレクト
                return redirect(url_for("update_password_form",
                                        access_token=session.access_token,
                                        refresh_token=session.refresh_token))
            else:
                error = "セッション情報が取得できませんでした。"
                return render_template("verify_otp.html", email=email, error=error)
        except Exception as e:
            error = f"OTP検証に失敗しました: {e}"
            return render_template("verify_otp.html", email=email, error=error)

    return render_template("verify_otp.html", email=email)


# 3. パスワード更新フォーム
@app.route("/update_password_form", methods=["GET", "POST"])
@log_action("パスワード変更フォーム")
def update_password_form():
    access_token = request.args.get("access_token")
    refresh_token = request.args.get("refresh_token")

    if access_token and refresh_token:
        try:
            supabase.auth.set_session(access_token, refresh_token)
        except Exception as e:
            error = "セッションの設定に失敗しました。もう一度ログインし直してください。"
            return render_template("update_password_form.html", error=error)

    if request.method == "POST":
        password = request.form["password"]
        try:
            supabase.auth.update_user({"password": password})
            flash("パスワードを変更しました。ログインしてください。", "success")
            return redirect(url_for("login"))

        except AuthWeakPasswordError:
            error = (
                "パスワードは次のすべてを含める必要があります："
                "小文字・大文字・数字・記号（例: !@#$%^&*)"
            )
            return render_template("update_password_form.html", error=error)

        except AuthApiError:
            error = "パスワードの変更に失敗しました。もう一度お試しください。"
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


#  ダッシュボード（ログイン後のページ）
@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
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
        print("project 取得結果:", response.data)
        projects = response.data if response.data else []
    except Exception as e:
        print("project 取得エラー:", e)
        projects = []

    return render_template(
        "dashboard.html",
        user_id=user_id,
        user_email=user_email,
        profile=data["profile"],
        skillsheet=data["skillsheet"],
        projects=projects,  # ← ここはリスト
        error=error  # エラーメッセージをテンプレートに渡す
    )


#  プロフィール入力処理
@app.route("/profile_input", methods=["GET", "POST"])
def profile_input():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        last_name = request.form.get("last_name")   # 名字を取得
        first_name = request.form.get("first_name") # 名前を取得
        last_name_kana = request.form.get("last_name_kana") # カタカナの名字を取得
        first_name_kana = request.form.get("first_name_kana") # カタカナの名前を取得
        birth_date = request.form.get("birth_date")  # 生年月日を取得
        location = request.form.get("location")     #最寄り駅
        occupation = request.form.get("occupation") #職業
        education = request.form.get("education") #学歴
        certifications = request.form.get("certifications") #資格
        bio = request.form.get("bio") #自己紹介

        # 生年月日から年齢を計算
        if birth_date:
            birth_date = datetime.strptime(birth_date, '%Y-%m-%d')
            today = datetime.now()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        else:
            age = None

        # カタカナからローマ字のイニシャルを生成
        def generate_initial(last_name_kana, first_name_kana):
            if not last_name_kana or not first_name_kana:
                return ""
            
            # カタカナからローマ字への変換マップ
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
                'ワ': 'W', 'ヲ': 'O',
                'ン': 'N',
                'ガ': 'G', 'ギ': 'G', 'グ': 'G', 'ゲ': 'G', 'ゴ': 'G',
                'ザ': 'Z', 'ジ': 'J', 'ズ': 'Z', 'ゼ': 'Z', 'ゾ': 'Z',
                'ダ': 'D', 'ヂ': 'J', 'ヅ': 'Z', 'デ': 'D', 'ド': 'D',
                'バ': 'B', 'ビ': 'B', 'ブ': 'B', 'ベ': 'B', 'ボ': 'B',
                'パ': 'P', 'ピ': 'P', 'プ': 'P', 'ペ': 'P', 'ポ': 'P',
                'ャ': 'Y', 'ュ': 'Y', 'ョ': 'Y',
                'ッ': '',  # 小さい「ッ」は次の文字の子音を重ねる
            }
            
            # カタカナの最初の文字を取得してローマ字に変換
            last_initial = kana_to_romaji.get(last_name_kana[0], last_name_kana[0])
            first_initial = kana_to_romaji.get(first_name_kana[0], first_name_kana[0])
            
            return f"{last_initial}{first_initial}"

        initial = generate_initial(last_name_kana, first_name_kana)
        full_name = f"{last_name} {first_name}"

        # supabaseのtableにデータを追加
        try:
            result = supabase.table("profile").upsert({
                "user_id": session['user_id'],  # ユーザーID
                "last_name": last_name,
                "first_name": first_name,
                "last_name_kana": last_name_kana,
                "first_name_kana": first_name_kana,
                "name": full_name,  # フルネームも保存
                "birth_date": birth_date.strftime('%Y-%m-%d') if birth_date else None,  # 生年月日を保存
                "age": age,  # 計算した年齢を保存
                "location": location,
                "occupation": occupation,
                "education": education,
                "certifications": certifications,
                "bio": bio,
                "initial": initial,  # イニシャルを追加
            }, on_conflict=["user_id"]).execute()

            # レスポンスのステータスコードを確認
            if result.model_dump().get("error"):
                print("保存エラー:", result.error)

                # 入力値を再表示するため、フォーム値からprofile辞書を構築
                profile_input = {
                    "last_name": last_name,
                    "first_name": first_name,
                    "last_name_kana": last_name_kana,
                    "first_name_kana": first_name_kana,
                    "birth_date": birth_date.strftime('%Y-%m-%d') if birth_date else None,
                    "location": location,
                    "occupation": occupation,
                    "education": education,
                    "certifications": certifications,
                    "bio": bio,
                    "initial": initial,
                }

                return render_template("profile_input.html", error="保存に失敗しました。", profile=profile_input)

            # 成功の場合
            return redirect(url_for("dashboard"))

        except Exception as e:
            # 例外処理
            print(f"エラー: {e}")
            return render_template("profile_input.html", error="予期せぬエラーが発生しました。", profile={})


    # GET時：既存データを取得してフォームに反映
    user_id = session['user_id']
    profile_data = get_supabase_data("profile", user_id) or {}
    # 取得したデータをフォームに表示
    return render_template("profile_input.html", profile=profile_data)
            


#  スキルシート作成ページ & 処理
@app.route("/skillsheet_input", methods=["GET", "POST"])
def skillsheet_input():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    

    # Flaskセッションにユーザーがいる前提
    user_id = session.get("user_id")


    # データ送信
    data = {
        "user_id": user_id,
        "python": request.form.get("python"),
        
    }

    result = supabase.table("skillsheet").upsert(data).execute()
    print(result)



    # スキルシートのカテゴリとスキルを定義
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
        "サーバソフトウェア": ["apache_http_server", "nginx", "iis", "apache_tomcat", "oracle_weblogic", "adobe_coldfusion", "wildfly", "websphere", "jetty", "glassfish", "squid", "varnish", "sendmail", "postfix", ],
        "データベース": ["mysql", "oracle", "postgresql", "sqlite", "mongodb", "casandra", "microsoft_sql_server", "amazon_aurora", "mariadb", "redis", "dynamodb", "elasticsearch", "amazon_rds"],
        "ツール類": ["wireshark", "owasp_zap", "burp_suite", "nessus", "openvas", "tera_term", "powershell", "cmd", "winscp", "tor", "kintone", "jira", "confluence", "servicenow", "sakura_editor", "power_automate", "automation_anywhere", "active_directory", "sap_erp", "salesforce"],
        "言語": ["japanese", "english", "chinese", "korean", "tagalog", "german", "spanish", "italian", "russian", "portugese", "french", "lithuanian", "malay", "romanian"],
        "セキュリティ調査ツール": ["shodan", "censys", "greynoise", "ibm_x_force", "urlsan.io", "abuselpdb", "virustotal", "cyberchef", "any.run", "hybrid_analysis", "wappalyzer", "wireshark"],
    }

    

    skillsheet_data = get_supabase_data("skillsheet", session['user_id'])


    

    # POSTリクエストの処理
    if request.method == "POST":
        data = {field: request.form.get(field) for fields in categories.values() for field in fields}

       


         # user_id と更新日時を追加
        data["user_id"] = session['user_id']
        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        

       # Supabaseへ upsert
        result = supabase.table("skillsheet").upsert(data, on_conflict=["user_id"]).execute()

        # ↓ここを追加
        print("🪵 Supabase upsert結果:", result.model_dump())

        if result.model_dump().get("error"):
            return render_template("skillsheet_input.html", categories=categories, skillsheet=skillsheet_data, error="保存に失敗しました")

        return redirect(url_for("dashboard"))

    # GET時の表示
    return render_template("skillsheet_input.html", categories=categories, skillsheet=skillsheet_data)




# プロジェクト入力ページ & 処理
@app.route("/project_input", methods=["GET", "POST"])
def project_input():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":
        # AI生成のためにフォームからプロジェクト情報を取得
        action = request.form.get("action")

        name = request.form.get("name") # プロジェクト名を取得
        description = request.form.get("description") # プロジェクトの説明を取得
        start_at = request.form.get("start_at") # 開始日を取得
        end_at = request.form.get("end_at")     # 終了日を取得
        technologies = request.form.getlist("technologies") # 使用した技術を取得（複数選択可能）



        if action == "generate":
            prompt = f"""
            以下のプロジェクト概要を基に、職務経歴書向けの箇条書き形式で実績説明を生成してください。

            # プロジェクト概要:
            {description}
            """

            try:
                model = genai.GenerativeModel(model_name="gemini-2.0-flash-lite")
                response = model.generate_content(prompt)
                text = response.text

                # Markdown記法や記号の除去
                cleaned = re.sub(r'^##+\s*', '', text, flags=re.MULTILINE)
                cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
                cleaned = re.sub(r'^[\*\-\+]\s+', '', cleaned, flags=re.MULTILINE)
                cleaned = re.sub(r'^\*\s+', '', cleaned, flags=re.MULTILINE)
                cleaned = re.sub(r'\*(\S.*?)\*', r'\1', cleaned)
                cleaned = cleaned.replace('*', '')

                session['generated_summary'] = cleaned

            except Exception as e:
                print("AI生成失敗:", e)
                session['generated_summary'] = "AI生成に失敗しました。"

            project = {
                
                "name": name,
                "description": description,
                "start_at": start_at,
                "end_at": end_at,
                "technologies": technologies,
            }

            return render_template("project_input.html", project=project, generated_summary=cleaned)

        elif action == "save":
            try:
                # 空欄をNoneに
                start_at = start_at or None
                end_at = end_at or None

                # 必須チェック
                if not name or not description:
                    return render_template("project_input.html", error="プロジェクト名と説明は必須です。")

                result = supabase.table("project").insert({
                    "user_id": session['user_id'],
                    "name": name,
                    "description": description,
                    "start_at": start_at,
                    "end_at": end_at,
                    "technologies": technologies,
                }).execute()

                # 成功かどうかは result.data で判断
                if not result.data:
                    print("保存エラー（dataなし）:", result.model_dump())
                    return render_template("project_input.html", error="プロジェクトの保存に失敗しました。")

                return redirect(url_for("dashboard"))

            except Exception as e:
                print(f"予期せぬエラー: {e}")
                return render_template("project_input.html", error="予期せぬエラーが発生しました。")

    # GET時
    generated_summary = session.pop('generated_summary', "")
    # 
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
def project_edit(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":

        action = request.form.get("action")

        # フォームからプロジェクト情報を取得
        name = request.form.get("name")
        description = request.form.get("description")
        start_at = request.form.get("start_at") or None
        end_at = request.form.get("end_at") or None
        technologies = request.form.getlist("technologies")

        # AI生成のための処理
        if action == "generate":
            prompt = f"""
            以下のプロジェクト概要を基に、職務経歴書向けの箇条書き形式で実績説明を生成してください。

            # プロジェクト概要:
            {description}
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

            except Exception as e:
                print("AI生成失敗:", e)
                session['generated_summary'] = "AI生成に失敗しました。"

            project = {
                "id": project_id,
                "name": name,
                "description": description,
                "start_at": start_at,
                "end_at": end_at,
                "technologies": technologies,
                    }   

            return render_template("project_edit.html", project=project, generated_summary=cleaned)

        elif action == "save":

            # フォームからの更新処理
            try:
                result = supabase.table("project").update({
                    "name": name,
                    "description": description,
                    "start_at": start_at,
                    "end_at": end_at,
                    "technologies": technologies,
                }).eq("id", project_id).eq("user_id", session['user_id']).execute()

                return redirect(url_for("dashboard"))

            except Exception as e:
                print("更新エラー:", e)
                return render_template("project_edit.html", error="更新に失敗しました。")

    
    else:
        try:
            response = supabase.table("project").select("*").eq("id", project_id).eq("user_id", session['user_id']).maybe_single().execute()
            project = response.data

            if not project:
                return redirect(url_for("dashboard"))

            return render_template("project_edit.html", project=project)

        except Exception as e:
            print("取得エラー:", e)
            return redirect(url_for("dashboard"))



# PDF作成ページ
@app.route("/create_pdf", methods=["GET"])
def create_pdf():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for("login"))

    try:
        # ───  from_() を使ってクエリし、execute() の結果を必ず受け取る ───
        print(f"Fetching profile for user_id: {user_id}")
        profile_res = (
            supabase
            .from_("profile")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        print(f"Profile response: {profile_res}")

        print(f"Fetching skillsheet for user_id: {user_id}")
        skillsheet_res = (
            supabase
            .from_("skillsheet")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        print(f"Skillsheet response: {skillsheet_res}")

        print(f"Fetching projects for user_id: {user_id}")
        projects_res = (
            supabase
            .from_("project")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        print(f"Projects response: {projects_res}")

        # ───  execute() が None を返していないか、error がないかチェック ───
        for name, res in [("profile", profile_res), ("skillsheet", skillsheet_res), ("projects", projects_res)]:
            if res is None:
                print(f"Error: {name} response is None")
                session['error'] = f"{name}のデータ取得に失敗しました。"
                return redirect(url_for('dashboard'))
            if hasattr(res, "error") and res.error:
                print(f"Error: {name} query error: {res.error}")
                app.logger.error(f"{name} query error: {res.error}")
                session['error'] = f"{name}のデータ取得に失敗しました。"
                return redirect(url_for('dashboard'))

        # ───  data 部分が None の場合は「レコードなし」として扱う ───
        profile = profile_res.data[0] if profile_res.data and len(profile_res.data) > 0 else {}
        skillsheet = skillsheet_res.data[0] if skillsheet_res.data and len(skillsheet_res.data) > 0 else {}
        projects = projects_res.data or []

        # プロフィールデータが空の場合は、ダッシュボードにリダイレクト
        if not profile:
            session['error'] = "プロフィールデータが登録されていません。"
            return redirect(url_for('dashboard'))

        # PDF初期化
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

        # プロフィール情報の表示
        p.setFont("IPAexGothic", 16)
        p.drawString(profile_x, profile_y, f"氏名：{profile.get('initial', '')}")
        p.setFont("IPAexGothic", 12)
        p.drawString(profile_x, profile_y - 25, f"年齢: {profile.get('age', '')}")
        p.drawString(profile_x, profile_y - 45, f"職業: {profile.get('occupation', '')}")
        if profile.get('location'):
            p.drawString(profile_x, profile_y - 65, f"所在地: {profile.get('location', '')}")
        if profile.get('education'):
            p.drawString(profile_x, profile_y - 85, f"学歴: {profile.get('education', '')}")
        if profile.get('certifications'):
            p.drawString(profile_x, profile_y - 105, f"資格: {profile.get('certifications', '')}")
        if profile.get('bio'):
            p.drawString(profile_x, profile_y - 125, f"自己紹介: {profile.get('bio', '')}")

        # スキル一覧描画開始Y座標（紺色ブロックの下から開始）
        y = height - block_height - 50

        # ========== スキル ==========
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



        # --- プロジェクト履歴ページ ---

        # ── 折り返し描画用ヘルパー関数 ──
        def draw_wrapped_text(canvas, text, x, y, max_width,
                            font_name="IPAexGothic", font_size=10, leading=14):
            """
            canvas: ReportLab のキャンバスオブジェクト
            text: 折り返したい全文
            x, y: 左下基準の描画開始座標
            max_width: 1行あたりの最大幅（ポイント単位）
            font_name, font_size: フォントとサイズ
            leading: 行間（フォントサイズより少し大きめが推奨）
            戻り値: 描画した行数
            """
            canvas.setFont(font_name, font_size)
            words = text.split()  # 空白で分割して単語ごとに処理

            lines = []
            current_line = ""
            for w in words:
                # まず current_line + " " + w の幅を測定
                test_line = current_line + (" " if current_line else "") + w
                test_width = pdfmetrics.stringWidth(test_line, font_name, font_size)
                if test_width <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = w
            if current_line:
                lines.append(current_line)

            # 描画：y から行間ごとに下方向へずらして一行ずつ描画
            for i, line in enumerate(lines):
                canvas.drawString(x, y - i * leading, line)

            return len(lines)

        
        # プロジェクト一覧は必ず新しいページに表示
        p.showPage()
        y = height - 50

        # ヘッダーの装飾
        p.setFillColor(navy)
        p.rect(50, y - 5, width - 100, 1, fill=True, stroke=0)
        p.setFillColor(black)

        # プロジェクト履歴のタイトル
        p.setFont("IPAexGothic", 16)
        p.drawString(60, y, "■ プロジェクト履歴")
        y -= 50

        # 日付パース用関数
        def parse_date(date_str):
            if not date_str or not isinstance(date_str, str):
                return datetime.min
            try:
                # "YYYY-MM-DDTHH:MM:SS" の場合、先頭10文字だけを読み込む
                return datetime.strptime(date_str[:10], "%Y-%m-%d")
            except Exception as e:
                print(f"parse_date error with input '{date_str}': {e}")
                return datetime.min

        # 開始日でソートして新しい順に並べる
        sorted_projects = sorted(
            projects,
            key=lambda x: parse_date(x.get("start_at")),
            reverse=True
        )

        prev_y = y

        for i, project in enumerate(sorted_projects):
            # ── 改ページ判定 ──
            if y < 150:
                p.showPage()
                y = height - 50
                p.setFillColor(navy)
                p.rect(50, y - 5, width - 100, 1, fill=True, stroke=0)
                p.setFillColor(black)
                p.setFont("IPAexGothic", 16)
                p.drawString(60, y, "■ プロジェクト履歴（続き）")
                y -= 50

            # ── デバッグプリント：何件目かと y の値を確認 ──
            print(f"{i+1}件目: {project.get('name')}, y={y}")

            # タイムラインの基準位置（テキスト描画用）
            timeline_x = 120

            # プロジェクト名（タイムラインの右側）
            p.setFont("IPAexGothic", 12)
            p.setFillColor(navy)
            p.drawString(timeline_x + 20, y + 5, f"・{project.get('name', '')}")
            p.setFillColor(black)

            # プロジェクト詳細（タイムラインの右側）
            detail_x = timeline_x + 20
            detail_y = y - 15

            # 詳細情報の装飾（横線）
            p.setFillColor(navy)
            p.rect(detail_x - 5, detail_y - 2, width - detail_x - 50, 1, fill=True, stroke=0)
            p.setFillColor(black)

            # 期間
            if project.get("start_at") or project.get("end_at"):
                p.setFont("IPAexGothic", 10)
                p.drawString(
                    detail_x,
                    detail_y,
                    f"期間: {project.get('start_at', '')} ～ {project.get('end_at', '')}"
                )
                detail_y -= 20

            # 役割
            if project.get("role"):
                p.setFont("IPAexGothic", 10)
                p.drawString(detail_x, detail_y, f"役割: {project.get('role')}")
                detail_y -= 20

            # 説明（折り返し描画）
            if project.get("description"):
                p.setFont("IPAexGothic", 10)
                description_text = f"説明: {project.get('description')}"
                max_width = width - detail_x - 50
                # 折り返し後に何行描画したかを取得
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
                # 折り返し行数分だけ Y を下げる
                detail_y -= (num_lines * 14)

            # 技術
            if project.get("technologies"):
                p.setFont("IPAexGothic", 10)
                techs = (
                    ", ".join(project["technologies"])
                    if isinstance(project["technologies"], list)
                    else str(project["technologies"])
                )
                p.drawString(detail_x, detail_y, f"技術: {techs}")
                detail_y -= 20

            # 次のプロジェクトの描画開始位置を更新
            prev_y = y
            y = detail_y - 40  # プロジェクト間の間隔を広げる




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

        return redirect(url_for('view_pdf'))

# PDF作成処理
    except Exception as e:
        print(f"PDF作成エラー: {e}")
        session['error'] = f"PDFの作成に失敗しました: {str(e)}"
        return redirect(url_for('dashboard'))



# PDF表示ページ
@app.route("/view_pdf")
def view_pdf():
    if 'user_id' not in session:
        return redirect(url_for("login"))
    
    user_id = session['user_id']
    pdf_path = f"static/temp/{user_id}_skillsheet.pdf"
    
    if not os.path.exists(pdf_path):
        return redirect(url_for('create_pdf'))

    # ← ここで profile, skillsheet, projects を再フェッチ
    profile_res = (
        supabase
        .from_("profile")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    skillsheet_res = (
        supabase
        .from_("skillsheet")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    projects_res = (
        supabase
        .from_("project")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )


    profile    = profile_res.data    if profile_res and profile_res.data else {}
    skillsheet = skillsheet_res.data if skillsheet_res and skillsheet_res.data else {}
    projects   = projects_res.data   if projects_res and projects_res.data else []

    return render_template(
        "view_pdf.html",
        pdf_path=pdf_path,
        profile=profile,
        skillsheet=skillsheet,
        projects=projects
    )

#  ログアウト処理
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('home'))


# アプリの実行
if __name__ == "__main__":
    app.run(debug=True)
