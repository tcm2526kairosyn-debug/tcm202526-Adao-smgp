import uuid
from flask_login import UserMixin
from .extensions import db
from datetime import datetime

VALID_ROLES = ('user', 'admin', 'inativado')


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'user' | 'admin'

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_inativado(self):
        return self.role == 'inativado'


class PendingRegistration(db.Model):
    __tablename__ = 'pending_registration'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | approved | rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PendingRegistration {self.username} | {self.status}>'


class ReactivationRequest(db.Model):
    __tablename__ = 'reactivation_request'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text)
    contact_channel = db.Column(db.String(200))
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | approved | rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='reactivation_requests')

    def __repr__(self):
        return f'<ReactivationRequest user_id={self.user_id} | {self.status}>'


class Projeto(db.Model):
    __tablename__ = 'projetos'

    id = db.Column(db.Integer, primary_key=True)
    projeto_uuid = db.Column(db.String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String(100), nullable=False)
    gestor_projeto = db.Column(db.String(100), nullable=False)
    equipa_projeto = db.Column(db.Text)
    objetivo = db.Column(db.Text)
    entregaveis = db.Column(db.Text)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    orcamento = db.Column(db.Float)
    fase_atual = db.Column(db.String(50), default='Iniciação')
    status = db.Column(db.String(20), default='Ativo')
    created_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    inactive_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<Projeto {self.nome} | UUID: {self.projeto_uuid} | Ativo: {self.is_active}>'


class MethodologyEvidenceBase(db.Model):
    __tablename__ = 'methodology_evidence_base'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)   # not unique — SCD Type-2
    name = db.Column(db.String(100), nullable=False)
    posture = db.Column(db.String(20))   # Adaptativa | Preditiva | Híbrida
    tier = db.Column(db.Integer)         # 1 or 2

    # Constraint flags for Level 1 filter
    max_team_size = db.Column(db.Integer)
    requires_fixed_scope = db.Column(db.Boolean, default=False)
    regulatory_compatible = db.Column(db.Boolean, default=True)

    # Posture coordinates in (AdPO, AsPO) space — used for Level 1 alignment
    # classification only (admissibility tier), never as a Level 2 MAVT column.
    ag_posture = db.Column(db.Integer, default=2)  # {1,2,3,4}
    as_posture = db.Column(db.Integer, default=2)  # {1,2,3,4}

    # Candidate typology — prevents treating overlays/norms/complementary methods
    # as autonomous substitutes for a primary methodological envelope (Level 1).
    candidate_type = db.Column(db.String(40))   # framework | method | guide | norm | domain_process_model
    candidate_role = db.Column(db.String(40))   # primary_envelope | complementary | reference_overlay | normative_overlay
    eligible_as_primary_envelope = db.Column(db.Boolean, default=True)

    # Stage 3 Level 2 fit criteria C1-C7 (benefit-oriented, normalized 0-1).
    # These are the ONLY criteria consumed by the MAVT matrix — no posture or
    # context signal is re-introduced here (see kairosynlogic.run_fit_m_level2).
    score_c1_responsiveness = db.Column(db.Float, default=0.5)      # cadence, WIP control, change absorption
    score_c2_alignment = db.Column(db.Float, default=0.5)           # stakeholder alignment, discovery, sensemaking
    score_c3_traceability = db.Column(db.Float, default=0.5)        # evidence traceability, audit artefacts
    score_c4_compliance = db.Column(db.Float, default=0.5)          # compliance readiness, formal gates
    score_c5_pace_criticality = db.Column(db.Float, default=0.5)    # pace under escalation/assurance/risk
    score_c6_integration_risk = db.Column(db.Float, default=0.5)    # hw/sw co-evolution, dependency handling
    score_c7_distributed_support = db.Column(db.Float, default=0.5) # coordination, scaling, distributed delivery

    description = db.Column(db.Text)

    # SCD Type-2 audit
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    active_date = db.Column(db.DateTime, default=datetime.utcnow)
    inactive_date = db.Column(db.DateTime, nullable=True)
    updated_by = db.Column(db.String(80), nullable=True)

    def __repr__(self):
        return f'<MEB {self.code} | {self.posture} | tier={self.tier}>'


class ToolEvidenceBase(db.Model):
    __tablename__ = 'tool_evidence_base'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), nullable=False)   # not unique — SCD Type-2
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.JSON)          # ["Planning", "Tracking", ...]  — multi-category support
    cost_tier = db.Column(db.String(10))  # free | low | medium | high
    cost_monthly_eur = db.Column(db.Float, default=0.0)

    # Stored as JSON arrays for cross-DB compatibility
    compatible_postures = db.Column(db.JSON)       # ["Adaptativa", "Híbrida"]
    compatible_methodologies = db.Column(db.JSON)  # ["SCRUM", "KANBAN"]

    # Hard constraints
    gdpr_compliant = db.Column(db.Boolean, default=True)

    # Posture metadata in (AdPO, AsPO) space — retained for Level A audit/display;
    # NOT consumed by Level B MAVT scoring (see kairosynlogic.run_fit_t_level_b).
    agility_support = db.Column(db.Integer, default=2)   # {1,2,3,4}
    assurance_support = db.Column(db.Integer, default=2)  # {1,2,3,4}

    # Stage 4 Level B implementation capability dimensions CD1-CD8 (normalized 0-1).
    # These are the ONLY criteria consumed by the MAVT matrix.
    contribution_cd1 = db.Column(db.Float, default=0.5)  # evidence & traceability depth
    contribution_cd2 = db.Column(db.Float, default=0.5)  # verification cadence & review controls
    contribution_cd3 = db.Column(db.Float, default=0.5)  # iteration & flow control
    contribution_cd4 = db.Column(db.Float, default=0.5)  # discovery & feedback capacity
    contribution_cd5 = db.Column(db.Float, default=0.5)  # risk, safety & security evidence routines
    contribution_cd6 = db.Column(db.Float, default=0.5)  # compliance & audit readiness
    contribution_cd7 = db.Column(db.Float, default=0.5)  # lifecycle integration & evidence automation
    contribution_cd8 = db.Column(db.Float, default=0.5)  # dependency & interface management

    # SCD Type-2 audit
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    active_date = db.Column(db.DateTime, default=datetime.utcnow)
    inactive_date = db.Column(db.DateTime, nullable=True)
    updated_by = db.Column(db.String(80), nullable=True)

    def __repr__(self):
        return f'<TEB {self.code} | {self.category}>'


class MCDMWeights(db.Model):
    __tablename__ = 'mcdm_weights'

    id = db.Column(db.Integer, primary_key=True)
    context = db.Column(db.String(10), nullable=False)  # 'MEB' | 'TEB' — not unique (SCD Type-2)
    weights = db.Column(db.JSON, nullable=False)
    labels = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by = db.Column(db.String(80))

    # SCD Type-2 audit
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    active_date = db.Column(db.DateTime, default=datetime.utcnow)
    inactive_date = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<MCDMWeights {self.context} | active={self.is_active} | {self.weights}>'


class ProjectDecision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    projeto_id = db.Column(db.Integer, db.ForeignKey('projetos.id'), nullable=True)

    # Etapa 1
    agpi_score = db.Column(db.Float)
    aspi_score = db.Column(db.Float)
    evidence_notes = db.Column(db.JSON)
    questionnaire_version = db.Column(db.String(10), default='v2')

    # Etapa 2
    suggested_approach = db.Column(db.String(50))  # Preditiva | Adaptativa | Híbrida
    decision_control_register = db.Column(db.JSON)  # {hard: [], threshold: [], soft: []}
    reentry_cause = db.Column(db.String(100))       # governance_infeasibility | tool_infeasibility

    # Etapa 3
    selected_methodology = db.Column(db.String(100))
    selected_methodology_id = db.Column(db.Integer, db.ForeignKey('methodology_evidence_base.id'), nullable=True)
    meb_filtered = db.Column(db.JSON)        # IDs que passaram Level 1
    meb_exclusions = db.Column(db.JSON)      # [{code, name, cause, detail}] — auditoria Level 1
    methodology_ranking = db.Column(db.JSON) # [{id, code, name, score, misfit}, ...]
    mcdm_engine = db.Column(db.String(20), default='MAVT')

    # Etapa 4
    teb_filtered = db.Column(db.JSON)   # IDs que passaram Level A
    teb_exclusions = db.Column(db.JSON) # [{code, name, cause, detail}] — auditoria Level A
    tool_portfolio = db.Column(db.JSON) # [{id, code, name, score, category}, ...]

    # State machine
    current_stage = db.Column(db.String(50), default='stage_1_diagnosis')

    # Audit
    state_history = db.Column(db.JSON)
    context_data = db.Column(db.JSON)
    transition_history = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
