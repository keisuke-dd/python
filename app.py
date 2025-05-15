from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
from datetime import datetime, timezone, timedelta
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
app.secret_key = "111"  # セッション用のシークレットキー

#  セッションの設定
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # 30分操作なしで自動ログアウト

# セッションの永続化を有効にする
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



# 共通関数: Supabaseからデータを取得する
def get_supabase_data(table_name, user_id, exclude_fields=None):
    """
    Supabaseからデータを取得し、指定されたフィールドを除外する。

    :param table_name: Supabaseのテーブル名
    :param user_id: ユーザーID
    :param exclude_fields: 除外するフィールドのリスト（デフォルトは["user_id", "created_at", "updated_at"]）
    :return: 取得したデータの辞書 or None
    """
    if exclude_fields is None:
        exclude_fields = ["user_id", "created_at", "updated_at"]

    try:
        response = supabase.table(table_name).select("*").eq("user_id", user_id).execute()
        print(f"{table_name} 取得結果:", response.data)

        if response.data and len(response.data) > 0:
            # 不要なフィールドを除外したデータを返す
            return {
                key: value for key, value in response.data[0].items()
                if key not in exclude_fields and value
            }
        else:
            return None
    except Exception as e:
        print(f"{table_name} 取得エラー:", e)
        return None


#  ダッシュボード（ログイン後のページ）
@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_email = session.get('user_email')

    # 取得したいテーブル名と変数名のペア
    tables = {
        "profile": "profile",
        "skillsheet": "skillsheet",
        "projects": "projects"
    }

    # データ取得
    data = {}
    for table_name, var_name in tables.items():
        data[var_name] = get_supabase_data(table_name, user_id)

    # プロジェクトは複数行ある可能性があるので、リスト形式でテンプレートに渡す
    if data["projects"]:
        data["projects"] = [data["projects"]] if isinstance(data["projects"], dict) else data["projects"]

    # テンプレートに渡す
    return render_template(
        "dashboard.html",
        user_id=user_id,
        user_email=user_email,
        profile=data["profile"],
        skillsheet=data["skillsheet"],
        projects=data["projects"]
    )



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
    


#  スキルシート作成ページ & 処理
@app.route("/skillsheet_input", methods=["GET", "POST"])
def skillsheet_input():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":
        # フォームの項目名リストを作成
        fields = [
                    # 言語
                    "python", "ruby", "javascript", "shell", "c", "c++", "c#", "java", "html", "go", "css", "swift", "kotlin", "vba",

                    # フレームワーク
                    "ruby_on_rails", "django", "flask", "laravel", "symfony", "cakephp", "php", "next_js", "nuxt_js", "vue_js", "spring_boot", "bottle", "react",

                    # 開発環境
                    "vscode", "eclipse", "pycharm", "jupyter_notebook", "android_studio", "atom", "xcode", "webstorm", "netbeans", "visual_studio",

                    # OS
                    "widows", "windows_server", "macos", "linux", "unix", "solaris", "android", "ios", "chromeos", "centos", "ubuntu", "ms_dos",
                    "watchos", "wear_os", "raspberrypi_os", "oracle_solaris", "z/os", "firefox_os", "blackberryos", "rhel", "kali_linux", "parrot_os", "whonix",

                    # クラウド
                    "aws", "azure", "gcp", "oci",

                    # セキュリティ製品
                    "splunk", "microsoft_sentinel", "microsoft_defender_for_endpoint", "cybereason", "crowdstrike_falcon", "vectra", "exabeam",
                    "sep(symantecendpointprotection)", "tanium", "logstorage", "trellix", "fireeye_nx", "fireeye_hy", "fireeye_cm", "ivanti",
                    "f5_big_ip", "paloalto_prisma", "tenable",

                    # ネットワーク環境
                    "cisco_catalyst", "cisco_meraki", "cisco_nexus", "cisco_others", "allied_switch", "allied_others", "nec_ip8800_series", "nec_ix_series",
                    "yamaha_rtx/nvr", "hpe_aruba_switch", "fortinet_fortiswitch", "fortinet_fortogate", "paloalto_pa_series", "panasonic_switch",
                    "media_converter", "wireless_network", "other_network_devices",

                    # 仮想化基盤
                    "vmware_vsphere", "vmware_workstaion", "oracle_virtualbox", "vmware_fusion", "microsoft_hyper_v", "kvm(kernel_based_virtual_machine)",
                    "docker", "kubernetes",

                    # AI
                    "gemini", "chatgpt", "copilot", "perplexity", "grok", "azure_openai",

                    # サーバソフトウェア
                    "apache_http_server", "nginx", "iis", "apache_tomcat", "oracle_weblogic", "adobe_coldfusion", "wildfly", "websphere", "jetty", "glassfish",
                    "squid", "varnish", "sendmail", "postfix",

                    # データベース
                    "mysql", "oracle", "postgresql", "sqlite", "mongodb", "casandra", "microsoft_sql_server", "amazon_aurora", "mariadb", "redis",
                    "dynamodb", "elasticsearch", "amazon_rds",

                    # ツール類
                    "wireshark", "owasp_zap", "burp_suite", "nessus", "openvas", "tera_term", "powershell", "cmd", "winscp", "tor", "kintone", "jira",
                    "confluence", "servicenow", "sakura_editor", "power_automate", "automation_anywhere", "active_directory", "sap_erp", "salesforce",

                    # 言語（自然言語）
                    "english", "chinese", "korean", "tagalog", "german", "spanish", "italian", "russian", "portugese", "french", "lithuanian", "malay", "romanian",

                    # セキュリティ調査ツール
                    "shodan", "censys", "greynoise", "ibm_x_force", "urlsan.io", "abuselpdb", "virustotal", "cyberchef", "any.run", "hybrid_analysis",
                    "wappalyzer","wireshark"
                ]

        
        # フォームからデータを取得し、辞書に格納
        data = {field: request.form.get(field) for field in fields}
        data["user_id"] = session['user_id']
        # 修正前:
        # data["updated_at"] = datetime.utcnow().isoformat()

        # 修正後:
        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            # Supabaseにデータを保存（upsert：既存データの更新または新規挿入）
            result = supabase.table("skillsheet").upsert(data, on_conflict=["user_id"]).execute()


            if result.model_dump().get("error"):
                return render_template("skillsheet_input.html", error="スキルシートの保存に失敗しました。")
            
            return redirect(url_for("skillsheet_output"))

        except Exception as e:
            print(f"エラー: {e}")
            return render_template("skillsheet_input.html", error="予期せぬエラーが発生しました。")
        
        # ← ここが抜けていた！
    return render_template("skillsheet_input.html")
  



#  スキルシート表示ページ
@app.route("/skillsheet_output", methods=["GET"])
def skillsheet_output():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        response = supabase.table("skillsheet").select("*").eq("user_id", session['user_id']).execute()

        display_skills = {}  # ← ここで初期化しておくことで、どのパスでも存在する

        # デバッグ出力
        print("スキルシート取得結果:", response.data)
        print("display_skills:", display_skills)


        if response.data and len(response.data) > 0:
            skillsheet_data = response.data[0]

            # user_id や updated_at を除いて、空でないスキルだけ抽出
            display_skills = {
                key: value for key, value in skillsheet_data.items()
                if key not in ["user_id","created_at", "updated_at"] and value
            }

            return render_template("skillsheet_output.html", skillsheet=display_skills)

        else:
            return render_template("skillsheet_output.html", error="スキルシートが見つかりません。")

    except Exception as e:
        print(f"スキルシート取得エラー: {e}")
        return render_template("skillsheet_output.html", error="スキルシートの取得に失敗しました。")




# プロジェクト入力ページ & 処理
@app.route("/project_input", methods=["GET", "POST"])
def project_input():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        start_at = request.form.get("start_at")
        end_at = request.form.get("end_at")
        role = request.form.get("role")
        technologies = request.form.getlist("technologies")

        try:
            # Supabaseのテーブルにプロジェクトデータを保存
            result = supabase.table("project").upsert({
                "user_id": session['user_id'],
                "name": name,
                "description": description,
                "start_at": start_at,
                "end_at": end_at,
                "role": role,
                "technologies": technologies,
            }, on_conflict=["user_id", "name"]).execute()

            if result.model_dump().get("error"):
                print("保存エラー:", result.error)
                return render_template("project_input.html", error="プロジェクトの保存に失敗しました。")

            return redirect(url_for("project_output"))

        except Exception as e:
            print(f"エラー: {e}")
            return render_template("project_input.html", error="予期せぬエラーが発生しました。")

    return render_template("project_input.html")


# プロジェクト表示ページ
@app.route("/project_output", methods=["GET"])
def project_output():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        response = supabase.table("project").select("*").eq("user_id", session['user_id']).execute()

        # デバッグ出力
        print("プロジェクト取得結果:", response.data)

        if response.data and len(response.data) > 0:
            return render_template("project_output.html", project=response.data)
        else:
            return render_template("project_output.html", error="プロジェクトが見つかりません。")

    except Exception as e:
        print(f"プロジェクト取得エラー: {e}")
        return render_template("project_output.html", error="プロジェクトの取得に失敗しました。")
    


#  ログアウト処理
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('home'))


# アプリの実行
if __name__ == "__main__":
    app.run(debug=True)
