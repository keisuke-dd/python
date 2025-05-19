# 必要なライブラリのインポート
from requirements import *


# 環境変数の読み込み
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


# Supabaseクライアントの作成
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1回だけ日本語フォントを登録（フォント名は自由に決められます）
pdfmetrics.registerFont(TTFont('IPAexGothic', 'static/fonts/ipaexg.ttf'))

# Flaskの設定
app = Flask(__name__)
app.secret_key = "your_secret_key"  # セッション用のシークレットキー


#  セッションの設定
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)  # 15分操作なしで自動ログアウト


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


@app.route("/update_email", methods=["GET", "POST"])
def update_email():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":
        new_email = request.form["new_email"]

        try:
            # ユーザー情報の更新
            user = supabase.auth.update_user({
                "email": new_email
            })
            return render_template("update_email.html", success="メールアドレスを更新しました。")
        except Exception as e:
            print(f"メールアドレスの更新失敗: {e}")
            return render_template("update_email.html", error="メールアドレスの更新に失敗しました。")

    return render_template("update_email.html")


# パスワードリセットページ
@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        email = request.form.get("email")
        try:
            # Supabaseにパスワードリセットリンクをリクエスト
            supabase.auth.reset_password_for_email(email)
            return "パスワードリセットのリンクが送信されました。"
        except Exception as e:
            print(f"エラー: {e}")
            return "送信に失敗しました。"
    return render_template("reset_password.html")



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
        projects=projects  # ← ここはリスト
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
            return redirect(url_for("dashboard"))

        except Exception as e:
            # 例外処理
            print(f"エラー: {e}")
            return render_template("profile_input.html", error="予期せぬエラーが発生しました。")

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

    skillsheet_data = get_supabase_data("skillsheet", session['user_id'])

    if request.method == "POST":
        data = {field: request.form.get(field) for fields in categories.values() for field in fields}
        data["user_id"] = session['user_id']
        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = supabase.table("skillsheet").upsert(data, on_conflict=["user_id"]).execute()
        if result.model_dump().get("error"):
            return render_template("skillsheet_input.html", categories=categories, skillsheet=skillsheet_data, error="保存に失敗しました")

        return redirect(url_for("dashboard"))

    return render_template("skillsheet_input.html", categories=categories, skillsheet=skillsheet_data)
  







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
            result = supabase.table("project").insert({
                "user_id": session['user_id'],
                "name": name,
                "description": description,
                "start_at": start_at,
                "end_at": end_at,
                "role": role,
                "technologies": technologies,
            }).execute()

            if result.model_dump().get("error"):
                print("保存エラー:", result.error)
                return render_template("project_input.html", error="プロジェクトの保存に失敗しました。")

            return redirect(url_for("dashboard"))

        except Exception as e:
            print(f"エラー: {e}")
            return render_template("project_input.html", error="予期せぬエラーが発生しました。")

    return render_template("project_input.html")


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
        name = request.form.get("name")
        description = request.form.get("description")
        start_at = request.form.get("start_at")
        if start_at == "":
                start_at = None

        end_at = request.form.get("end_at")
        if end_at == "":
                end_at = None
        role = request.form.get("role")
        technologies= request.form.get("technologies")
        

        try:
            result = supabase.table("project").update({
                "name": name,
                "description": description,
                "start_at": start_at,
                "end_at": end_at,
                "role": role,
                "technologies": technologies,
            }).eq("id", project_id).eq("user_id", session['user_id']).execute()

            return redirect(url_for("dashboard"))

        except Exception as e:
            print("更新エラー:", e)
            return render_template("project_edit.html", error="更新に失敗しました。")

    else:
        try:
            response = supabase.table("project").select("*").eq("id", project_id).eq("user_id", session['user_id']).single().execute()
            project = response.data

            if not project:
                return redirect(url_for("project_edit"))

            return render_template("project_edit.html", project=project)

        except Exception as e:
            print("取得エラー:", e)
            return redirect(url_for("project_edit"))





# PDF作成ページ
@app.route("/create_pdf", methods=["GET"])
def create_pdf():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for("login"))
    
    # Supabaseからデータ取得
    profile = supabase.table("profile").select("*").eq("user_id", user_id).single().execute().data
    skillsheet = supabase.table("skillsheet").select("*").eq("user_id", user_id).single().execute().data
    projects = supabase.table("project").select("*").eq("user_id", user_id).execute().data

    # PDF初期化
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    # ========== 紺色の背景ブロック ==========
    block_width = 180
    block_height = 220
    p.setFillColor(navy)
    p.rect(0, height - block_height, block_width, block_height, fill=True, stroke=0)

    # ========== 画像挿入 ==========
    try:
        image_path = "./static/images/tom_2.png"
        p.drawImage(image_path, 40, height - 100, width=90, height=50, mask='auto')
    except Exception as e:
        print("画像読み込みエラー:", e)

    # ========== タイトル（ブロック内に） ==========
    p.setFillColorRGB(1, 1, 1)  # 白文字
    p.setFont("IPAexGothic", 16)
    p.drawString(40, height - 120, "スキルシート")

    # ========== テキストを黒に戻す ==========
    p.setFillColor(black)

    # プロフィール表示位置（ブロックの右端より右側）
    profile_x = block_width + 10  # 210
    profile_y = height - 50  # 紺ブロックの少し下あたりから開始

    p.setFont("IPAexGothic", 12)
    p.drawString(profile_x, profile_y, f"氏名: {profile.get('name', '')}")
    p.drawString(profile_x, profile_y - 18, f"年齢: {profile.get('age', '')}")
    p.drawString(profile_x, profile_y - 36, f"職業: {profile.get('occupation', '')}")

    # スキル一覧描画開始Y座標はプロフィールのさらに下あたりに設定
    y = profile_y - 180

    # ========== スキル ==========
    p.setFont("IPAexGothic", 12)
    p.drawString(100, y, "■ スキル一覧")
    y -= 30
    for skill, level in skillsheet.items():
        if skill != "user_id" and level:
            p.drawString(120, y, f"{skill.replace('_', ' ').title()}: {level}")
            y -= 15
            if y < 100:
                p.showPage()
                y = height - 50
                p.setFont("IPAexGothic", 12)

    y -= 20
    p.drawString(100, y, "■ プロジェクト一覧")
    y -= 20

    for project in projects:
        if y < 120:
            p.showPage()
            y = height - 50
            p.setFont("IPAexGothic", 12)

        p.drawString(120, y, f"・{project.get('name', '')}")
        y -= 15

        if project.get('description'):
            p.drawString(140, y, f"{project['description']}")
            y -= 15

        if project.get('start_at') or project.get('end_at'):
            p.drawString(140, y, f"期間: {project.get('start_at', '')} ～ {project.get('end_at', '')}")
            y -= 15

        if project.get('role'):
            p.drawString(140, y, f"役割: {project['role']}")
            y -= 15

        if project.get('technologies'):
            techs = ", ".join(project['technologies']) if isinstance(project['technologies'], list) else str(project['technologies'])
            p.drawString(140, y, f"技術: {techs}")
            y -= 25

    # フッター日付
    p.setFont("IPAexGothic", 9)
    p.drawString(100, 30, f"作成日: {datetime.now().strftime('%Y/%m/%d')}")

    p.showPage()
    p.save()
    buffer.seek(0)

    return make_response(buffer.read(), {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'inline; filename=skillsheet.pdf'
    })


#  ログアウト処理
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('home'))


# アプリの実行
if __name__ == "__main__":
    app.run(debug=True)
