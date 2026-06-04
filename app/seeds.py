from .extensions import db
from .models import MethodologyEvidenceBase, ToolEvidenceBase, MCDMWeights


def run_seeds():
    _seed_meb()
    _seed_teb()
    _seed_mcdm_weights()
    print("Seeds MEB, TEB e MCDMWeights carregados com sucesso.")


def _seed_mcdm_weights():
    from datetime import datetime

    _upsert_weights('MEB',
                    weights=[0.25, 0.25, 0.10, 0.10, 0.30],
                    labels=['assurance', 'agility', 'scalability', 'hybridisation', 'posture_alignment'])

    _upsert_weights('TEB',
                    weights=[0.30, 0.25, 0.25, 0.20],
                    labels=['traceability', 'integration', 'flow_support', 'context_alignment'])


def _upsert_weights(context: str, weights: list, labels: list):
    from datetime import datetime
    existing = MCDMWeights.query.filter_by(context=context, is_active=True).first()
    if existing and existing.labels == labels:
        return  # already up-to-date
    now = datetime.utcnow()
    if existing:
        existing.is_active = False
        existing.inactive_date = now
    try:
        db.session.add(MCDMWeights(
            context=context,
            weights=weights,
            labels=labels,
            is_active=True,
            active_date=now,
            updated_by='system',
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _seed_meb():
    methodologies = [
        dict(
            code="SCRUM", name="Scrum", posture="Adaptativa", tier=1,
            requires_fixed_scope=False, regulatory_compatible=True,
            ag_posture=4, as_posture=1,
            score_assurance=0.45, score_agility=0.90, score_scalability=0.65, score_hybridisation=0.70,
            description="Framework ágil iterativa com sprints de 1-4 semanas. "
                        "Ideal para equipas pequenas com requisitos voláteis."
        ),
        dict(
            code="KANBAN", name="Kanban", posture="Adaptativa", tier=1,
            requires_fixed_scope=False, regulatory_compatible=True,
            ag_posture=3, as_posture=1,
            score_assurance=0.35, score_agility=0.95, score_scalability=0.70, score_hybridisation=0.75,
            description="Sistema de fluxo contínuo orientado a limitar o trabalho "
                        "em curso (WIP). Altamente flexível e visual."
        ),
        dict(
            code="PMBOK6", name="PMBoK 6ª Edição", posture="Preditiva", tier=1,
            requires_fixed_scope=True, regulatory_compatible=True,
            ag_posture=1, as_posture=4,
            score_assurance=0.90, score_agility=0.30, score_scalability=0.75, score_hybridisation=0.40,
            description="Guia de boas práticas do PMI. Forte em rastreabilidade, "
                        "gestão de risco e stakeholders. Requer âmbito definido."
        ),
        dict(
            code="PRINCE2", name="PRINCE2 Agile", posture="Preditiva", tier=1,
            requires_fixed_scope=True, regulatory_compatible=True,
            ag_posture=1, as_posture=4,
            score_assurance=0.95, score_agility=0.25, score_scalability=0.65, score_hybridisation=0.35,
            description="Metodologia orientada a processos com forte governança. "
                        "Amplamente utilizada em projetos governamentais e europeus."
        ),
        dict(
            code="SAFe", name="SAFe 6.0", posture="Híbrida", tier=2,
            requires_fixed_scope=False, regulatory_compatible=True,
            ag_posture=3, as_posture=3,
            score_assurance=0.70, score_agility=0.70, score_scalability=0.95, score_hybridisation=0.85,
            description="Framework de escalonamento ágil para organizações de grande "
                        "dimensão. Equilibra agilidade e governança corporativa."
        ),
        dict(
            code="XP", name="Extreme Programming (XP)", posture="Adaptativa", tier=2,
            requires_fixed_scope=False, regulatory_compatible=False,
            ag_posture=4, as_posture=2,
            score_assurance=0.40, score_agility=0.90, score_scalability=0.45, score_hybridisation=0.50,
            description="Metodologia ágil de engenharia de software com práticas como "
                        "TDD, pair programming e integração contínua."
        ),
        dict(
            code="DSDM", name="DSDM Atern", posture="Híbrida", tier=1,
            requires_fixed_scope=False, regulatory_compatible=True,
            ag_posture=3, as_posture=3,
            score_assurance=0.75, score_agility=0.65, score_scalability=0.65, score_hybridisation=0.80,
            description="Framework ágil orientada a negócio com foco em entregas no "
                        "prazo. Equilibra flexibilidade e controlo."
        ),
        dict(
            code="CRISP_DM", name="CRISP-DM", posture="Híbrida", tier=2,
            requires_fixed_scope=False, regulatory_compatible=True,
            ag_posture=2, as_posture=3,
            score_assurance=0.65, score_agility=0.55, score_scalability=0.60, score_hybridisation=0.65,
            description="Processo standard para projetos de Data Science e Machine Learning. "
                        "Iterativo com forte ênfase na compreensão dos dados."
        ),
        dict(
            code="ISO21502", name="ISO 21502", posture="Preditiva", tier=2,
            requires_fixed_scope=True, regulatory_compatible=True,
            ag_posture=1, as_posture=4,
            score_assurance=0.92, score_agility=0.28, score_scalability=0.70, score_hybridisation=0.38,
            description="Norma ISO internacional para gestão de projetos. "
                        "Orientada a processos com forte governança e conformidade regulatória."
        ),
        dict(
            code="PM2", name="PM2 (Comissão Europeia)", posture="Híbrida", tier=2,
            requires_fixed_scope=False, regulatory_compatible=True,
            ag_posture=3, as_posture=3,
            score_assurance=0.72, score_agility=0.68, score_scalability=0.80, score_hybridisation=0.82,
            description="Framework de gestão de projetos desenvolvida pela Comissão Europeia. "
                        "Combina estrutura com flexibilidade; amplamente utilizada em projetos públicos europeus."
        ),
    ]

    for m in methodologies:
        existing = MethodologyEvidenceBase.query.filter_by(code=m["code"], is_active=True).first()
        try:
            if existing:
                for k, v in m.items():
                    setattr(existing, k, v)
            else:
                db.session.add(MethodologyEvidenceBase(**m))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _seed_teb():
    tools = [
        # Planning
        dict(
            code="MS_PROJECT", name="Microsoft Project", category="Planning",
            cost_tier="medium", cost_monthly_eur=30.0,
            compatible_postures=["Preditiva", "Híbrida"],
            compatible_methodologies=["PMBOK6", "PRINCE2", "DSDM", "ISO21502", "PM2"],
            requires_cloud=False, gdpr_compliant=True,
            agility_support=1, assurance_support=4,
            score_traceability=0.85, score_integration=0.60, score_flow_support=0.45,
        ),
        dict(
            code="PROJECTLIBRE", name="ProjectLibre", category="Planning",
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Preditiva", "Híbrida"],
            compatible_methodologies=["PMBOK6", "PRINCE2", "ISO21502", "PM2"],
            requires_cloud=False, gdpr_compliant=True,
            agility_support=1, assurance_support=3,
            score_traceability=0.65, score_integration=0.35, score_flow_support=0.35,
        ),
        # Tracking
        dict(
            code="JIRA", name="Jira", category="Tracking",
            cost_tier="low", cost_monthly_eur=8.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "SAFe", "XP", "DSDM"],
            requires_cloud=True, gdpr_compliant=True,
            agility_support=4, assurance_support=3,
            score_traceability=0.85, score_integration=0.90, score_flow_support=0.85,
        ),
        dict(
            code="TRELLO", name="Trello", category="Tracking",
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "XP"],
            requires_cloud=True, gdpr_compliant=True,
            agility_support=4, assurance_support=1,
            score_traceability=0.40, score_integration=0.65, score_flow_support=0.90,
        ),
        dict(
            code="ASANA", name="Asana", category="Tracking",
            cost_tier="low", cost_monthly_eur=10.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "DSDM", "SAFe"],
            requires_cloud=True, gdpr_compliant=True,
            agility_support=3, assurance_support=2,
            score_traceability=0.65, score_integration=0.75, score_flow_support=0.80,
        ),
        dict(
            code="GITHUB_ISSUES", name="GitHub Issues", category="Tracking",
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "XP"],
            requires_cloud=True, gdpr_compliant=True,
            agility_support=4, assurance_support=2,
            score_traceability=0.55, score_integration=0.85, score_flow_support=0.70,
        ),
        dict(
            code="MONDAY", name="Monday.com", category="Tracking",
            cost_tier="medium", cost_monthly_eur=12.0,
            compatible_postures=["Adaptativa", "Híbrida", "Preditiva"],
            compatible_methodologies=["SCRUM", "KANBAN", "PMBOK6", "DSDM"],
            requires_cloud=True, gdpr_compliant=True,
            agility_support=3, assurance_support=3,
            score_traceability=0.75, score_integration=0.80, score_flow_support=0.80,
        ),
        dict(
            code="CLICKUP", name="ClickUp", category="Tracking",
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Adaptativa", "Híbrida", "Preditiva"],
            compatible_methodologies=["SCRUM", "KANBAN", "PMBOK6"],
            requires_cloud=True, gdpr_compliant=True,
            agility_support=3, assurance_support=2,
            score_traceability=0.70, score_integration=0.75, score_flow_support=0.80,
        ),
        # Communication
        dict(
            code="SLACK", name="Slack", category="Communication",
            cost_tier="low", cost_monthly_eur=7.0,
            compatible_postures=["Adaptativa", "Híbrida", "Preditiva"],
            compatible_methodologies=["SCRUM", "KANBAN", "XP", "SAFe", "DSDM", "PMBOK6", "PRINCE2", "CRISP_DM", "ISO21502", "PM2"],
            requires_cloud=True, gdpr_compliant=True,
            agility_support=3, assurance_support=2,
            score_traceability=0.30, score_integration=0.85, score_flow_support=0.40,
        ),
        dict(
            code="TEAMS", name="Microsoft Teams", category="Communication",
            cost_tier="low", cost_monthly_eur=5.0,
            compatible_postures=["Adaptativa", "Híbrida", "Preditiva"],
            compatible_methodologies=["PMBOK6", "PRINCE2", "SAFe", "DSDM", "SCRUM", "KANBAN", "ISO21502", "PM2"],
            requires_cloud=True, gdpr_compliant=True,
            agility_support=2, assurance_support=3,
            score_traceability=0.45, score_integration=0.80, score_flow_support=0.40,
        ),
        # Documentation
        dict(
            code="CONFLUENCE", name="Confluence", category="Documentation",
            cost_tier="low", cost_monthly_eur=5.0,
            compatible_postures=["Adaptativa", "Híbrida", "Preditiva"],
            compatible_methodologies=["SCRUM", "KANBAN", "SAFe", "PMBOK6", "PRINCE2", "DSDM", "ISO21502", "PM2"],
            requires_cloud=True, gdpr_compliant=True,
            agility_support=2, assurance_support=4,
            score_traceability=0.80, score_integration=0.85, score_flow_support=0.50,
        ),
        dict(
            code="NOTION", name="Notion", category="Documentation",
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "XP", "CRISP_DM"],
            requires_cloud=True, gdpr_compliant=True,
            agility_support=3, assurance_support=2,
            score_traceability=0.50, score_integration=0.60, score_flow_support=0.60,
        ),
        # Collaboration
        dict(
            code="MIRO", name="Miro", category="Collaboration",
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "XP", "DSDM", "SAFe", "CRISP_DM"],
            requires_cloud=True, gdpr_compliant=True,
            agility_support=4, assurance_support=1,
            score_traceability=0.30, score_integration=0.60, score_flow_support=0.90,
        ),
    ]

    for t in tools:
        existing = ToolEvidenceBase.query.filter_by(code=t["code"], is_active=True).first()
        try:
            if existing:
                for k, v in t.items():
                    setattr(existing, k, v)
            else:
                db.session.add(ToolEvidenceBase(**t))
            db.session.commit()
        except Exception:
            db.session.rollback()
