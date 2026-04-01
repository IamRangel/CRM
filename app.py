from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
    session,
)
from models import db, Lead, Historico, Usuario
from sqlalchemy import extract
import engine
import os, pyperclip
from datetime import datetime, timedelta

from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["SECRET_KEY"] = "dev-phd-system-2026-rangel"

# 🔐 CONTROLE DE SESSÃO
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)
app.config["SESSION_PERMANENT"] = False

db.init_app(app)

# ================= LOGIN CONFIG =================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para acessar esta página."
login_manager.login_message_category = "info"

ADMIN_USER = "admin"
ADMIN_PASS = "admin"


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# 🔥 GARANTE SESSÃO NÃO PERSISTENTE
@app.before_request
def make_session_non_permanent():
    session.permanent = False


# ================= CONTEXT =================
@app.context_processor
def utility_processor():
    return dict(tempo_relativo=engine.tempo_relativo)


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = Usuario.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=False)
            return redirect(url_for("index"))
        else:
            flash("Login inválido", "error")

    return render_template("login.html")


# ================= LOGOUT =================
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ================= CADASTRO =================
# ================= CADASTRO =================
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        admin_user = request.form.get("admin_user")
        admin_pass = request.form.get("admin_pass")

        if admin_user == ADMIN_USER and admin_pass == ADMIN_PASS:
            username = request.form.get("username")
            password = request.form.get("password")

            # NOVO: Verificação de duplicidade
            usuario_existente = Usuario.query.filter_by(username=username).first()
            if usuario_existente:
                flash("Este nome de usuário já está em uso.", "error")
                return render_template("cadastro.html")

            hash_senha = generate_password_hash(password)
            novo = Usuario(username=username, password=hash_senha)
            db.session.add(novo)
            db.session.commit()

            flash("Usuário criado com sucesso!", "success")
            return redirect(url_for("login"))
        else:
            flash("Credenciais de admin inválidas", "error")

    return render_template("cadastro.html")


# ================= CRM (PROTEGIDO) =================
@app.route("/")
@login_required
def index():
    # Tenta pegar da URL, senão da sessão, senão do dia atual
    mes_filtro = request.args.get(
        "mes", session.get("filtro_mes", datetime.now().month), type=int
    )
    ano_filtro = request.args.get(
        "ano", session.get("filtro_ano", datetime.now().year), type=int
    )

    # Salva na sessão para persistência ao navegar entre páginas
    session["filtro_mes"] = mes_filtro
    session["filtro_ano"] = ano_filtro

    status_filtro = request.args.get("status", "TODOS")

    # Base da query filtrando por Mês e Ano
    query_base = Lead.query.filter(
        extract("month", Lead.data_cadastro) == mes_filtro,
        extract("year", Lead.data_cadastro) == ano_filtro,
    )

    all_leads_mes = query_base.all()

    # Cálculo de estatísticas para os cards superiores
    stats = {
        "TOTAL": len(all_leads_mes),
        "INTERESSADOS": query_base.filter_by(status_comercial="INTERESSADO").count(),
        "PENDENTES": 0,
        "NAO_INTERESSADO": query_base.filter_by(
            status_comercial="SEM_INTERESSE"
        ).count(),
        "FECHADOS": query_base.filter_by(status_comercial="FECHADO").count(),
    }

    # Lógica para contar Pendentes baseada na engine de atraso
    for lead in all_leads_mes:
        lead.acao_pendente = engine.decidir_acao_lead(lead)
        if lead.acao_pendente:
            stats["PENDENTES"] += 1

    # Filtragem da lista de exibição baseada no status clicado
    if status_filtro == "PENDENTES":
        leads_exibir = [l for l in all_leads_mes if engine.decidir_acao_lead(l)]
    elif status_filtro == "INTERESSADOS":
        leads_exibir = query_base.filter_by(status_comercial="INTERESSADO").all()
    elif status_filtro == "NAO_INTERESSADO":
        leads_exibir = query_base.filter_by(status_comercial="SEM_INTERESSE").all()
    elif status_filtro == "FECHADOS":
        leads_exibir = query_base.filter_by(status_comercial="FECHADO").all()
    else:
        leads_exibir = all_leads_mes

    db.session.commit()

    return render_template(
        "index.html",
        leads=leads_exibir,
        stats=stats,
        mes_atual=mes_filtro,
        ano_atual=ano_filtro,
        status_ativo=status_filtro,
    )


@app.route("/dashboard")
@login_required
def dashboard():
    # 1. PEGA O MÊS E ANO (URL -> SESSÃO -> ATUAL)
    mes = request.args.get(
        "mes", session.get("filtro_mes", datetime.now().month), type=int
    )
    ano = request.args.get(
        "ano", session.get("filtro_ano", datetime.now().year), type=int
    )

    # Atualiza a sessão para manter a consistência entre as páginas
    session["filtro_mes"] = mes
    session["filtro_ano"] = ano

    motivo_selecionado = request.args.get("motivo")

    # 2. BUSCA OS LEADS DO PERÍODO SELECIONADO
    leads_mes_query = Lead.query.filter(
        extract("month", Lead.data_cadastro) == mes,
        extract("year", Lead.data_cadastro) == ano,
    )
    leads_mes = leads_mes_query.all()
    total = len(leads_mes)

    # 3. FILTRA APENAS OS QUE DESISTIRAM (SEM INTERESSE)
    desistentes = [l for l in leads_mes if l.status_comercial == "SEM_INTERESSE"]

    # 4. CONTAGEM DINÂMICA DE MOTIVOS
    contagem_motivos = {}
    for d in desistentes:
        # Se o motivo estiver vazio no banco, define como "Não Informado"
        mot = d.motivo_sem_interesse if d.motivo_sem_interesse else "Não Informado"
        contagem_motivos[mot] = contagem_motivos.get(mot, 0) + 1

    # Transforma o dicionário em lista para o template/gráfico
    dados_motivos = [{"motivo": k, "qtd": v} for k, v in contagem_motivos.items()]

    # 5. CÁLCULO DA TAXA DE DESISTÊNCIA
    taxa_desistencia = 0
    if total > 0:
        taxa_desistencia = round((len(desistentes) / total) * 100, 1)

    # 6. FILTRO DE ALUNOS POR MOTIVO (Para a tabela detalhada)
    alunos_motivo = []
    if motivo_selecionado:
        alunos_motivo = [
            l for l in desistentes if l.motivo_sem_interesse == motivo_selecionado
        ]

    return render_template(
        "dashboard.html",
        motivos=dados_motivos,
        total=total,
        mes=mes,
        ano=ano,
        alunos=alunos_motivo,
        mot_ativo=motivo_selecionado,
        taxa=taxa_desistencia,
    )


# ================= RESTO DO SISTEMA =================
@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")
    if file:
        if not os.path.exists(app.config["UPLOAD_FOLDER"]):
            os.makedirs(app.config["UPLOAD_FOLDER"])
        path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(path)
        engine.processar_upload_csv(path, db, Lead)
    return redirect(url_for("index"))


@app.route("/status/<int:lead_id>/<novo_status>", methods=["POST"])
@login_required
def mudar_status(lead_id, novo_status):
    lead = db.session.get(Lead, lead_id)
    motivo = request.form.get("motivo")
    if lead:
        lead.status_comercial = novo_status
        if motivo:
            lead.motivo_sem_interesse = motivo
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


@app.route("/enviar/<int:lead_id>")
@login_required
def enviar_wa(lead_id):
    lead = db.session.get(Lead, lead_id)
    if lead:
        nome = engine.extrair_primeiro_nome(lead.nome)
        msg = engine.montar_mensagem(nome, lead.acao_pendente)
        pyperclip.copy(msg)
        os.startfile(f"whatsapp://send?phone=55{lead.contato}")

        h = Historico(lead_id=lead.id, acao=lead.acao_pendente, mensagem=msg)
        db.session.add(h)
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


@app.route("/verificar/<int:lead_id>")
@login_required
def verificar_wa(lead_id):
    lead = db.session.get(Lead, lead_id)
    if lead:
        os.startfile(f"whatsapp://send?phone=55{lead.contato}")
        h = Historico(lead_id=lead.id, acao="VISUALIZOU", mensagem="Verificou perfil.")
        db.session.add(h)
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


@app.route("/comentario/<int:lead_id>", methods=["POST"])
@login_required
def salvar_comentario(lead_id):
    lead = db.session.get(Lead, lead_id)
    if lead:
        lead.comentario = request.form.get("comentario")
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


# ================= RUN =================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, use_reloader=False)
