import numpy as np
from .mcdm_engine import MCDMEngine

_MEB_WEIGHTS_DEFAULT = np.array([0.12, 0.12, 0.18, 0.18, 0.15, 0.13, 0.12])
_TEB_WEIGHTS_DEFAULT = np.array([0.15, 0.12, 0.13, 0.10, 0.10, 0.15, 0.15, 0.10])

_MEB_CRITERIA = ['score_c1_responsiveness', 'score_c2_alignment', 'score_c3_traceability',
                 'score_c4_compliance', 'score_c5_pace_criticality',
                 'score_c6_integration_risk', 'score_c7_distributed_support']
_TEB_CRITERIA = ['contribution_cd1', 'contribution_cd2', 'contribution_cd3', 'contribution_cd4',
                 'contribution_cd5', 'contribution_cd6', 'contribution_cd7', 'contribution_cd8']

_SENSITIVITY_THRESHOLD = 0.60  # prototype decision-support threshold, convenção da prova de conceito

_MISFIT_BY_TIER = {'exact': 0.0, 'adjacent': 0.7, 'distant': 1.5}


_MEB_CRITERIA_LABELS = [
    ('C1', 'Responsiveness'), ('C2', 'Alignment'), ('C3', 'Traceability'), ('C4', 'Compliance'),
    ('C5', 'Pace/Criticality'), ('C6', 'Integration Risk'), ('C7', 'Distributed Support'),
]


def get_weights_preset(context: str) -> tuple[list[float], int | None]:
    """get_weights_preset('MEB') -> ([0.12, 0.12, 0.18, 0.18, 0.15, 0.13, 0.12], 7)"""
    fallback = _MEB_WEIGHTS_DEFAULT if context == 'MEB' else _TEB_WEIGHTS_DEFAULT
    try:
        from ..models import MCDMWeights
        row = MCDMWeights.query.filter_by(context=context, is_active=True).first()
        if row and row.weights and len(row.weights) == len(fallback):
            return [float(w) for w in row.weights], row.id
    except Exception:
        pass
    return fallback.tolist(), None


def weights_to_points(weights: list[float]) -> list[int]:
    """weights_to_points([0.12, 0.12, 0.18, 0.18, 0.15, 0.13, 0.12]) -> [12, 12, 18, 18, 15, 13, 12]"""
    total = sum(weights) or 1.0
    raw = [w / total * 100 for w in weights]
    points = [int(r) for r in raw]
    order = sorted(range(len(raw)), key=lambda i: raw[i] - points[i], reverse=True)
    for i in order[:100 - sum(points)]:
        points[i] += 1
    return points


def points_to_weights(points: list[float], n: int) -> list[float] | None:
    """points_to_weights([12, 12, 18, 18, 15, 13, 12], 7) -> [0.12, 0.12, 0.18, 0.18, 0.15, 0.13, 0.12]"""
    if len(points) != n or any(p < 0 for p in points) or sum(points) <= 0:
        return None
    total = float(sum(points))
    return [round(p / total, 4) for p in points]


def criteria_labels(context: str) -> list[dict]:
    """criteria_labels('TEB')[0] -> {'code': 'CD1', 'label': 'Evidence & Traceability'}"""
    if context == 'MEB':
        return [{"code": c, "label": l} for c, l in _MEB_CRITERIA_LABELS]
    return [{"code": c, "label": l} for _, c, l in _CD_LABELS]


def _require_weights(weights, n: int) -> np.ndarray:
    """_require_weights([0.12, 0.12, 0.18, 0.18, 0.15, 0.13, 0.12], 7) -> array([...])"""
    if weights is None or len(weights) != n:
        raise ValueError(f"Vetor de pesos confirmado em falta ou com dimensão errada (esperado {n}).")
    return np.array(weights, dtype=float)


# ── Etapa 2 ─────────────────────────────────────────────────────────────────

STAGE1_DIMENSIONS = [
    {"key": "causal_complexity", "code": "D1", "name": "Causal Complexity", "organiser": "AdPO",
     "reading": "Complexidade causal, interdependências e previsibilidade das relações entre ações e resultados",
     "low": "Relações causa-efeito previsíveis", "high": "Causalidade emergente, legível só após integração"},
    {"key": "novelty_exposure", "code": "D2", "name": "Technological & Novelty Exposure", "organiser": "AdPO",
     "reading": "Grau de novidade tecnológica, desconhecimento e exposição a soluções pouco estabilizadas",
     "low": "Tecnologia conhecida e estabilizada", "high": "Soluções novas, sem precedentes"},
    {"key": "stakeholder_alignment", "code": "D3", "name": "Stakeholder Alignment & Cognitive Agreement", "organiser": "AdPO",
     "reading": "Alinhamento entre stakeholders, objetivos, interpretações e critérios de decisão",
     "low": "Objetivos e critérios partilhados", "high": "Desacordo sobre objetivos e interpretações"},
    {"key": "pace_criticality", "code": "D4", "name": "Pace & Criticality", "organiser": "AsPO",
     "reading": "Pressão temporal, criticidade das entregas e impacto de atrasos ou falhas",
     "low": "Atrasos ou falhas com impacto reduzido", "high": "Prazos apertados, falhas com impacto severo"},
    {"key": "environmental_volatility", "code": "D5", "name": "Environmental Volatility", "organiser": "AdPO",
     "reading": "Frequência e magnitude de alterações externas relevantes",
     "low": "Contexto externo estável", "high": "Alterações externas frequentes e relevantes"},
    {"key": "structural_fragility", "code": "D6", "name": "Structural Fragility & Saturation", "organiser": "AsPO",
     "reading": "Fragilidade estrutural, dependências, gargalos e saturação de capacidade",
     "low": "Baixo acoplamento, capacidade folgada", "high": "Gargalos, dependências críticas, capacidade saturada"},
    {"key": "institutional_pressure", "code": "D7", "name": "Institutional Pressure & Compliance Load", "organiser": "AsPO",
     "reading": "Obrigações legais, normativas, contratuais e de assurance",
     "low": "Sem obrigações formais relevantes", "high": "Obrigações legais e normativas não discricionárias"},
    {"key": "interpretative_ambiguity", "code": "D8", "name": "Interpretative Ambiguity", "organiser": "AdPO",
     "reading": "Grau de ambiguidade e instabilidade das interpretações aplicáveis ao problema",
     "low": "Interpretações estáveis e partilhadas", "high": "Significados contestados e instáveis"},
]
_DIM = {d["code"]: d["key"] for d in STAGE1_DIMENSIONS}
ADPO_DIMS = [d["key"] for d in STAGE1_DIMENSIONS if d["organiser"] == "AdPO"]
ASPO_DIMS = [d["key"] for d in STAGE1_DIMENSIONS if d["organiser"] == "AsPO"]


def compute_indices(context_data: dict) -> tuple[float, float]:
    """
    compute_indices({'causal_complexity':3,'novelty_exposure':4,'stakeholder_alignment':2,'pace_criticality':3,
    'environmental_volatility':3,'structural_fragility':4,'institutional_pressure':4,'interpretative_ambiguity':3}) -> (4.0, 4.0)
    """
    def _ordinal(dims: list[str]) -> float:
        h = sum(1 for d in dims if context_data.get(d, 1) >= 3)
        return float(min(h, 3) + 1)

    return _ordinal(ADPO_DIMS), _ordinal(ASPO_DIMS)


def resolve_approach(adpo: float, aspo: float) -> str:
    """resolve_approach(4.0, 1.0) -> 'Adaptativa'"""
    if adpo >= 3.0 and aspo <= 2.0:
        return "Adaptativa"
    elif adpo <= 2.0 and aspo >= 3.0:
        return "Preditiva"
    else:
        return "Híbrida"


def approach_descriptor(adpo: float, aspo: float) -> str | None:
    """approach_descriptor(4.0, 3.0) -> 'Híbrida de alta pressão, adaptive-leaning'"""
    if resolve_approach(adpo, aspo) != "Híbrida":
        return None
    if adpo <= 2.0 and aspo <= 2.0:
        return "Híbrida de baixa pressão"
    if aspo > adpo:
        return "Híbrida de alta pressão, assurance-heavy"
    if adpo > aspo:
        return "Híbrida de alta pressão, adaptive-leaning"
    return "Híbrida de alta pressão, balanced"


def build_decision_control_register(approach: str, context_data: dict, adpo: float, aspo: float) -> dict:
    """
    build_decision_control_register('Preditiva', {'institutional_pressure':4,'pace_criticality':4,...}, 1.0, 4.0)
    -> {'binding_constraints': [{'constraint':'regulatory_compatible','value':True,'scope':'M',...},
                                 {'constraint':'gdpr_compliant','value':True,'scope':'T',...}],
        'acceptance_thresholds': [{'constraint':'requires_fixed_scope','value':True,'scope':'M',...}],
        'advisory_guidelines': []}
    """
    register = {"binding_constraints": [], "acceptance_thresholds": [], "advisory_guidelines": []}
    v = {code: context_data.get(key, 1) for code, key in _DIM.items()}

    if v["D7"] >= 3:
        register["binding_constraints"].append({
            "constraint": "regulatory_compatible", "value": True, "scope": "M", "source": ["D7"],
            "reason": f"D7 Institutional Pressure {v['D7']}/4: obrigações normativas exigem candidatos regulatory_compatible."
        })
    if v["D7"] >= 4:
        register["binding_constraints"].append({
            "constraint": "gdpr_compliant", "value": True, "scope": "T", "source": ["D7"],
            "reason": f"D7 Institutional Pressure {v['D7']}/4: carga máxima de compliance exige ferramentas conformes com o RGPD."
        })

    if v["D4"] >= 3:
        register["acceptance_thresholds"].append({
            "constraint": "requires_fixed_scope", "value": (approach == "Preditiva"), "scope": "M", "source": ["D4"],
            "reason": f"D4 Pace & Criticality {v['D4']}/4: criticidade das entregas exige âmbito definido em abordagem Preditiva."
        })

    advisory = [
        (max(v["D2"], v["D8"]) >= 3, "favour_discovery_rituals", ["D2", "D8"],
         "novidade ou ambiguidade interpretativa elevadas favorecem rituais de descoberta reforçados"),
        (v["D5"] >= 3, "favour_frequent_feedback", ["D5"],
         "volatilidade do ambiente favorece ciclos de feedback mais frequentes"),
        (v["D3"] >= 3, "reinforce_facilitation", ["D3"],
         "baixo alinhamento entre stakeholders favorece facilitação reforçada"),
        (v["D6"] >= 3, "favour_controlled_integration", ["D6"],
         "fragilidade estrutural favorece mecanismos de integração controlada"),
    ]
    for active, constraint, source, text in advisory:
        if active:
            register["advisory_guidelines"].append({
                "constraint": constraint, "scope": "M", "source": source,
                "reason": f"{', '.join(f'{c} {v[c]}/4' for c in source)}: {text}."
            })

    return register


def _posture_alignment_tier(adpo: float, aspo: float,
                            adpo_min: int, adpo_max: int, aspo_min: int, aspo_max: int) -> str:
    """_posture_alignment_tier(4, 4, 3, 4, 1, 2) -> 'distant'"""
    dx = max(adpo_min - adpo, adpo - adpo_max, 0)
    dy = max(aspo_min - aspo, aspo - aspo_max, 0)
    delta = max(dx, dy)
    if delta == 0:
        return 'exact'
    elif delta == 1:
        return 'adjacent'
    else:
        return 'distant'


def _approach_compatible(compatible_approaches: list, approach: str) -> bool:
    """_approach_compatible(['Preditiva','Híbrida'], 'Adaptativa') -> False"""
    if not approach:
        return True
    if not compatible_approaches:
        return True
    return approach in compatible_approaches


# ── Etapa 3 ─────────────────────────────────────────────────────────────────

def _meb_scoped_constraints(decision_control_register: dict) -> tuple[dict, dict]:
    """_meb_scoped_constraints(dcr) -> ({'regulatory_compatible': True}, {'requires_fixed_scope': True})"""
    binding_constraints = {c["constraint"]: c["value"]
                           for c in decision_control_register.get("binding_constraints", []) if c["scope"] == "M"}
    acceptance_thresholds = {c["constraint"]: c["value"]
                             for c in decision_control_register.get("acceptance_thresholds", []) if c["scope"] == "M"}
    return binding_constraints, acceptance_thresholds


def _check_binding_and_acceptance(m, binding_constraints: dict, acceptance_thresholds: dict) -> dict | None:
    """_check_binding_and_acceptance(XP, {}, {}) -> None"""
    if "regulatory_compatible" in binding_constraints:
        if m.regulatory_compatible != binding_constraints["regulatory_compatible"]:
            return {"cause": "binding_regulatory_incompatible",
                    "detail": "Binding constraint: regulatory_compatible exigido pelo decision-control register."}

    if "requires_fixed_scope" in acceptance_thresholds:
        required = acceptance_thresholds["requires_fixed_scope"]
        has_scope = m.requires_fixed_scope or False
        if required and not has_scope:
            return {"cause": "acceptance_threshold_requires_fixed_scope",
                    "detail": "Acceptance threshold: âmbito fixo exigido, não suportado pela metodologia."}
    return None


def _check_approach_and_posture(m, approach: str, adpo: float, aspo: float) -> tuple[dict | None, str]:
    """_check_approach_and_posture(ISO21502, 'Adaptativa', 4.0, 1.0) -> ({'cause': 'approach_incompatible', ...}, None)"""
    if not _approach_compatible(m.compatible_approaches, approach):
        return {"cause": "approach_incompatible",
                "detail": f"Abordagens compatíveis {m.compatible_approaches} não incluem '{approach}'."}, None

    adpo_min = m.posture_adpo_min if m.posture_adpo_min is not None else 2
    adpo_max = m.posture_adpo_max if m.posture_adpo_max is not None else 2
    aspo_min = m.posture_aspo_min if m.posture_aspo_min is not None else 2
    aspo_max = m.posture_aspo_max if m.posture_aspo_max is not None else 2
    tier = _posture_alignment_tier(adpo, aspo, adpo_min, adpo_max, aspo_min, aspo_max)
    if tier == 'distant':
        return {"cause": "posture_distant",
                "detail": f"(AdPO={adpo:.0f}, AsPO={aspo:.0f}) fora da região de postura declarada "
                          f"AdPO∈[{adpo_min},{adpo_max}] × AsPO∈[{aspo_min},{aspo_max}] (distância ≥ 2)."}, tier
    return None, tier


def _missing_criteria(obj, criteria: list[str]) -> list[str]:
    """_missing_criteria(JIRA, _TEB_CRITERIA) -> []"""
    return [c for c in criteria if getattr(obj, c) is None]


def run_fit_m_level1(decision_control_register: dict, adpo: float, aspo: float,
                     approach: str = 'Híbrida') -> list:
    """
    run_fit_m_level1(dcr, adpo=1.0, aspo=4.0, approach='Preditiva')
    -> (viable=[(PRINCE2,'exact'), (PM2,'exact')],
        exclusions=[{'code':'SCRUM','cause':'acceptance_threshold_requires_fixed_scope',...}, ...8 total])
    """
    from ..models import MethodologyEvidenceBase

    candidates = MethodologyEvidenceBase.query.filter(
        MethodologyEvidenceBase.is_active == True
    ).all()

    binding_constraints, acceptance_thresholds = _meb_scoped_constraints(decision_control_register)

    viable = []
    exclusions = []

    def _exclude(m, cause, detail):
        exclusions.append({"code": m.code, "name": m.name, "cause": cause, "detail": detail})

    for m in candidates:
        exc = _check_binding_and_acceptance(m, binding_constraints, acceptance_thresholds)
        if exc:
            _exclude(m, exc["cause"], exc["detail"])
            continue

        if m.eligible_as_primary_envelope is False:
            _exclude(m, "not_eligible_primary_envelope",
                     f"candidate_role='{m.candidate_role}', não elegível como envelope metodológico primário.")
            continue

        exc, tier = _check_approach_and_posture(m, approach, adpo, aspo)
        if exc:
            _exclude(m, exc["cause"], exc["detail"])
            continue

        missing = _missing_criteria(m, _MEB_CRITERIA)
        if missing:
            _exclude(m, "missing_criteria_evidence",
                     f"Sem valor na MEB para {', '.join(missing)}, não pode entrar no MAVT sem evidência.")
            continue

        viable.append((m, tier))

    return viable, exclusions


def run_fit_m_level2(viable: list, engine_name: str = 'MAVT', *, weights: list) -> list:
    """
    run_fit_m_level2([(PRINCE2,'exact'), (PM2,'exact')], weights=[0.12,0.12,0.18,0.18,0.15,0.13,0.12])
    -> [{'code':'PRINCE2','score':0.7325,...}, {'code':'PM2','score':0.7025,...}]
    """
    if not viable:
        return []

    X = np.array([[float(getattr(m, c)) for c in _MEB_CRITERIA] for m, _ in viable])
    weights = _require_weights(weights, len(_MEB_CRITERIA))

    engine = MCDMEngine(method=engine_name)
    ranked_indices = engine.rank(X, weights)

    result = []
    for idx, score in ranked_indices:
        m, tier = viable[idx]
        result.append({
            "id": m.id,
            "code": m.code,
            "name": m.name,
            "posture": m.posture,
            "compatible_approaches": m.compatible_approaches or [],
            "tier": m.tier,
            "score": round(score, 4),
            "misfit": _MISFIT_BY_TIER.get(tier, 0.7),
            "posture_alignment_tier": tier,
            "posture_region": {
                "adpo_min": m.posture_adpo_min, "adpo_max": m.posture_adpo_max,
                "aspo_min": m.posture_aspo_min, "aspo_max": m.posture_aspo_max,
            },
            "candidate_type": m.candidate_type,
            "candidate_role": m.candidate_role,
            "description": m.description or "",
            "criteria": {
                "c1_responsiveness": round(m.score_c1_responsiveness, 3),
                "c2_alignment": round(m.score_c2_alignment, 3),
                "c3_traceability": round(m.score_c3_traceability, 3),
                "c4_compliance": round(m.score_c4_compliance, 3),
                "c5_pace_criticality": round(m.score_c5_pace_criticality, 3),
                "c6_integration_risk": round(m.score_c6_integration_risk, 3),
                "c7_distributed_support": round(m.score_c7_distributed_support, 3),
            }
        })
    return sorted(result, key=lambda x: x["score"], reverse=True)


def get_envelope_component_candidates(primary_meth, decision_control_register: dict,
                                      adpo: float, aspo: float, approach: str) -> tuple:
    """
    get_envelope_component_candidates(PRINCE2, dcr, adpo=1.0, aspo=4.0, approach='Preditiva')
    -> (eligible=[ISO21502],
        exclusions=[{'code':'PMBOK6','name':'PMBoK 6ª Edição','cause':'acceptance_threshold_requires_fixed_scope',...}])
    """
    from ..models import MethodologyEvidenceBase

    if primary_meth is None:
        return [], []

    binding_constraints, acceptance_thresholds = _meb_scoped_constraints(decision_control_register)

    rows = MethodologyEvidenceBase.query.filter_by(is_active=True).all()
    metadata_compatible = [m for m in rows
                           if m.id != primary_meth.id
                           and primary_meth.code in (m.compatible_as_component_of or [])]

    eligible = []
    exclusions = []

    def _exclude(m, cause, detail):
        exclusions.append({"code": m.code, "name": m.name, "cause": cause, "detail": detail})

    for m in metadata_compatible:
        exc = _check_binding_and_acceptance(m, binding_constraints, acceptance_thresholds)
        if exc:
            _exclude(m, exc["cause"], exc["detail"])
            continue
        exc, _tier = _check_approach_and_posture(m, approach, adpo, aspo)
        if exc:
            _exclude(m, exc["cause"], exc["detail"])
            continue
        eligible.append(m)

    return eligible, exclusions


# ── Etapa 4 ─────────────────────────────────────────────────────────────────

def _check_tool_acceptance_thresholds(t, acceptance_thresholds: dict) -> dict | None:
    """
    _check_tool_acceptance_thresholds(TEAMS, {'min_contribution_cd6': 0.75})
    -> {'cause': 'acceptance_threshold_min_contribution_cd6', 'detail': 'contribution_cd6 = 0.50 < 0.75 ...'}
    """
    for constraint, required in acceptance_thresholds.items():
        attr = constraint[len('min_'):] if constraint.startswith('min_') else constraint
        if not hasattr(t, attr):
            raise ValueError(f"Acceptance threshold desconhecido para a TEB: '{constraint}'.")
        value = getattr(t, attr)
        if constraint.startswith('min_'):
            if value is None or value < required:
                return {"cause": f"acceptance_threshold_{constraint}",
                        "detail": f"Acceptance threshold: {attr} = {value} < {required} exigido pelo decision-control register."}
        elif value != required:
            return {"cause": f"acceptance_threshold_{constraint}",
                    "detail": f"Acceptance threshold: {attr} = {value}, exigido {required} pelo decision-control register."}
    return None


def run_fit_t_level_a(selected_meth, decision_control_register: dict,
                      envelope_codes: list = None) -> tuple:
    """
    run_fit_t_level_a(PRINCE2, dcr, ['PRINCE2'])
    -> (viable=[MS_PROJECT, PROJECTLIBRE, SLACK, TEAMS, CONFLUENCE],
        exclusions=[{'code':'JIRA','cause':'methodology_incompatible',...}, ...])
    """
    from ..models import ToolEvidenceBase

    envelope_codes = envelope_codes or [selected_meth.code]

    tools = ToolEvidenceBase.query.filter_by(is_active=True).all()
    binding_constraints = {c["constraint"]: c["value"]
                           for c in decision_control_register.get("binding_constraints", []) if c["scope"] == "T"}
    acceptance_thresholds = {c["constraint"]: c["value"]
                             for c in decision_control_register.get("acceptance_thresholds", []) if c["scope"] == "T"}

    viable = []
    exclusions = []

    def _exclude(t, cause, detail):
        exclusions.append({"code": t.code, "name": t.name, "cause": cause, "detail": detail})

    for t in tools:
        if "gdpr_compliant" in binding_constraints:
            if t.gdpr_compliant != binding_constraints["gdpr_compliant"]:
                _exclude(t, "binding_gdpr_incompatible",
                         "Binding constraint: gdpr_compliant exigido pelo decision-control register.")
                continue

        exc = _check_tool_acceptance_thresholds(t, acceptance_thresholds)
        if exc:
            _exclude(t, exc["cause"], exc["detail"])
            continue

        if not (set(t.compatible_methodologies or []) & set(envelope_codes)):
            _exclude(t, "methodology_incompatible",
                     f"Não declara compatibilidade com o envelope metodológico ({', '.join(envelope_codes)}).")
            continue

        if selected_meth.posture not in (t.compatible_postures or []):
            _exclude(t, "posture_incompatible",
                     f"Não declara compatibilidade com a postura '{selected_meth.posture}'.")
            continue

        missing = _missing_criteria(t, _TEB_CRITERIA)
        if missing:
            _exclude(t, "missing_criteria_evidence",
                     f"Sem valor na TEB para {', '.join(missing)}, não pode entrar no MAVT sem evidência.")
            continue

        viable.append(t)

    return viable, exclusions


_CD_LABELS = [
    ('contribution_cd1', 'CD1', 'Evidence & Traceability'),
    ('contribution_cd2', 'CD2', 'Verification & Review'),
    ('contribution_cd3', 'CD3', 'Iteration & Flow'),
    ('contribution_cd4', 'CD4', 'Discovery & Feedback'),
    ('contribution_cd5', 'CD5', 'Risk/Safety/Security'),
    ('contribution_cd6', 'CD6', 'Compliance & Audit'),
    ('contribution_cd7', 'CD7', 'Lifecycle Integration'),
    ('contribution_cd8', 'CD8', 'Dependency & Interface'),
]


def build_capability_map(viable_tools: list) -> list:
    """
    build_capability_map(viable_tools)
    -> [{'code':'CD1','label':'Evidence & Traceability','max_contribution':0.75,'coverage':'strong',
         'covered_by':[{'code':'MS_PROJECT','contribution':0.75}, ...]}, ...CD2-CD8]
    """
    capability_map = []
    for attr, code, label in _CD_LABELS:
        contribs = sorted(
            ({"code": t.code, "name": t.name, "contribution": round(float(getattr(t, attr)), 2)}
             for t in viable_tools),
            key=lambda x: x["contribution"], reverse=True)
        max_c = contribs[0]["contribution"] if contribs else 0.0
        coverage = 'strong' if max_c >= 0.7 else ('partial' if max_c >= 0.4 else 'gap')
        capability_map.append({
            "key": attr,
            "code": code,
            "label": label,
            "max_contribution": max_c,
            "coverage": coverage,
            "covered_by": [c for c in contribs if c["contribution"] >= 0.5],
        })
    return capability_map


def run_fit_t_level_b(viable_tools: list, engine_name: str = 'MAVT', top_n: int = 3,
                      *, weights: list) -> dict:
    """
    run_fit_t_level_b(viable_tools, top_n=2, weights=[0.15,0.12,0.13,0.10,0.10,0.15,0.15,0.10])
    -> shortlist {'Documentation':['CONFLUENCE'], 'Planning':['MS_PROJECT','PROJECTLIBRE'], 'Communication':['TEAMS','SLACK']}
    """
    if not viable_tools:
        return {}

    X = np.array([[float(getattr(t, c)) for c in _TEB_CRITERIA] for t in viable_tools])

    engine = MCDMEngine(method=engine_name)
    ranked = engine.rank(X, _require_weights(weights, len(_TEB_CRITERIA)))

    all_scored = []
    for idx, score in ranked:
        t = viable_tools[idx]
        all_scored.append({
            "id": t.id,
            "code": t.code,
            "name": t.name,
            "category": t.category,
            "cost_tier": t.cost_tier,
            "cost_monthly_eur": t.cost_monthly_eur,
            "score": round(score, 4),
            "criteria": {
                "cd1_traceability": round(t.contribution_cd1, 3),
                "cd2_verification": round(t.contribution_cd2, 3),
                "cd3_flow_control": round(t.contribution_cd3, 3),
                "cd4_discovery": round(t.contribution_cd4, 3),
                "cd5_risk_safety": round(t.contribution_cd5, 3),
                "cd6_compliance": round(t.contribution_cd6, 3),
                "cd7_integration": round(t.contribution_cd7, 3),
                "cd8_dependency": round(t.contribution_cd8, 3),
            }
        })

    by_category = {}
    for item in all_scored:
        cats = item["category"] if isinstance(item["category"], list) else [item["category"]]
        for cat in cats:
            by_category.setdefault(cat, []).append(item)

    shortlist_by_category = {cat: tools[:top_n] for cat, tools in by_category.items()}
    return shortlist_by_category


# ── Sensitivity Analysis ──────────────────────────────────────────────────────

def run_sensitivity_analysis(ranking: list, n_mc: int = 500, *, weights: list | None, seed: int = 42) -> dict | None:
    """
    run_sensitivity_analysis(ranking_B, n_mc=500, weights=[0.12,0.12,0.18,0.18,0.15,0.13,0.12])
    -> {'top_name':'PRINCE2 Agile', 'robustness_pct':100.0, 'stable':True, 'displaced_pct':0.0,
        'displacing_alternative':None, 'displacing_alternative_pct':0.0, 'per_criterion':[...7 entries...]}
    """
    if not ranking or len(ranking) < 2 or weights is None:
        return None
    if not all('criteria' in m for m in ranking):
        return None

    CRITERIA = ['c1_responsiveness', 'c2_alignment', 'c3_traceability', 'c4_compliance',
                'c5_pace_criticality', 'c6_integration_risk', 'c7_distributed_support']
    LABELS   = ['C1 Responsiveness', 'C2 Alignment', 'C3 Traceability', 'C4 Compliance',
                'C5 Pace/Criticality', 'C6 Integration Risk', 'C7 Distributed Support']
    N = len(CRITERIA)

    X = np.array([[float(m['criteria'][c]) for c in CRITERIA] for m in ranking])

    w0 = _require_weights(weights, 7)

    def _top(w: np.ndarray) -> int:
        return MCDMEngine(method='MAVT').rank(X, w)[0][0]

    def _redistribute(j: int, w_new: float) -> np.ndarray | None:
        others = np.array([w0[i] if i != j else 0.0 for i in range(N)])
        s = others.sum()
        if s < 1e-10:
            return None
        w = others * (1.0 - w_new) / s
        w[j] = w_new
        total = w.sum()
        return w / total if total > 0 else None

    current_top = _top(w0)
    top_name = ranking[current_top]['name']

    per_criterion = []
    step = 0.01
    for j, (label, key) in enumerate(zip(LABELS, CRITERIA)):
        w_cur = float(w0[j])
        s_min, s_max = 0.0, 1.0

        for w_new in np.arange(w_cur - step, -step, -step):
            nw = _redistribute(j, round(max(0.0, w_new), 4))
            if nw is None:
                break
            if _top(nw) != current_top:
                s_min = round(max(0.0, w_new) + step, 3)
                break

        for w_new in np.arange(w_cur + step, 1.0 + step, step):
            nw = _redistribute(j, round(min(1.0, w_new), 4))
            if nw is None:
                break
            if _top(nw) != current_top:
                s_max = round(min(1.0, w_new) - step, 3)
                break

        per_criterion.append({
            'label': label,
            'key': key,
            'current': round(w_cur, 3),
            'min': round(s_min, 3),
            'max': round(s_max, 3),
            'range': round(max(0.0, s_max - s_min), 3),
        })

    rng = np.random.default_rng(seed)
    samples = rng.dirichlet(np.ones(N), size=n_mc)
    top_count = 0
    displacing_counts: dict[str, int] = {}

    for w in samples:
        winner_idx = MCDMEngine(method='MAVT').rank(X, w)[0][0]
        if winner_idx == current_top:
            top_count += 1
        else:
            name = ranking[winner_idx]['name']
            displacing_counts[name] = displacing_counts.get(name, 0) + 1

    robustness = round(top_count / n_mc, 3)
    displacing = max(displacing_counts, key=displacing_counts.get) if displacing_counts else None
    displacing_pct = round(displacing_counts[displacing] / n_mc * 100, 1) if displacing else 0.0

    return {
        'top_name': top_name,
        'robustness_score': robustness,
        'robustness_pct': round(robustness * 100, 1),
        'stability_threshold': _SENSITIVITY_THRESHOLD,
        'stable': robustness >= _SENSITIVITY_THRESHOLD,
        'per_criterion': per_criterion,
        'displaced_pct': round((n_mc - top_count) / n_mc * 100, 1),
        'displacing_alternative': displacing,
        'displacing_alternative_pct': displacing_pct,
        'n_simulations': n_mc,
        'seed': seed,
        'sampling': 'Dirichlet(1,...,1)',
        'sweep_step': step,
        'base_weights': [round(float(w), 4) for w in w0],
        'criteria': CRITERIA,
        'evaluated': [{'id': m['id'], 'code': m['code'], 'score': m['score']} for m in ranking],
    }
