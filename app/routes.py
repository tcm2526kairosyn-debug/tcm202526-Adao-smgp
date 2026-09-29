import csv
import io
import json
import secrets
import threading
from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, current_app, make_response, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
import resend
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db
from .models import User, PendingRegistration, ReactivationRequest, Projeto, ProjectDecision, MethodologyEvidenceBase, ToolEvidenceBase, MCDMWeights
from .services.kairosynlogic import (
    compute_indices, resolve_approach, build_decision_control_register,
    run_fit_m_level1, run_fit_m_level2,
    run_fit_t_level_a, run_fit_t_level_b,
    run_sensitivity_analysis, get_envelope_component_candidates,
    build_capability_map, get_weights_preset, weights_to_points,
    points_to_weights, criteria_labels,
)

main = Blueprint('main', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Máquina de estados ────────────────────────────────────────────────────────

TRANSITIONS = {
    ('stage_1_diagnosis',  'SUBMIT_DIAGNOSIS'):    'stage_2_approach',
    ('stage_2_approach',   'CONFIRM_APPROACH'):    'stage_3_fit_m',
    ('stage_3_fit_m',      'CONFIRM_METHODOLOGY'): 'stage_4_fit_t',
    ('stage_3_fit_m',      'REENTRY_GOVERNANCE'):  'stage_2_approach',
    ('stage_3_fit_m',      'REVISE_APPROACH'):     'stage_2_approach',
    ('stage_4_fit_t',      'CONFIRM_TOOLS'):       'stage_complete',
    ('stage_4_fit_t',      'REENTRY_METHODOLOGY'): 'stage_3_fit_m',
    ('stage_4_fit_t',      'REVISE_METHODOLOGY'):  'stage_3_fit_m',
    ('stage_4_fit_t',      'REENTRY_APPROACH'):    'stage_2_approach',
    ('stage_1_diagnosis',  'NEXT'):                'stage_2_approach',
    ('stage_2_approach',   'NEXT'):                'stage_3_fit_m',
    ('stage_3_fit_m',      'NEXT'):                'stage_4_fit_t',
    ('stage_3_evaluation', 'NEXT'):                'stage_4_tailoring',
}

STAGE_REDIRECT = {
    'stage_1_diagnosis': 'main.diagnostico',
    'stage_2_approach':  'main.etapa2',
    'stage_3_fit_m':     'main.etapa3',
    'stage_4_fit_t':     'main.etapa4',
    'stage_complete':    'main.workflow',
}


def _log_transition(decision, previous, new_state, action, cause=None):
    history = list(decision.transition_history or [])
    entry = {
        "from": previous,
        "to": new_state,
        "action": action,
        "timestamp": datetime.utcnow().isoformat(),
        "user": current_user.username
    }
    if cause:
        entry["reentry_cause"] = cause
    history.append(entry)
    decision.transition_history = history
    decision.current_stage = new_state


_WEIGHTS_FIELD = {'MEB': 'meb_weights', 'TEB': 'teb_weights'}
_WEIGHTS_STAGE_LABEL = {'MEB': 'Etapa 3 (C1-C7)', 'TEB': 'Etapa 4 (CD1-CD8)'}


def _decision_weights(decision, context):
    """_decision_weights(decision, 'MEB') -> [0.12, 0.12, 0.18, 0.18, 0.15, 0.13, 0.12] | None"""
    record = getattr(decision, _WEIGHTS_FIELD[context])
    return record.get('values') if record else None


def _weights_panel(decision, context):
    record = getattr(decision, _WEIGHTS_FIELD[context])
    if record:
        values, source = record['values'], 'decision'
    else:
        values, _ = get_weights_preset(context)
        source = 'preset'
    return {
        "stage_label": _WEIGHTS_STAGE_LABEL[context],
        "criteria": criteria_labels(context),
        "points": weights_to_points(values),
        "confirmed": bool(record),
        "confirmed_by": record.get('confirmed_by') if record else None,
        "confirmed_at": record.get('confirmed_at', '')[:16].replace('T', ' ') if record else None,
        "justification": record.get('justification') if record else None,
        "source": source,
    }


def _confirm_weights(decision, context):
    """_confirm_weights(decision, 'MEB') com w_0..w_6 = 12,12,18,18,15,13,12 -> True"""
    n = len(criteria_labels(context))
    try:
        points = [float(request.form.get(f'w_{i}', '')) for i in range(n)]
    except ValueError:
        return False
    values = points_to_weights(points, n)
    if values is None:
        return False
    _, preset_id = get_weights_preset(context)
    now = datetime.utcnow().isoformat()
    setattr(decision, _WEIGHTS_FIELD[context], {
        "values": values,
        "points": points,
        "elicitation_method": "direct_100_points",
        "justification": (request.form.get('weights_justification') or '').strip() or None,
        "preset_id": preset_id,
        "confirmed_by": current_user.username,
        "confirmed_at": now,
    })
    history = list(decision.transition_history or [])
    history.append({
        "from": decision.current_stage,
        "to": decision.current_stage,
        "action": f"CONFIRM_WEIGHTS_{context}",
        "timestamp": now,
        "user": current_user.username,
        "weights": values,
    })
    decision.transition_history = history
    return True


# ── Autenticação ──────────────────────────────────────────────────────────────

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email    = request.form.get('email', '').strip() or None

        if not username or not password:
            flash('Username e password são obrigatórios.')
            return redirect(url_for('main.register'))

        if User.query.filter_by(username=username).first():
            flash('Este username já existe.')
            return redirect(url_for('main.register'))

        if PendingRegistration.query.filter_by(username=username, status='pending').first():
            flash('Já existe um pedido pendente para este username.')
            return redirect(url_for('main.register'))

        token = secrets.token_urlsafe(32)
        pending = PendingRegistration(
            username=username,
            password_hash=generate_password_hash(password),
            email=email,
            token=token,
        )
        db.session.add(pending)
        db.session.commit()

        _send_approval_email(username, email, token)

        flash('O seu pedido foi enviado para aprovação. Será notificado quando a conta for ativada.')
        return redirect(url_for('main.login'))

    return render_template('register.html')


def _send_email_async(to, subject, html):
    """Envia email via Resend HTTP API em background thread."""
    app = current_app._get_current_object()
    def _send(app, to, subject, html):
        with app.app_context():
            api_key = app.config.get('RESEND_API_KEY', '')
            if not api_key:
                app.logger.warning("RESEND_API_KEY não configurado, email não enviado.")
                return
            try:
                resend.api_key = api_key
                resend.Emails.send({
                    "from": app.config.get('RESEND_FROM', 'KairoSyn SAD <onboarding@resend.dev>'),
                    "to": [to] if isinstance(to, str) else to,
                    "subject": subject,
                    "html": html,
                })
            except Exception as e:
                app.logger.warning(f"Falha ao enviar email: {e}")
    threading.Thread(target=_send, args=(app, to, subject, html), daemon=True).start()


def _admin_email():
    return current_app.config.get('ADMIN_EMAIL', '')


def _send_approval_email(username, user_email, token):
    admin = _admin_email()
    if not admin:
        return
    base_url    = current_app.config.get('BASE_URL', 'http://127.0.0.1:5000')
    approve_url = f"{base_url}{url_for('main.admin_approve', token=token)}"

    body_html = f"""
    <h2>KairoSyn SAD, Pedido de Registo</h2>
    <p>Um novo utilizador solicitou acesso ao sistema:</p>
    <ul>
        <li><strong>Username:</strong> {username}</li>
        <li><strong>Email:</strong> {user_email or '(não fornecido)'}</li>
    </ul>
    <p>Para aprovar e atribuir a role, clique no link abaixo:</p>
    <p><a href="{approve_url}" style="background:#4f46e5;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">
        Aprovar / Rejeitar Pedido
    </a></p>
    <p style="color:#888;font-size:0.85em;">Este link é de uso único e seguro.</p>
    """
    _send_email_async(admin, f"KairoSyn SAD, Pedido de registo: {username}", body_html)


@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            if user.is_inativado:
                return render_template('login.html', inativado=True, inativado_user_id=user.id)
            login_user(user)
            return redirect(url_for('main.index'))
        flash('Username ou password inválidos.')
    return render_template('login.html')


@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))


@main.route('/reativar/<int:user_id>', methods=['GET', 'POST'])
def reativar(user_id):
    user = User.query.get_or_404(user_id)
    if not user.is_inativado:
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        existing = ReactivationRequest.query.filter_by(user_id=user_id, status='pending').first()
        if existing:
            flash('Já existe um pedido de reativação pendente para esta conta.')
            return redirect(url_for('main.login'))

        message         = request.form.get('message', '').strip()
        contact_channel = request.form.get('contact_channel', '').strip()

        req = ReactivationRequest(
            user_id=user_id,
            message=message or None,
            contact_channel=contact_channel or None,
        )
        db.session.add(req)
        db.session.commit()

        _send_reactivation_email(user, message, contact_channel)

        flash('Pedido de reativação enviado. O administrador irá contactá-lo em breve.')
        return redirect(url_for('main.login'))

    return render_template('reativar.html', user=user)


def _send_registration_approved_email(recipient_email, username):
    admin = _admin_email()
    if not admin:
        return
    email_info = f" ({recipient_email})" if recipient_email and '@' in recipient_email else ""
    body_html = f"""
    <p>A conta do utilizador <strong>{username}</strong>{email_info} foi <strong>aprovada</strong>.</p>
    <p>O utilizador já pode autenticar-se no sistema com as suas credenciais.</p>
    <p style="color:#888;font-size:0.85em;">KairoSyn SAD, confirmação de aprovação</p>
    """
    _send_email_async(admin, f"KairoSyn SAD, Conta aprovada: {username}", body_html)


def _send_approval_reactivation_email(recipient_email, username):
    admin = _admin_email()
    if not admin:
        return
    email_info = f" ({recipient_email})" if recipient_email and '@' in recipient_email else ""
    body_html = f"""
    <p>A conta do utilizador <strong>{username}</strong>{email_info} foi <strong>reativada</strong>.</p>
    <p>O utilizador já pode aceder ao sistema.</p>
    <p style="color:#888;font-size:0.85em;">KairoSyn SAD, confirmação de reativação</p>
    """
    _send_email_async(admin, f"KairoSyn SAD, Conta reativada: {username}", body_html)


def _send_rejection_email(recipient_email, username):
    admin = _admin_email()
    if not admin:
        return
    email_info = f" ({recipient_email})" if recipient_email and '@' in recipient_email else ""
    body_html = f"""
    <p>O pedido de acesso do utilizador <strong>{username}</strong>{email_info} foi <strong>rejeitado</strong>.</p>
    <p style="color:#888;font-size:0.85em;">KairoSyn SAD, confirmação de rejeição</p>
    """
    _send_email_async(admin, f"KairoSyn SAD, Pedido rejeitado: {username}", body_html)


def _send_reactivation_email(user, message, contact_channel):
    admin = _admin_email()
    if not admin:
        return
    base_url  = current_app.config.get('BASE_URL', 'http://127.0.0.1:5000')
    gerir_url = f"{base_url}{url_for('main.gerirusers')}"

    body_html = f"""
    <h2>KairoSyn SAD, Pedido de Reativação de Conta</h2>
    <p>O utilizador abaixo solicitou a reativação da sua conta inativada:</p>
    <ul>
        <li><strong>Username:</strong> {user.username}</li>
        <li><strong>Email:</strong> {user.email or '(não fornecido)'}</li>
        <li><strong>Canal de contacto:</strong> {contact_channel or '(não fornecido)'}</li>
    </ul>
    {'<p><strong>Mensagem:</strong> ' + message + '</p>' if message else ''}
    <p>Para reativar, aceda ao painel de administração:</p>
    <p><a href="{gerir_url}" style="background:#4f46e5;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">
        Gerir Utilizadores
    </a></p>
    """
    _send_email_async(admin, f"KairoSyn SAD, Pedido de reativação: {user.username}", body_html)


# ── Admin, aprovação de registos ─────────────────────────────────────────────

@main.route('/admin/approve/<token>', methods=['GET', 'POST'])
def admin_approve(token):
    pending = PendingRegistration.query.filter_by(token=token).first_or_404()

    if pending.status != 'pending':
        return render_template('admin_approve.html', pending=pending, already_processed=True)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'reject':
            pending.status = 'rejected'
            db.session.commit()
            _send_rejection_email(pending.email, pending.username)
            flash(f'Pedido de "{pending.username}" rejeitado.')
            return redirect(url_for('main.gerirusers'))

        role = request.form.get('role', 'user')
        if role not in ('user', 'admin'):
            role = 'user'

        new_user = User(
            username=pending.username,
            password=pending.password_hash,
            email=pending.email,
            role=role,
        )
        db.session.add(new_user)
        pending.status = 'approved'
        db.session.commit()

        _send_registration_approved_email(pending.email, pending.username)
        flash(f'Utilizador "{pending.username}" aprovado com role "{role}".')
        return redirect(url_for('main.gerirusers'))

    return render_template('admin_approve.html', pending=pending)


@main.route('/gerirusers', methods=['GET', 'POST'])
@login_required
@admin_required
def gerirusers():
    if request.method == 'POST':
        action  = request.form.get('action')

        if action == 'add_user':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            email    = request.form.get('email', '').strip() or None
            role     = request.form.get('role', 'user')
            if role not in ('user', 'admin', 'inativado'):
                role = 'user'
            if not username or not password:
                flash('Username e password são obrigatórios.')
            elif User.query.filter_by(username=username).first():
                flash(f'O username "{username}" já existe.')
            else:
                new_user = User(
                    username=username,
                    password=generate_password_hash(password),
                    email=email,
                    role=role,
                )
                db.session.add(new_user)
                db.session.commit()
                flash(f'Utilizador "{username}" criado com role "{role}".')
            return redirect(url_for('main.gerirusers'))

        user_id = request.form.get('user_id', type=int)
        target  = User.query.get_or_404(user_id)

        if action == 'change_role':
            new_role = request.form.get('role', 'user')
            if new_role not in ('user', 'admin', 'inativado'):
                new_role = 'user'
            if target.id == current_user.id and new_role != 'admin':
                flash('Não pode alterar a sua própria role de admin.')
            else:
                target.role = new_role
                db.session.commit()
                flash(f'Role de "{target.username}" alterada para "{new_role}".')

        elif action == 'approve_reactivation':
            req_id = request.form.get('req_id', type=int)
            req = ReactivationRequest.query.get_or_404(req_id)
            req.user.role = 'user'
            req.status = 'approved'
            db.session.commit()
            _send_approval_reactivation_email(req.contact_channel, req.user.username)
            flash(f'Conta de "{req.user.username}" reativada com sucesso.')

        elif action == 'reject_reactivation':
            req_id = request.form.get('req_id', type=int)
            req = ReactivationRequest.query.get_or_404(req_id)
            req.status = 'rejected'
            db.session.commit()
            # Enviar email ao canal de contacto se for um endereço de email válido
            _send_rejection_email(req.contact_channel, req.user.username)
            flash(f'Pedido de reativação de "{req.user.username}" rejeitado.')

        elif action == 'delete':
            if target.id == current_user.id:
                flash('Não pode eliminar a sua própria conta.')
            else:
                db.session.delete(target)
                db.session.commit()
                flash(f'Utilizador "{target.username}" eliminado.')

        return redirect(url_for('main.gerirusers'))

    users               = User.query.order_by(User.id).all()
    pending_list        = PendingRegistration.query.order_by(PendingRegistration.created_at.desc()).all()
    reactivation_list   = ReactivationRequest.query.order_by(ReactivationRequest.created_at.desc()).all()
    return render_template('gerirusers.html', users=users, pending_list=pending_list, reactivation_list=reactivation_list)


# ── Dashboard / Início ────────────────────────────────────────────────────────

@main.route("/")
@login_required
def index():
    stats = {
        "projetos":    Projeto.query.filter_by(is_active=True).count(),
        "diagnosticos": ProjectDecision.query.filter_by(user_id=current_user.id).count(),
        "concluidos":  ProjectDecision.query.filter_by(user_id=current_user.id, current_stage='stage_complete').count(),
        "metodologias": MethodologyEvidenceBase.query.count(),
    }
    last_decision = (ProjectDecision.query
                     .filter_by(user_id=current_user.id)
                     .order_by(ProjectDecision.created_at.desc())
                     .first())
    return render_template("index.html", stats=stats, last_decision=last_decision)


# ── Gestão de Projetos ────────────────────────────────────────────────────────

@main.route("/gestaoprojetos")
@login_required
def listaprojetos():
    projetos = Projeto.query.filter_by(is_active=True).order_by(Projeto.created_date.desc()).all()

    latest_decisions = {}
    decision_counts = {}
    for p in projetos:
        d = ProjectDecision.query.filter_by(projeto_id=p.id).order_by(ProjectDecision.created_at.desc()).first()
        if d:
            latest_decisions[p.id] = d
        version_ids = [v.id for v in Projeto.query.filter_by(projeto_uuid=p.projeto_uuid).all()]
        decision_counts[p.id] = ProjectDecision.query.filter(ProjectDecision.projeto_id.in_(version_ids)).count()

    return render_template('gestaoprojetos.html', projetos=projetos,
                           latest_decisions=latest_decisions, decision_counts=decision_counts)


def _parse_team_and_deliverables(form):
    roles = form.getlist('team_role[]')
    qtys  = form.getlist('team_qty[]')
    equipa_json = [
        {"role": r.strip(), "qty": int(q or 1)}
        for r, q in zip(roles, qtys) if r.strip()
    ]
    phases = form.getlist('deliv_phase[]')
    texts  = form.getlist('deliv_text[]')
    entregaveis_dict = {}
    for ph, tx in zip(phases, texts):
        if tx.strip():
            entregaveis_dict.setdefault(ph, []).append(tx.strip())
    return (
        json.dumps(equipa_json, ensure_ascii=False),
        json.dumps(entregaveis_dict, ensure_ascii=False),
    )


def _projeto_form_context(projeto=None):
    users = User.query.filter(User.role != 'inativado').order_by(User.username).all()
    equipa = []
    entregaveis = {}
    if projeto:
        try:
            equipa = json.loads(projeto.equipa_projeto or '[]')
        except (ValueError, TypeError):
            raw = projeto.equipa_projeto or ''
            equipa = [{"role": r.strip(), "qty": 1} for r in raw.split(',') if r.strip()]
        try:
            entregaveis = json.loads(projeto.entregaveis or '{}')
        except (ValueError, TypeError):
            if projeto.entregaveis:
                entregaveis = {"Execução": [projeto.entregaveis]}
    return {"users": users, "equipa_parsed": equipa, "entregaveis_parsed": entregaveis}


@main.route('/projeto/novo', methods=['GET', 'POST'])
@login_required
def criar_projeto():
    if request.method == 'POST':
        try:
            data_ini_str = request.form.get('data_inicio')
            data_fim_str = request.form.get('data_fim')
            if not data_ini_str or not data_fim_str:
                flash('Erro: Datas de início e fim são obrigatórias.', 'danger')
                return render_template('form_projeto.html', projeto=None, titulo="Criar Novo Projeto",
                                       **_projeto_form_context())

            equipa_json, entregaveis_json = _parse_team_and_deliverables(request.form)
            novo_projeto = Projeto(
                projeto_uuid=__import__('uuid').uuid4().__str__(),
                nome=request.form['nome'],
                gestor_projeto=request.form['gestor'],
                equipa_projeto=equipa_json,
                objetivo=request.form['objetivo'],
                entregaveis=entregaveis_json,
                orcamento=float(request.form['orcamento'] or 0),
                fase_atual=request.form['fase'],
                status=request.form['status'],
                is_active=True,
                data_inicio=datetime.strptime(data_ini_str, '%Y-%m-%d').date(),
                data_fim=datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            )
            db.session.add(novo_projeto)
            db.session.commit()
            flash('Projeto criado com sucesso!', 'success')
            return redirect(url_for('main.listaprojetos'))
        except ValueError as e:
            flash(f'Erro no formato dos dados: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro inesperado: {str(e)}', 'danger')
    return render_template('form_projeto.html', projeto=None, titulo="Criar Novo Projeto",
                           **_projeto_form_context())


@main.route('/projeto/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_projeto(id):
    projeto_atual = Projeto.query.get_or_404(id)
    if request.method == 'POST':
        try:
            data_ini_str = request.form.get('data_inicio')
            data_fim_str = request.form.get('data_fim')
            if not data_ini_str or not data_fim_str:
                flash('Erro: As datas são obrigatórias.', 'danger')
                return render_template('form_projeto.html', projeto=projeto_atual, titulo="Editar Projeto",
                                       **_projeto_form_context(projeto_atual))

            equipa_json, entregaveis_json = _parse_team_and_deliverables(request.form)
            projeto_atual.is_active = False
            projeto_atual.inactive_date = datetime.utcnow()

            nova_versao = Projeto(
                projeto_uuid=projeto_atual.projeto_uuid,
                nome=request.form['nome'],
                gestor_projeto=request.form['gestor'],
                equipa_projeto=equipa_json,
                objetivo=request.form['objetivo'],
                entregaveis=entregaveis_json,
                orcamento=float(request.form['orcamento'] or 0),
                fase_atual=request.form['fase'],
                status=request.form['status'],
                is_active=True,
                data_inicio=datetime.strptime(data_ini_str, '%Y-%m-%d').date(),
                data_fim=datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            )
            db.session.add(nova_versao)
            db.session.commit()
            flash('Nova versão do projeto gravada com sucesso.', 'success')
            return redirect(url_for('main.listaprojetos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'danger')
    return render_template('form_projeto.html', projeto=projeto_atual, titulo="Editar Projeto",
                           **_projeto_form_context(projeto_atual))


@main.route("/projeto/<string:projeto_uuid>/historicoprojeto")
@login_required
def historico_projeto(projeto_uuid):
    versoes = Projeto.query.filter_by(projeto_uuid=projeto_uuid).order_by(Projeto.created_date.desc()).all()
    if not versoes:
        flash("Projeto não encontrado.", "danger")
        return redirect(url_for("main.listaprojetos"))
    return render_template("historicoprojeto.html", versoes=versoes, nome_projeto=versoes[0].nome)


# ── Diagnóstico (Etapa 1) ─────────────────────────────────────────────────────

@main.route("/diagnostico", methods=["GET", "POST"])
@login_required
def diagnostico():
    if request.method == "POST":
        context_data = {
            'complexity':            int(request.form.get('complexity', 2)),
            'novelty':               int(request.form.get('novelty', 2)),
            'dynamism':              int(request.form.get('dynamism', 2)),
            'team_autonomy':         int(request.form.get('team_autonomy', 2)),
            'criticality':           int(request.form.get('criticality', 2)),
            'compliance':            int(request.form.get('compliance', 2)),
            'traceability':          int(request.form.get('traceability', 2)),
            'stakeholder_formality': int(request.form.get('stakeholder_formality', 2)),
        }

        evidence_notes = {
            dim: request.form.get(f'note_{dim}', '').strip()
            for dim in context_data
        }

        projeto_id_raw = request.form.get('projeto_id')
        projeto_id = int(projeto_id_raw) if projeto_id_raw else None

        new_decision = ProjectDecision(
            project_name=request.form.get('project_name', 'Sem nome').strip() or 'Sem nome',
            user_id=current_user.id,
            projeto_id=projeto_id,
            context_data=context_data,
            evidence_notes={k: v for k, v in evidence_notes.items() if v},
            questionnaire_version='v2',
            current_stage='stage_2_approach',
            transition_history=[{
                "from": "stage_1_diagnosis",
                "to": "stage_2_approach",
                "action": "SUBMIT_DIAGNOSIS",
                "timestamp": datetime.utcnow().isoformat(),
                "user": current_user.username
            }]
        )
        db.session.add(new_decision)
        db.session.commit()
        return redirect(url_for('main.etapa2', id=new_decision.id))

    projetos = Projeto.query.filter_by(is_active=True).order_by(Projeto.nome).all()
    projeto_id_prefill = request.args.get('projeto_id', type=int)
    projeto_prefill = Projeto.query.get(projeto_id_prefill) if projeto_id_prefill else None
    from_decision_id = request.args.get('from_decision_id', type=int)
    prev_decision = ProjectDecision.query.get(from_decision_id) if from_decision_id else None
    return render_template("diagnostico.html", projetos=projetos,
                           projeto_id_prefill=projeto_id_prefill, projeto_prefill=projeto_prefill,
                           prev_decision=prev_decision)


# ── Etapa 2, Abordagem ───────────────────────────────────────────────────────

@main.route("/etapa2/<int:id>", methods=["GET", "POST"])
@login_required
def etapa2(id):
    decision = ProjectDecision.query.get_or_404(id)

    if decision.agpi_score is None or decision.aspi_score is None:
        agpi, aspi = compute_indices(decision.context_data or {})
        decision.agpi_score = agpi
        decision.aspi_score = aspi
        decision.suggested_approach = resolve_approach(agpi, aspi)
        db.session.commit()

    if request.method == "POST":
        confirmed_approach = request.form.get('confirmed_approach', decision.suggested_approach)
        context = decision.context_data or {}
        decision_control_register = build_decision_control_register(confirmed_approach, context, decision.agpi_score, decision.aspi_score)

        context['confirmed_approach'] = confirmed_approach
        decision.context_data = context
        decision.suggested_approach = confirmed_approach
        decision.decision_control_register = decision_control_register

        engine_choice = request.form.get('mcdm_engine', decision.mcdm_engine or 'MAVT')
        decision.mcdm_engine = engine_choice if engine_choice in ('MAVT', 'AHP') else 'MAVT'

        action = request.form.get('action', 'CONFIRM_APPROACH')
        previous = decision.current_stage

        decision.reentry_cause = None
        _log_transition(decision, previous, 'stage_3_fit_m', 'CONFIRM_APPROACH')
        db.session.commit()
        return redirect(url_for('main.etapa3', id=id))

    return render_template("etapa2.html", decision=decision)


# ── Etapa 3, Fit_M ───────────────────────────────────────────────────────────

@main.route("/etapa3/<int:id>", methods=["GET", "POST"])
@login_required
def etapa3(id):
    decision = ProjectDecision.query.get_or_404(id)

    decision_control_register = decision.decision_control_register or {"binding_constraints": [], "acceptance_thresholds": [], "advisory_guidelines": []}
    agpi = decision.agpi_score or 2.0
    aspi = decision.aspi_score or 2.0
    approach = decision.suggested_approach or 'Híbrida'

    if request.method == "POST":
        selected_id = request.form.get('selected_methodology_id')
        action = request.form.get('action', 'CONFIRM_METHODOLOGY')
        previous = decision.current_stage

        if action in ('REENTRY_GOVERNANCE', 'REVISE_APPROACH'):
            decision.reentry_cause = 'governance_infeasibility'
            _log_transition(decision, previous, 'stage_2_approach', action, cause='governance_infeasibility')
            db.session.commit()
            return redirect(url_for('main.etapa2', id=id))

        if action == 'CONFIRM_WEIGHTS':
            if _confirm_weights(decision, 'MEB'):
                db.session.commit()
                flash("Pesos C1-C7 confirmados para esta decisão.", "success")
            else:
                flash("Pesos inválidos: use valores não negativos com soma superior a 0.", "warning")
            return redirect(url_for('main.etapa3', id=id))

        if selected_id and not decision.meb_weights:
            flash("Confirme os pesos C1-C7 antes de selecionar a metodologia.", "warning")
            return redirect(url_for('main.etapa3', id=id))

        if selected_id:
            meth = MethodologyEvidenceBase.query.get(int(selected_id))
            decision.selected_methodology_id = meth.id
            decision.selected_methodology = meth.name

            admissible_components, _comp_exclusions = get_envelope_component_candidates(
                meth, decision_control_register, agpi, aspi, approach)
            admissible_ids = {c.id for c in admissible_components}
            by_comp_id = {c.id: c for c in admissible_components}

            components = []
            dropped = 0
            inadmissible = 0
            for cid in request.form.getlist('component_ids'):
                cid = int(cid)
                if cid not in admissible_ids:
                    inadmissible += 1
                    continue
                comp = by_comp_id[cid]
                justification = (request.form.get(f'component_justification_{cid}') or '').strip()
                if not justification:
                    dropped += 1
                    continue
                components.append({
                    "id": comp.id, "code": comp.code, "name": comp.name,
                    "role": comp.candidate_role, "justification": justification,
                })
            decision.methodological_envelope = {
                "primary": {"id": meth.id, "code": meth.code, "name": meth.name},
                "components": components,
            }
            if dropped:
                flash(f"{dropped} componente(s) do envelope ignorado(s) por falta de justificação.", "warning")
            if inadmissible:
                flash(f"{inadmissible} componente(s) ignorado(s): deixaram de ser admissíveis face às restrições do decision-control register.", "warning")

            decision.reentry_cause = None
            _log_transition(decision, previous, 'stage_4_fit_t', 'CONFIRM_METHODOLOGY')
            db.session.commit()
            return redirect(url_for('main.etapa4', id=id))

        flash("Selecione uma metodologia antes de continuar.", "warning")

    viable, meb_exclusions = run_fit_m_level1(decision_control_register, agpi, aspi, approach=approach)

    if not viable:
        decision.reentry_cause = 'no_feasible_methodology_after_level1'
        decision.meb_exclusions = meb_exclusions
        decision.meb_filtered = []
        decision.methodology_ranking = []
        _log_transition(decision, decision.current_stage, 'stage_2_approach', 'REENTRY_GOVERNANCE', cause='no_feasible_methodology_after_level1')
        db.session.commit()
        flash("Nenhuma metodologia viável encontrada. Reveja a abordagem.", "warning")
        return redirect(url_for('main.etapa2', id=id))

    decision.meb_exclusions = meb_exclusions
    decision.meb_filtered = [m.id for m, _ in viable]
    ranking = []
    meb_weights = _decision_weights(decision, 'MEB')
    if meb_weights:
        ranking = run_fit_m_level2(viable, decision.mcdm_engine or 'MAVT', weights=meb_weights)
        decision.methodology_ranking = ranking
    db.session.commit()

    meb_total = MethodologyEvidenceBase.query.count()

    cause_counts = {}
    for e in meb_exclusions:
        cause_counts[e["cause"]] = cause_counts.get(e["cause"], 0) + 1

    sankey_nodes = [{"name": f"MEB Total ({meb_total})"}]
    sankey_links = []
    for cause, count in cause_counts.items():
        sankey_nodes.append({"name": f"{cause.replace('_', ' ').capitalize()} ({count})"})
        sankey_links.append({"source": 0, "target": len(sankey_nodes) - 1, "value": count})

    sankey_nodes.append({"name": f"Ranking MCDM ({len(viable)})"})
    sankey_links.append({"source": 0, "target": len(sankey_nodes) - 1, "value": max(len(viable), 1)})

    sankey_data = {"nodes": sankey_nodes, "links": sankey_links}

    by_id = {m.id: m for m, _ in viable}
    envelope_options = {}
    for item in ranking:
        eligible, comp_exclusions = get_envelope_component_candidates(
            by_id.get(item["id"]), decision_control_register, agpi, aspi, approach)
        envelope_options[str(item["id"])] = {
            "eligible": [
                {"id": c.id, "code": c.code, "name": c.name, "role": c.candidate_role}
                for c in eligible
            ],
            "excluded": comp_exclusions,
        }

    return render_template("etapa3.html", decision=decision, ranking=ranking,
                           meb_total=meb_total, viable_count=len(viable),
                           meb_exclusions=meb_exclusions,
                           envelope_options=envelope_options,
                           sankey_data=json.dumps(sankey_data),
                           wp=_weights_panel(decision, 'MEB'))


# ── Etapa 4, Fit_T ───────────────────────────────────────────────────────────

@main.route("/etapa4/<int:id>", methods=["GET", "POST"])
@login_required
def etapa4(id):
    decision = ProjectDecision.query.get_or_404(id)

    selected_meth = None
    if decision.selected_methodology_id:
        selected_meth = MethodologyEvidenceBase.query.get(decision.selected_methodology_id)

    if not selected_meth:
        flash("Selecione uma metodologia na Etapa 3 antes de continuar.", "warning")
        return redirect(url_for('main.etapa3', id=id))

    decision_control_register = decision.decision_control_register or {"binding_constraints": [], "acceptance_thresholds": [], "advisory_guidelines": []}

    envelope_codes = [selected_meth.code] + [
        c["code"] for c in (decision.methodological_envelope or {}).get("components", [])
    ]

    if request.method == "POST":
        action = request.form.get('action', 'CONFIRM_TOOLS')
        previous = decision.current_stage

        if action == 'REENTRY_APPROACH':
            decision.reentry_cause = 'governance_threshold'
            _log_transition(decision, previous, 'stage_2_approach', action, cause='governance_threshold')
            db.session.commit()
            return redirect(url_for('main.etapa2', id=id))

        if action in ('REENTRY_METHODOLOGY', 'REVISE_METHODOLOGY'):
            decision.reentry_cause = 'tool_infeasibility'
            _log_transition(decision, previous, 'stage_3_fit_m', action, cause='tool_infeasibility')
            db.session.commit()
            return redirect(url_for('main.etapa3', id=id))

        if action == 'CONFIRM_WEIGHTS':
            if _confirm_weights(decision, 'TEB'):
                db.session.commit()
                flash("Pesos CD1-CD8 confirmados para esta decisão.", "success")
            else:
                flash("Pesos inválidos: use valores não negativos com soma superior a 0.", "warning")
            return redirect(url_for('main.etapa4', id=id))

        teb_weights = _decision_weights(decision, 'TEB')
        if not teb_weights:
            flash("Confirme os pesos CD1-CD8 antes de concluir.", "warning")
            return redirect(url_for('main.etapa4', id=id))

        viable_tools, teb_exclusions = run_fit_t_level_a(selected_meth, decision_control_register, envelope_codes)
        decision.teb_exclusions = teb_exclusions
        decision.capability_map = build_capability_map(viable_tools)
        ranked_by_category = run_fit_t_level_b(viable_tools, decision.mcdm_engine or 'MAVT', weights=teb_weights)
        portfolio = []
        seen_codes = set()
        for cat, tools in ranked_by_category.items():
            chosen_code = request.form.get(f'sel_{cat}')
            selected = next((t for t in tools if t['code'] == chosen_code), tools[0] if tools else None)
            if selected and selected['code'] not in seen_codes:
                portfolio.append(selected)
                seen_codes.add(selected['code'])

        decision.tool_portfolio = portfolio
        decision.teb_filtered = [t.id for t in viable_tools]
        decision.reentry_cause = None
        _log_transition(decision, previous, 'stage_complete', 'CONFIRM_TOOLS')
        db.session.commit()
        flash("Diagnóstico KairoSyn concluído com sucesso!", "success")
        return redirect(url_for('main.workflow', id=id))

    viable_tools, teb_exclusions = run_fit_t_level_a(selected_meth, decision_control_register, envelope_codes)
    decision.teb_exclusions = teb_exclusions
    capability_map = build_capability_map(viable_tools)
    decision.capability_map = capability_map

    if not viable_tools:
        decision.reentry_cause = 'tool_infeasibility'
        _log_transition(decision, decision.current_stage, 'stage_3_fit_m', 'REENTRY_METHODOLOGY', cause='tool_infeasibility')
        db.session.commit()
        flash("Nenhuma ferramenta compatível encontrada. Reveja a metodologia.", "warning")
        return redirect(url_for('main.etapa3', id=id))

    ranked_by_category = {}
    teb_weights = _decision_weights(decision, 'TEB')
    if teb_weights:
        ranked_by_category = run_fit_t_level_b(viable_tools, decision.mcdm_engine or 'MAVT', weights=teb_weights)
    decision.teb_filtered = [t.id for t in viable_tools]
    db.session.commit()

    return render_template("etapa4.html", decision=decision,
                           ranked_by_category=ranked_by_category,
                           selected_meth=selected_meth,
                           teb_exclusions=teb_exclusions,
                           capability_map=capability_map,
                           viable_count=len(viable_tools),
                           wp=_weights_panel(decision, 'TEB'))


# ── Reassessment pós-conclusão (nova execução clonada) ───────────────────────

_REASSESS_TARGETS = {
    'stage_2_approach': {
        'action': 'REASSESSMENT_APPROACH',
        'cause': 'organiser_drift_or_decision_control_reconfiguration',
        'redirect': 'main.etapa2',
    },
    'stage_3_fit_m': {
        'action': 'REASSESSMENT_METHODOLOGY',
        'cause': 'evidence_update_or_configuration_infeasibility',
        'redirect': 'main.etapa3',
    },
}


@main.route("/decision/<int:id>/reassess", methods=["POST"])
@login_required
def reassess_decision(id):
    origin = ProjectDecision.query.get_or_404(id)
    target = request.form.get('target')

    if origin.current_stage != 'stage_complete':
        flash("Reassessment só está disponível para decisões concluídas.", "warning")
        return redirect(url_for('main.workflow', id=id))
    if target not in _REASSESS_TARGETS:
        flash("Destino de reassessment inválido.", "warning")
        return redirect(url_for('main.workflow', id=id))

    spec = _REASSESS_TARGETS[target]
    justification = request.form.get('justification', '').strip()
    now = datetime.utcnow().isoformat()

    new_decision = ProjectDecision(
        project_name=origin.project_name,
        user_id=current_user.id,
        projeto_id=origin.projeto_id,
        questionnaire_version=origin.questionnaire_version,
        mcdm_engine=origin.mcdm_engine,
        context_data=dict(origin.context_data or {}),
        evidence_notes=dict(origin.evidence_notes or {}),
        current_stage=target,
        reentry_cause=spec['cause'],
        transition_history=[{
            "from": "stage_complete",
            "to": target,
            "action": spec['action'],
            "timestamp": now,
            "user": current_user.username,
            "reentry_cause": spec['cause'],
            "source_decision_id": origin.id,
            "justification": justification or None,
        }],
    )

    if target == 'stage_3_fit_m':
        new_decision.agpi_score = origin.agpi_score
        new_decision.aspi_score = origin.aspi_score
        new_decision.suggested_approach = origin.suggested_approach
        new_decision.decision_control_register = dict(origin.decision_control_register or {})

    db.session.add(new_decision)
    db.session.flush()

    origin_history = list(origin.transition_history or [])
    origin_history.append({
        "from": "stage_complete",
        "to": target,
        "action": spec['action'],
        "timestamp": now,
        "user": current_user.username,
        "reentry_cause": spec['cause'],
        "spawned_decision_id": new_decision.id,
        "justification": justification or None,
    })
    origin.transition_history = origin_history

    db.session.commit()
    flash(f"Nova execução #{new_decision.id} criada a partir da decisão concluída #{origin.id}.", "success")
    return redirect(url_for(spec['redirect'], id=new_decision.id))


# ── Workflow / Estado atual ───────────────────────────────────────────────────

@main.route("/workflow/<int:id>")
@login_required
def workflow(id):
    decision = ProjectDecision.query.get_or_404(id)
    projeto = Projeto.query.get(decision.projeto_id) if decision.projeto_id else None

    sensitivity = None
    if decision.methodology_ranking and decision.agpi_score and decision.aspi_score:
        try:
            sensitivity = run_sensitivity_analysis(
                decision.methodology_ranking,
                weights=_decision_weights(decision, 'MEB'),
            )
        except Exception:
            pass

    return render_template("workflow.html", decision=decision, projeto=projeto,
                           sensitivity=sensitivity)


@main.route('/projeto/<string:projeto_uuid>/diagnosticos')
@login_required
def projeto_diagnosticos(projeto_uuid):
    all_versions = Projeto.query.filter_by(projeto_uuid=projeto_uuid).all()
    if not all_versions:
        abort(404)
    projeto = next((v for v in all_versions if v.is_active), all_versions[0])
    version_ids = [v.id for v in all_versions]
    decisions = (ProjectDecision.query
                 .filter(ProjectDecision.projeto_id.in_(version_ids))
                 .order_by(ProjectDecision.created_at.desc())
                 .all())
    return render_template('projeto_diagnosticos.html', projeto=projeto, decisions=decisions)


@main.route("/update-state/<int:id>/<string:action>", methods=["POST"])
@login_required
def update_state(id, action):
    decision = ProjectDecision.query.get_or_404(id)
    previous = decision.current_stage
    new_state = TRANSITIONS.get((previous, action), previous)

    if new_state != previous:
        _log_transition(decision, previous, new_state, action)
        db.session.commit()

    redirect_view = STAGE_REDIRECT.get(new_state, 'main.workflow')
    if redirect_view == 'main.diagnostico':
        params = {'from_decision_id': id}
        if decision.projeto_id:
            params['projeto_id'] = decision.projeto_id
        return redirect(url_for(redirect_view, **params))
    return redirect(url_for(redirect_view, id=id))


# ── Decision Log ──────────────────────────────────────────────────────────────

@main.route("/historico")
@login_required
def historico():
    decisions = (ProjectDecision.query
                 .filter_by(user_id=current_user.id)
                 .order_by(ProjectDecision.created_at.desc())
                 .all())
    return render_template("historico.html", decisions=decisions)


@main.route("/decision/<int:id>/export")
@login_required
def export_decision(id):
    decision = ProjectDecision.query.get_or_404(id)
    fmt = request.args.get('format', 'json')

    sensitivity = None
    if decision.methodology_ranking and decision.agpi_score and decision.aspi_score:
        try:
            sensitivity = run_sensitivity_analysis(
                decision.methodology_ranking,
                weights=_decision_weights(decision, 'MEB'),
            )
        except Exception:
            pass

    payload = {
        "id": decision.id,
        "projeto_id": decision.projeto_id,
        "project_name": decision.project_name,
        "created_at": decision.created_at.isoformat() if decision.created_at else None,
        "questionnaire_version": decision.questionnaire_version,
        "current_stage": decision.current_stage,
        "reentry_cause": decision.reentry_cause,
        # Stage 1
        "adpo_score": decision.agpi_score,
        "aspo_score": decision.aspi_score,
        "context_data": decision.context_data,
        "evidence_notes": decision.evidence_notes,
        # Stage 2
        "suggested_approach": decision.suggested_approach,
        "decision_control_register": decision.decision_control_register,
        # Etapa 3
        "meb_filtered": decision.meb_filtered,
        "meb_exclusions": decision.meb_exclusions,
        "meb_weights": decision.meb_weights,
        "stage3_output": decision.stage3_output,
        "methodology_ranking": decision.methodology_ranking,
        "selected_methodology": decision.selected_methodology,
        "methodological_envelope": decision.methodological_envelope,
        "mcdm_engine": decision.mcdm_engine,
        "sensitivity_analysis": sensitivity,
        # Etapa 4
        "teb_filtered": decision.teb_filtered,
        "teb_exclusions": decision.teb_exclusions,
        "teb_weights": decision.teb_weights,
        "capability_map": decision.capability_map,
        "tool_portfolio": decision.tool_portfolio,
        # Auditoria
        "transition_history": decision.transition_history,
    }

    if fmt == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        flat_fields = ["id", "projeto_id", "project_name", "created_at", "questionnaire_version",
                       "current_stage", "reentry_cause",
                       "adpo_score", "aspo_score",
                       "suggested_approach", "selected_methodology", "mcdm_engine"]
        json_fields = ["context_data", "evidence_notes", "decision_control_register",
                       "meb_filtered", "meb_exclusions", "meb_weights", "stage3_output", "methodology_ranking",
                       "methodological_envelope", "sensitivity_analysis",
                       "teb_filtered", "teb_exclusions", "teb_weights", "capability_map", "tool_portfolio", "transition_history"]
        headers = flat_fields + json_fields
        values = [payload.get(f, "") for f in flat_fields] + [
            json.dumps(payload[f], ensure_ascii=False) if payload[f] is not None else ""
            for f in json_fields
        ]
        writer.writerow(headers)
        writer.writerow(values)

        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=decision_{id}.csv'
        return response

    response = make_response(json.dumps(payload, indent=2, ensure_ascii=False))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=decision_{id}.json'
    return response


@main.route("/decision/<int:id>/export/pdf")
@login_required
def export_decision_pdf(id):
    from weasyprint import HTML
    decision = ProjectDecision.query.get_or_404(id)
    sensitivity = None
    if decision.methodology_ranking and decision.agpi_score and decision.aspi_score:
        try:
            sensitivity = run_sensitivity_analysis(
                decision.methodology_ranking,
                weights=_decision_weights(decision, 'MEB'),
            )
        except Exception:
            pass
    html_string = render_template("pdf_report.html", decision=decision, now=datetime.utcnow(),
                                  sensitivity=sensitivity)
    pdf_bytes = HTML(string=html_string, base_url=request.host_url).write_pdf()
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=kairosy_decision_{id}.pdf'
    return response


# ── Admin, MCDM Engine ───────────────────────────────────────────────────────

@main.route('/admin/gerir-mcdm', methods=['GET', 'POST'])
@login_required
@admin_required
def gerir_mcdm():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'toggle_meb':
            meb = MethodologyEvidenceBase.query.get_or_404(request.form.get('meb_id', type=int))
            meb.is_active = not meb.is_active
            meb.inactive_date = None if meb.is_active else datetime.utcnow()
            db.session.commit()
            estado = 'ativada' if meb.is_active else 'inativada'
            flash(f'Metodologia "{meb.name}" {estado}.')

        elif action == 'toggle_teb':
            teb = ToolEvidenceBase.query.get_or_404(request.form.get('teb_id', type=int))
            teb.is_active = not teb.is_active
            teb.inactive_date = None if teb.is_active else datetime.utcnow()
            db.session.commit()
            estado = 'ativada' if teb.is_active else 'inativada'
            flash(f'Ferramenta "{teb.name}" {estado}.')

        elif action == 'update_pesos':
            context = request.form.get('context')
            current = MCDMWeights.query.filter_by(context=context, is_active=True).first()
            if not current:
                flash('Contexto de pesos inválido.')
                return redirect(url_for('main.gerir_mcdm'))
            try:
                new_weights = [float(request.form.get(f'w_{i}', 0)) for i in range(len(current.weights))]
                total = round(sum(new_weights), 6)
                if abs(total - 1.0) > 0.01:
                    flash(f'A soma dos pesos {context} deve ser 1.0 (atual: {total:.4f}).')
                    return redirect(url_for('main.gerir_mcdm') + '#tab-pesos')
                now = datetime.utcnow()
                current.is_active = False
                current.inactive_date = now
                db.session.add(MCDMWeights(
                    context=context,
                    weights=new_weights,
                    labels=current.labels,
                    is_active=True,
                    active_date=now,
                    updated_at=now,
                    updated_by=current_user.username,
                ))
                db.session.commit()
                flash(f'Pesos {context} atualizados. Versão anterior arquivada.')
            except (ValueError, TypeError):
                flash('Valores inválidos nos pesos.')

        return redirect(url_for('main.gerir_mcdm'))

    show_inactive = request.args.get('inativos') == '1'
    if show_inactive:
        mebs = MethodologyEvidenceBase.query.order_by(
            MethodologyEvidenceBase.is_active.desc(), MethodologyEvidenceBase.tier, MethodologyEvidenceBase.code
        ).all()
        tebs = ToolEvidenceBase.query.order_by(
            ToolEvidenceBase.is_active.desc(), ToolEvidenceBase.code
        ).all()
    else:
        mebs = MethodologyEvidenceBase.query.filter_by(is_active=True).order_by(
            MethodologyEvidenceBase.tier, MethodologyEvidenceBase.code
        ).all()
        tebs = ToolEvidenceBase.query.filter_by(is_active=True).order_by(
            ToolEvidenceBase.code
        ).all()

    meb_weights = MCDMWeights.query.filter_by(context='MEB', is_active=True).first()
    teb_weights = MCDMWeights.query.filter_by(context='TEB', is_active=True).first()
    meb_versions_count = MCDMWeights.query.filter_by(context='MEB').count()
    teb_versions_count = MCDMWeights.query.filter_by(context='TEB').count()
    return render_template('gerir_mcdm.html', mebs=mebs, tebs=tebs,
                           meb_weights=meb_weights, teb_weights=teb_weights,
                           meb_versions_count=meb_versions_count,
                           teb_versions_count=teb_versions_count,
                           show_inactive=show_inactive)


@main.route('/admin/mcdm-pesos/historico/<string:context>')
@login_required
@admin_required
def historico_pesos(context):
    if context not in ('MEB', 'TEB'):
        abort(404)
    versoes = (MCDMWeights.query
               .filter_by(context=context)
               .order_by(MCDMWeights.active_date.desc())
               .all())
    return render_template('historico_pesos.html', versoes=versoes, context=context)


@main.route('/admin/mcdm-pesos/restaurar/<int:id>', methods=['POST'])
@login_required
@admin_required
def restaurar_pesos(id):
    target = MCDMWeights.query.get_or_404(id)
    if target.is_active:
        flash('Esta versão já está ativa.')
        return redirect(url_for('main.historico_pesos', context=target.context))

    now = datetime.utcnow()
    current = MCDMWeights.query.filter_by(context=target.context, is_active=True).first()
    if current:
        current.is_active = False
        current.inactive_date = now

    target.is_active = True
    target.active_date = now
    target.inactive_date = None
    target.updated_at = now
    target.updated_by = current_user.username
    db.session.commit()
    flash(f'Versão de {target.active_date.strftime("%d/%m/%Y %H:%M") if target.active_date else "-"} restaurada como ativa.')
    return redirect(url_for('main.historico_pesos', context=target.context))


def _meb_primary_codes():
    return [m.code for m in MethodologyEvidenceBase.query.filter_by(
        is_active=True, eligible_as_primary_envelope=True
    ).order_by(MethodologyEvidenceBase.code).all()]


@main.route('/admin/meb/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def meb_novo():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        if not code:
            flash('O código é obrigatório.')
            return render_template('form_meb.html', meb=None, titulo='Nova Metodologia', primary_codes=_meb_primary_codes())
        if MethodologyEvidenceBase.query.filter_by(code=code, is_active=True).first():
            flash(f'Já existe uma metodologia ativa com o código "{code}".')
            return render_template('form_meb.html', meb=None, titulo='Nova Metodologia', primary_codes=_meb_primary_codes())

        meb = MethodologyEvidenceBase(
            code=code,
            name=request.form.get('name', '').strip(),
            posture=request.form.get('posture', 'Híbrida'),
            tier=int(request.form.get('tier', 1)),
            description=request.form.get('description', '').strip() or None,
            max_team_size=_parse_int(request.form.get('max_team_size')),
            requires_fixed_scope='requires_fixed_scope' in request.form,
            regulatory_compatible='regulatory_compatible' in request.form,
            posture_adpo_min=int(request.form.get('posture_adpo_min', 2)),
            posture_adpo_max=int(request.form.get('posture_adpo_max', 2)),
            posture_aspo_min=int(request.form.get('posture_aspo_min', 2)),
            posture_aspo_max=int(request.form.get('posture_aspo_max', 2)),
            compatible_approaches=request.form.getlist('compatible_approaches'),
            candidate_type=request.form.get('candidate_type', '').strip() or None,
            candidate_role=request.form.get('candidate_role', '').strip() or None,
            eligible_as_primary_envelope='eligible_as_primary_envelope' in request.form,
            compatible_as_component_of=request.form.getlist('compatible_as_component_of'),
            score_c1_responsiveness=float(request.form.get('score_c1_responsiveness', 0.5)),
            score_c2_alignment=float(request.form.get('score_c2_alignment', 0.5)),
            score_c3_traceability=float(request.form.get('score_c3_traceability', 0.5)),
            score_c4_compliance=float(request.form.get('score_c4_compliance', 0.5)),
            score_c5_pace_criticality=float(request.form.get('score_c5_pace_criticality', 0.5)),
            score_c6_integration_risk=float(request.form.get('score_c6_integration_risk', 0.5)),
            score_c7_distributed_support=float(request.form.get('score_c7_distributed_support', 0.5)),
            is_active=True,
            active_date=datetime.utcnow(),
            updated_by=current_user.username,
        )
        db.session.add(meb)
        db.session.commit()
        flash(f'Metodologia "{meb.name}" criada.')
        return redirect(url_for('main.gerir_mcdm'))

    return render_template('form_meb.html', meb=None, titulo='Nova Metodologia', primary_codes=_meb_primary_codes())


@main.route('/admin/meb/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def meb_editar(id):
    meb = MethodologyEvidenceBase.query.get_or_404(id)
    if request.method == 'POST':
        now = datetime.utcnow()
        meb.is_active = False
        meb.inactive_date = now
        new_meb = MethodologyEvidenceBase(
            code=meb.code,
            name=request.form.get('name', '').strip(),
            posture=request.form.get('posture', 'Híbrida'),
            tier=int(request.form.get('tier', 1)),
            description=request.form.get('description', '').strip() or None,
            max_team_size=_parse_int(request.form.get('max_team_size')),
            requires_fixed_scope='requires_fixed_scope' in request.form,
            regulatory_compatible='regulatory_compatible' in request.form,
            posture_adpo_min=int(request.form.get('posture_adpo_min', 2)),
            posture_adpo_max=int(request.form.get('posture_adpo_max', 2)),
            posture_aspo_min=int(request.form.get('posture_aspo_min', 2)),
            posture_aspo_max=int(request.form.get('posture_aspo_max', 2)),
            compatible_approaches=request.form.getlist('compatible_approaches'),
            candidate_type=request.form.get('candidate_type', '').strip() or None,
            candidate_role=request.form.get('candidate_role', '').strip() or None,
            eligible_as_primary_envelope='eligible_as_primary_envelope' in request.form,
            compatible_as_component_of=request.form.getlist('compatible_as_component_of'),
            score_c1_responsiveness=float(request.form.get('score_c1_responsiveness', 0.5)),
            score_c2_alignment=float(request.form.get('score_c2_alignment', 0.5)),
            score_c3_traceability=float(request.form.get('score_c3_traceability', 0.5)),
            score_c4_compliance=float(request.form.get('score_c4_compliance', 0.5)),
            score_c5_pace_criticality=float(request.form.get('score_c5_pace_criticality', 0.5)),
            score_c6_integration_risk=float(request.form.get('score_c6_integration_risk', 0.5)),
            score_c7_distributed_support=float(request.form.get('score_c7_distributed_support', 0.5)),
            is_active=True,
            active_date=now,
            updated_by=current_user.username,
        )
        db.session.add(new_meb)
        db.session.commit()
        flash(f'Metodologia "{new_meb.name}" atualizada (versão anterior arquivada).')
        return redirect(url_for('main.gerir_mcdm'))

    return render_template('form_meb.html', meb=meb, titulo='Editar Metodologia', primary_codes=_meb_primary_codes())


@main.route('/admin/meb/<string:code>/historico')
@login_required
@admin_required
def historico_meb(code):
    versoes = (MethodologyEvidenceBase.query
               .filter_by(code=code)
               .order_by(MethodologyEvidenceBase.active_date.desc())
               .all())
    if not versoes:
        abort(404)
    return render_template('historico_evidencia.html', versoes=versoes,
                           tipo='MEB', code=code, nome=versoes[0].name)


@main.route('/admin/meb/restaurar/<int:id>', methods=['POST'])
@login_required
@admin_required
def restaurar_meb(id):
    target = MethodologyEvidenceBase.query.get_or_404(id)
    if target.is_active:
        flash('Esta versão já está ativa.')
        return redirect(url_for('main.historico_meb', code=target.code))
    now = datetime.utcnow()
    current = MethodologyEvidenceBase.query.filter_by(code=target.code, is_active=True).first()
    if current:
        current.is_active = False
        current.inactive_date = now
    target.is_active = True
    target.active_date = now
    target.inactive_date = None
    target.updated_by = current_user.username
    db.session.commit()
    flash(f'Versão arquivada de "{target.name}" restaurada.')
    return redirect(url_for('main.historico_meb', code=target.code))


@main.route('/admin/teb/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def teb_novo():
    all_mebs = MethodologyEvidenceBase.query.filter_by(is_active=True).order_by(MethodologyEvidenceBase.code).all()
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        if not code:
            flash('O código é obrigatório.')
            return render_template('form_teb.html', teb=None, titulo='Nova Ferramenta', all_mebs=all_mebs)
        if ToolEvidenceBase.query.filter_by(code=code, is_active=True).first():
            flash(f'Já existe uma ferramenta ativa com o código "{code}".')
            return render_template('form_teb.html', teb=None, titulo='Nova Ferramenta', all_mebs=all_mebs)

        teb = ToolEvidenceBase(
            code=code,
            name=request.form.get('name', '').strip(),
            category=request.form.getlist('categories'),
            cost_tier=request.form.get('cost_tier', 'free'),
            cost_monthly_eur=float(request.form.get('cost_monthly_eur', 0.0)),
            compatible_postures=request.form.getlist('compatible_postures'),
            compatible_methodologies=request.form.getlist('compatible_methodologies'),
            gdpr_compliant='gdpr_compliant' in request.form,
            agility_support=int(request.form.get('agility_support', 2)),
            assurance_support=int(request.form.get('assurance_support', 2)),
            contribution_cd1=float(request.form.get('contribution_cd1', 0.5)),
            contribution_cd2=float(request.form.get('contribution_cd2', 0.5)),
            contribution_cd3=float(request.form.get('contribution_cd3', 0.5)),
            contribution_cd4=float(request.form.get('contribution_cd4', 0.5)),
            contribution_cd5=float(request.form.get('contribution_cd5', 0.5)),
            contribution_cd6=float(request.form.get('contribution_cd6', 0.5)),
            contribution_cd7=float(request.form.get('contribution_cd7', 0.5)),
            contribution_cd8=float(request.form.get('contribution_cd8', 0.5)),
            is_active=True,
            active_date=datetime.utcnow(),
            updated_by=current_user.username,
        )
        db.session.add(teb)
        db.session.commit()
        flash(f'Ferramenta "{teb.name}" criada.')
        return redirect(url_for('main.gerir_mcdm'))

    return render_template('form_teb.html', teb=None, titulo='Nova Ferramenta', all_mebs=all_mebs)


@main.route('/admin/teb/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def teb_editar(id):
    teb = ToolEvidenceBase.query.get_or_404(id)
    all_mebs = MethodologyEvidenceBase.query.filter_by(is_active=True).order_by(MethodologyEvidenceBase.code).all()
    if request.method == 'POST':
        now = datetime.utcnow()
        teb.is_active = False
        teb.inactive_date = now
        new_teb = ToolEvidenceBase(
            code=teb.code,
            name=request.form.get('name', '').strip(),
            category=request.form.getlist('categories'),
            cost_tier=request.form.get('cost_tier', 'free'),
            cost_monthly_eur=float(request.form.get('cost_monthly_eur', 0.0)),
            compatible_postures=request.form.getlist('compatible_postures'),
            compatible_methodologies=request.form.getlist('compatible_methodologies'),
            gdpr_compliant='gdpr_compliant' in request.form,
            agility_support=int(request.form.get('agility_support', 2)),
            assurance_support=int(request.form.get('assurance_support', 2)),
            contribution_cd1=float(request.form.get('contribution_cd1', 0.5)),
            contribution_cd2=float(request.form.get('contribution_cd2', 0.5)),
            contribution_cd3=float(request.form.get('contribution_cd3', 0.5)),
            contribution_cd4=float(request.form.get('contribution_cd4', 0.5)),
            contribution_cd5=float(request.form.get('contribution_cd5', 0.5)),
            contribution_cd6=float(request.form.get('contribution_cd6', 0.5)),
            contribution_cd7=float(request.form.get('contribution_cd7', 0.5)),
            contribution_cd8=float(request.form.get('contribution_cd8', 0.5)),
            is_active=True,
            active_date=now,
            updated_by=current_user.username,
        )
        db.session.add(new_teb)
        db.session.commit()
        flash(f'Ferramenta "{new_teb.name}" atualizada (versão anterior arquivada).')
        return redirect(url_for('main.gerir_mcdm'))

    return render_template('form_teb.html', teb=teb, titulo='Editar Ferramenta', all_mebs=all_mebs)


@main.route('/admin/teb/<string:code>/historico')
@login_required
@admin_required
def historico_teb(code):
    versoes = (ToolEvidenceBase.query
               .filter_by(code=code)
               .order_by(ToolEvidenceBase.active_date.desc())
               .all())
    if not versoes:
        abort(404)
    return render_template('historico_evidencia.html', versoes=versoes,
                           tipo='TEB', code=code, nome=versoes[0].name)


@main.route('/admin/teb/restaurar/<int:id>', methods=['POST'])
@login_required
@admin_required
def restaurar_teb(id):
    target = ToolEvidenceBase.query.get_or_404(id)
    if target.is_active:
        flash('Esta versão já está ativa.')
        return redirect(url_for('main.historico_teb', code=target.code))
    now = datetime.utcnow()
    current = ToolEvidenceBase.query.filter_by(code=target.code, is_active=True).first()
    if current:
        current.is_active = False
        current.inactive_date = now
    target.is_active = True
    target.active_date = now
    target.inactive_date = None
    target.updated_by = current_user.username
    db.session.commit()
    flash(f'Versão arquivada de "{target.name}" restaurada.')
    return redirect(url_for('main.historico_teb', code=target.code))


def _parse_int(val):
    try:
        return int(val) if val and str(val).strip() else None
    except (ValueError, TypeError):
        return None
