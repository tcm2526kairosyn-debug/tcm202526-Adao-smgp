from .extensions import db
from .models import MethodologyEvidenceBase, ToolEvidenceBase, MCDMWeights


def run_seeds():
    _seed_meb()
    _seed_teb()
    _seed_mcdm_weights()
    print("Seeds MEB, TEB e MCDMWeights carregados com sucesso.")


def _seed_mcdm_weights():
    from datetime import datetime

    # Level 2 (Stage 3) — explicit, elicited weights over C1-C7 only.
    # No posture/context signal is amplified automatically (no ALPHA reweighting).
    _upsert_weights('MEB',
                    weights=[0.12, 0.12, 0.18, 0.18, 0.15, 0.13, 0.12],
                    labels=['C1_responsiveness', 'C2_alignment', 'C3_traceability', 'C4_compliance',
                            'C5_pace_criticality', 'C6_integration_risk', 'C7_distributed_support'])

    # Level B (Stage 4) — explicit weights over CD1-CD8 only.
    _upsert_weights('TEB',
                    weights=[0.15, 0.12, 0.13, 0.10, 0.10, 0.15, 0.15, 0.10],
                    labels=['CD1_traceability', 'CD2_verification', 'CD3_flow_control', 'CD4_discovery',
                            'CD5_risk_safety', 'CD6_compliance', 'CD7_integration', 'CD8_dependency'])


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
    # Candidate typology and C1-C7 seed values follow the alignment note
    # (Tabelas 5 e 8): posture/context signals no longer feed the MAVT matrix
    # directly — only C1-C7 (methodology-fit criteria) are used in Level 2.
    methodologies = [
        dict(
            code="SCRUM", name="Scrum", posture="Adaptativa", tier=1,
            requires_fixed_scope=False, regulatory_compatible=True,
            posture_adpo_min=3, posture_adpo_max=4, posture_aspo_min=1, posture_aspo_max=2,
            compatible_approaches=['Adaptativa', 'Híbrida'],
            candidate_type="framework", candidate_role="primary_team_level",
            eligible_as_primary_envelope=True,
            compatible_as_component_of=[],
            score_c1_responsiveness=1.00, score_c2_alignment=0.75, score_c3_traceability=0.50,
            score_c4_compliance=0.25, score_c5_pace_criticality=0.50,
            score_c6_integration_risk=0.50, score_c7_distributed_support=0.50,
            description="Framework ágil iterativa com sprints de 1-4 semanas. "
                        "Ideal para equipas pequenas com requisitos voláteis."
        ),
        dict(
            code="KANBAN", name="Kanban", posture="Adaptativa", tier=1,
            requires_fixed_scope=False, regulatory_compatible=True,
            posture_adpo_min=2, posture_adpo_max=4, posture_aspo_min=1, posture_aspo_max=3,
            compatible_approaches=['Adaptativa', 'Híbrida'],
            candidate_type="flow_method", candidate_role="primary_or_complementary",
            eligible_as_primary_envelope=True,
            compatible_as_component_of=["SCRUM", "SAFe", "DSDM", "PM2"],
            score_c1_responsiveness=1.00, score_c2_alignment=0.50, score_c3_traceability=0.50,
            score_c4_compliance=0.25, score_c5_pace_criticality=0.75,
            score_c6_integration_risk=0.50, score_c7_distributed_support=0.50,
            description="Sistema de fluxo contínuo orientado a limitar o trabalho "
                        "em curso (WIP). Altamente flexível e visual."
        ),
        dict(
            code="PMBOK6", name="PMBoK 6ª Edição", posture="Preditiva", tier=1,
            requires_fixed_scope=True, regulatory_compatible=True,
            posture_adpo_min=1, posture_adpo_max=3, posture_aspo_min=2, posture_aspo_max=4,
            compatible_approaches=['Preditiva', 'Híbrida'],
            candidate_type="guide_bok", candidate_role="reference_overlay",
            eligible_as_primary_envelope=False,
            compatible_as_component_of=["PRINCE2", "PM2", "DSDM", "SAFe"],
            score_c1_responsiveness=0.50, score_c2_alignment=0.50, score_c3_traceability=0.75,
            score_c4_compliance=0.75, score_c5_pace_criticality=0.75,
            score_c6_integration_risk=0.50, score_c7_distributed_support=0.50,
            description="Guia de boas práticas do PMI. Forte em rastreabilidade, "
                        "gestão de risco e stakeholders. Não constitui, por si só, um "
                        "envelope metodológico primário (reference overlay)."
        ),
        dict(
            code="PRINCE2", name="PRINCE2 Agile", posture="Preditiva", tier=1,
            requires_fixed_scope=True, regulatory_compatible=True,
            posture_adpo_min=2, posture_adpo_max=4, posture_aspo_min=2, posture_aspo_max=4,
            # Divergência deliberada da Tabela 5 (que lista só "Hybrid"): PRINCE2
            # combina controlo formal predefinido com adaptação por etapas, pelo
            # que também é admissível em contextos Preditivos — decisão do autor.
            compatible_approaches=['Preditiva', 'Híbrida'],
            candidate_type="hybrid_methodology", candidate_role="primary_envelope",
            eligible_as_primary_envelope=True,
            compatible_as_component_of=[],
            score_c1_responsiveness=0.75, score_c2_alignment=0.75, score_c3_traceability=1.00,
            score_c4_compliance=0.75, score_c5_pace_criticality=0.75,
            score_c6_integration_risk=0.50, score_c7_distributed_support=0.50,
            description="Metodologia orientada a processos com forte governança. "
                        "Amplamente utilizada em projetos governamentais e europeus."
        ),
        dict(
            code="SAFe", name="SAFe 6.0", posture="Híbrida", tier=2,
            requires_fixed_scope=False, regulatory_compatible=True,
            posture_adpo_min=2, posture_adpo_max=4, posture_aspo_min=2, posture_aspo_max=4,
            compatible_approaches=['Híbrida'],
            candidate_type="scaling_framework", candidate_role="primary_envelope",
            eligible_as_primary_envelope=True,
            compatible_as_component_of=[],
            score_c1_responsiveness=0.75, score_c2_alignment=0.75, score_c3_traceability=0.75,
            score_c4_compliance=0.75, score_c5_pace_criticality=1.00,
            score_c6_integration_risk=1.00, score_c7_distributed_support=1.00,
            description="Framework de escalonamento ágil para organizações de grande "
                        "dimensão. Equilibra agilidade e governança corporativa."
        ),
        dict(
            code="XP", name="Extreme Programming (XP)", posture="Adaptativa", tier=2,
            requires_fixed_scope=False, regulatory_compatible=False,
            posture_adpo_min=3, posture_adpo_max=4, posture_aspo_min=1, posture_aspo_max=2,
            compatible_approaches=['Adaptativa', 'Híbrida'],
            candidate_type="engineering_method", candidate_role="complementary_engineering",
            eligible_as_primary_envelope=False,
            compatible_as_component_of=["SCRUM", "KANBAN", "SAFe", "DSDM"],
            score_c1_responsiveness=1.00, score_c2_alignment=0.50, score_c3_traceability=0.50,
            score_c4_compliance=0.25, score_c5_pace_criticality=0.75,
            score_c6_integration_risk=0.75, score_c7_distributed_support=0.25,
            description="Metodologia ágil de engenharia de software com práticas como "
                        "TDD, pair programming e integração contínua. Complementar a um "
                        "envelope de gestão, salvo em âmbito técnico restrito."
        ),
        dict(
            code="DSDM", name="DSDM Atern", posture="Híbrida", tier=1,
            requires_fixed_scope=False, regulatory_compatible=True,
            posture_adpo_min=2, posture_adpo_max=4, posture_aspo_min=2, posture_aspo_max=4,
            compatible_approaches=['Adaptativa', 'Híbrida'],
            candidate_type="methodology", candidate_role="primary_envelope",
            eligible_as_primary_envelope=True,
            compatible_as_component_of=[],
            score_c1_responsiveness=0.75, score_c2_alignment=0.75, score_c3_traceability=0.75,
            score_c4_compliance=0.50, score_c5_pace_criticality=0.75,
            score_c6_integration_risk=0.50, score_c7_distributed_support=0.50,
            description="Framework ágil orientada a negócio com foco em entregas no "
                        "prazo. Equilibra flexibilidade e controlo."
        ),
        dict(
            code="CRISP_DM", name="CRISP-DM", posture="Híbrida", tier=1,
            requires_fixed_scope=False, regulatory_compatible=True,
            posture_adpo_min=2, posture_adpo_max=4, posture_aspo_min=1, posture_aspo_max=3,
            compatible_approaches=['Adaptativa', 'Híbrida'],
            candidate_type="domain_process_model", candidate_role="primary_in_data_projects",
            eligible_as_primary_envelope=True,
            compatible_as_component_of=["SCRUM", "KANBAN", "SAFe"],
            score_c1_responsiveness=0.75, score_c2_alignment=0.75, score_c3_traceability=0.50,
            score_c4_compliance=0.25, score_c5_pace_criticality=0.50,
            score_c6_integration_risk=0.50, score_c7_distributed_support=0.25,
            description="Processo standard para projetos de Data Science e Machine Learning. "
                        "Iterativo com forte ênfase na compreensão dos dados."
        ),
        dict(
            code="ISO21502", name="ISO 21502", posture="Preditiva", tier=1,
            requires_fixed_scope=True, regulatory_compatible=True,
            posture_adpo_min=1, posture_adpo_max=3, posture_aspo_min=2, posture_aspo_max=4,
            compatible_approaches=['Preditiva', 'Híbrida'],
            candidate_type="guidance_standard", candidate_role="normative_overlay",
            eligible_as_primary_envelope=False,
            compatible_as_component_of=["PRINCE2", "PM2", "DSDM", "SAFe"],
            score_c1_responsiveness=0.50, score_c2_alignment=0.75, score_c3_traceability=0.75,
            score_c4_compliance=1.00, score_c5_pace_criticality=0.75,
            score_c6_integration_risk=0.50, score_c7_distributed_support=0.50,
            description="Norma ISO internacional para gestão de projetos. "
                        "Orientada a processos com forte governança e conformidade regulatória. "
                        "Não constitui, por si só, um substituto autónomo de metodologia (normative overlay)."
        ),
        dict(
            code="PM2", name="PM2 (Comissão Europeia)", posture="Híbrida", tier=1,
            requires_fixed_scope=True, regulatory_compatible=True,
            posture_adpo_min=1, posture_adpo_max=3, posture_aspo_min=2, posture_aspo_max=4,
            compatible_approaches=['Preditiva', 'Híbrida'],
            candidate_type="methodology", candidate_role="primary_envelope",
            eligible_as_primary_envelope=True,
            compatible_as_component_of=[],
            score_c1_responsiveness=0.50, score_c2_alignment=0.75, score_c3_traceability=1.00,
            score_c4_compliance=0.75, score_c5_pace_criticality=0.75,
            score_c6_integration_risk=0.50, score_c7_distributed_support=0.50,
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
    # CD1-CD8 seed values follow the same discrete rubric as C1-C7 (alignment
    # note Tabela 7): 0.00 ausente, 0.25 limitada/indireta, 0.50 moderada
    # (requer tailoring), 0.75 forte e operacionalizável, 1.00 muito forte e
    # estrutural. Illustrative estimates derived from documented product
    # capabilities (not empirically validated — see thesis limitations).
    # No posture/context coordinate is used here; agility_support/assurance_support
    # are retained only as Level A audit metadata (see kairosynlogic.run_fit_t_level_a).
    tools = [
        # Planning
        dict(
            code="MS_PROJECT", name="Microsoft Project", category=["Planning"],
            cost_tier="medium", cost_monthly_eur=30.0,
            compatible_postures=["Preditiva", "Híbrida"],
            compatible_methodologies=["PMBOK6", "PRINCE2", "DSDM", "ISO21502", "PM2"],
            gdpr_compliant=True,
            agility_support=1, assurance_support=4,
            contribution_cd1=0.75, contribution_cd2=0.75, contribution_cd3=0.50, contribution_cd4=0.25,
            contribution_cd5=0.50, contribution_cd6=0.75, contribution_cd7=0.50, contribution_cd8=0.75,
        ),
        dict(
            code="PROJECTLIBRE", name="ProjectLibre", category=["Planning"],
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Preditiva", "Híbrida"],
            compatible_methodologies=["PMBOK6", "PRINCE2", "ISO21502", "PM2"],
            gdpr_compliant=True,
            agility_support=1, assurance_support=3,
            contribution_cd1=0.75, contribution_cd2=0.50, contribution_cd3=0.25, contribution_cd4=0.25,
            contribution_cd5=0.25, contribution_cd6=0.50, contribution_cd7=0.25, contribution_cd8=0.75,
        ),
        # Tracking
        dict(
            code="JIRA", name="Jira", category=["Tracking"],
            cost_tier="low", cost_monthly_eur=8.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "SAFe", "XP", "DSDM"],
            gdpr_compliant=True,
            agility_support=4, assurance_support=3,
            contribution_cd1=0.75, contribution_cd2=0.75, contribution_cd3=0.75, contribution_cd4=0.75,
            contribution_cd5=0.50, contribution_cd6=0.75, contribution_cd7=1.00, contribution_cd8=0.75,
        ),
        dict(
            code="TRELLO", name="Trello", category=["Tracking"],
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "XP"],
            gdpr_compliant=True,
            agility_support=4, assurance_support=1,
            contribution_cd1=0.50, contribution_cd2=0.50, contribution_cd3=1.00, contribution_cd4=0.50,
            contribution_cd5=0.25, contribution_cd6=0.25, contribution_cd7=0.75, contribution_cd8=0.25,
        ),
        dict(
            code="ASANA", name="Asana", category=["Tracking"],
            cost_tier="low", cost_monthly_eur=10.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "DSDM", "SAFe"],
            gdpr_compliant=True,
            agility_support=3, assurance_support=2,
            contribution_cd1=0.75, contribution_cd2=0.75, contribution_cd3=0.75, contribution_cd4=0.50,
            contribution_cd5=0.25, contribution_cd6=0.50, contribution_cd7=0.75, contribution_cd8=0.50,
        ),
        dict(
            code="GITHUB_ISSUES", name="GitHub Issues", category=["Tracking"],
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "XP"],
            gdpr_compliant=True,
            agility_support=4, assurance_support=2,
            contribution_cd1=0.50, contribution_cd2=0.75, contribution_cd3=0.75, contribution_cd4=0.50,
            contribution_cd5=0.50, contribution_cd6=0.50, contribution_cd7=0.75, contribution_cd8=0.75,
        ),
        dict(
            code="MONDAY", name="Monday.com", category=["Tracking"],
            cost_tier="medium", cost_monthly_eur=12.0,
            compatible_postures=["Adaptativa", "Híbrida", "Preditiva"],
            compatible_methodologies=["SCRUM", "KANBAN", "PMBOK6", "DSDM"],
            gdpr_compliant=True,
            agility_support=3, assurance_support=3,
            contribution_cd1=0.75, contribution_cd2=0.75, contribution_cd3=0.75, contribution_cd4=0.75,
            contribution_cd5=0.25, contribution_cd6=0.50, contribution_cd7=0.75, contribution_cd8=0.50,
        ),
        dict(
            code="CLICKUP", name="ClickUp", category=["Tracking"],
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Adaptativa", "Híbrida", "Preditiva"],
            compatible_methodologies=["SCRUM", "KANBAN", "PMBOK6"],
            gdpr_compliant=True,
            agility_support=3, assurance_support=2,
            contribution_cd1=0.75, contribution_cd2=0.75, contribution_cd3=0.75, contribution_cd4=0.50,
            contribution_cd5=0.25, contribution_cd6=0.50, contribution_cd7=0.75, contribution_cd8=0.50,
        ),
        # Communication
        dict(
            code="SLACK", name="Slack", category=["Communication"],
            cost_tier="low", cost_monthly_eur=7.0,
            compatible_postures=["Adaptativa", "Híbrida", "Preditiva"],
            compatible_methodologies=["SCRUM", "KANBAN", "XP", "SAFe", "DSDM", "PMBOK6", "PRINCE2", "CRISP_DM", "ISO21502", "PM2"],
            gdpr_compliant=True,
            agility_support=3, assurance_support=2,
            contribution_cd1=0.25, contribution_cd2=0.25, contribution_cd3=0.50, contribution_cd4=0.75,
            contribution_cd5=0.25, contribution_cd6=0.25, contribution_cd7=0.75, contribution_cd8=0.25,
        ),
        dict(
            code="TEAMS", name="Microsoft Teams", category=["Communication"],
            cost_tier="low", cost_monthly_eur=5.0,
            compatible_postures=["Adaptativa", "Híbrida", "Preditiva"],
            compatible_methodologies=["PMBOK6", "PRINCE2", "SAFe", "DSDM", "SCRUM", "KANBAN", "ISO21502", "PM2"],
            gdpr_compliant=True,
            agility_support=2, assurance_support=3,
            contribution_cd1=0.50, contribution_cd2=0.50, contribution_cd3=0.50, contribution_cd4=0.75,
            contribution_cd5=0.25, contribution_cd6=0.50, contribution_cd7=0.75, contribution_cd8=0.25,
        ),
        # Documentation
        dict(
            code="CONFLUENCE", name="Confluence", category=["Documentation"],
            cost_tier="low", cost_monthly_eur=5.0,
            compatible_postures=["Adaptativa", "Híbrida", "Preditiva"],
            compatible_methodologies=["SCRUM", "KANBAN", "SAFe", "PMBOK6", "PRINCE2", "DSDM", "ISO21502", "PM2"],
            gdpr_compliant=True,
            agility_support=2, assurance_support=4,
            contribution_cd1=0.75, contribution_cd2=0.75, contribution_cd3=0.50, contribution_cd4=0.50,
            contribution_cd5=0.50, contribution_cd6=0.75, contribution_cd7=0.75, contribution_cd8=0.50,
        ),
        dict(
            code="NOTION", name="Notion", category=["Documentation"],
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "XP", "CRISP_DM"],
            gdpr_compliant=True,
            agility_support=3, assurance_support=2,
            contribution_cd1=0.50, contribution_cd2=0.50, contribution_cd3=0.50, contribution_cd4=0.50,
            contribution_cd5=0.25, contribution_cd6=0.50, contribution_cd7=0.50, contribution_cd8=0.25,
        ),
        # Collaboration
        dict(
            code="MIRO", name="Miro", category=["Collaboration"],
            cost_tier="free", cost_monthly_eur=0.0,
            compatible_postures=["Adaptativa", "Híbrida"],
            compatible_methodologies=["SCRUM", "KANBAN", "XP", "DSDM", "SAFe", "CRISP_DM"],
            gdpr_compliant=True,
            agility_support=4, assurance_support=1,
            contribution_cd1=0.25, contribution_cd2=0.25, contribution_cd3=1.00, contribution_cd4=0.75,
            contribution_cd5=0.25, contribution_cd6=0.25, contribution_cd7=0.50, contribution_cd8=0.25,
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
