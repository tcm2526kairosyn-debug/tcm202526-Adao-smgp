import numpy as np
from .mcdm_engine import MCDMEngine

_MEB_WEIGHTS_DEFAULT = np.array([0.12, 0.12, 0.18, 0.18, 0.15, 0.13, 0.12])
_TEB_WEIGHTS_DEFAULT = np.array([0.15, 0.12, 0.13, 0.10, 0.10, 0.15, 0.15, 0.10])

_MEB_CRITERIA = ['score_c1_responsiveness', 'score_c2_alignment', 'score_c3_traceability',
                 'score_c4_compliance', 'score_c5_pace_criticality',
                 'score_c6_integration_risk', 'score_c7_distributed_support']
_TEB_CRITERIA = ['contribution_cd1', 'contribution_cd2', 'contribution_cd3', 'contribution_cd4',
                 'contribution_cd5', 'contribution_cd6', 'contribution_cd7', 'contribution_cd8']

_MISFIT_BY_TIER = {'exact': 0.0, 'adjacent': 0.7, 'distant': 1.5}


def _load_weights(context: str, fallback: np.ndarray) -> np.ndarray:
    try:
        from ..models import MCDMWeights
        row = MCDMWeights.query.filter_by(context=context, is_active=True).first()
        if row and row.weights:
            return np.array(row.weights)
    except Exception:
        pass
    return fallback


MEB_WEIGHTS = _MEB_WEIGHTS_DEFAULT
TEB_WEIGHTS = _TEB_WEIGHTS_DEFAULT

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


def _resolve_weights(weights, context: str, fallback: np.ndarray) -> np.ndarray:
    if weights is not None and len(weights) == len(fallback):
        return np.array(weights, dtype=float)
    return _load_weights(context, fallback)


# ── Etapa 2 ─────────────────────────────────────────────────────────────────

def compute_indices(context_data: dict) -> tuple[float, float]:
    """
    compute_indices({'complexity':4,'novelty':4,'dynamism':4,'team_autonomy':3,
    'criticality':1,'compliance':1,'traceability':1,'stakeholder_formality':2}) -> (4.0, 1.0)
    """
    adpo_dims = ['complexity', 'novelty', 'dynamism', 'team_autonomy']
    aspo_dims = ['criticality', 'compliance', 'traceability', 'stakeholder_formality']

    def _ordinal(dims: list[str]) -> float:
        h = sum(1 for d in dims if context_data.get(d, 1) >= 3)
        if h == 0:
            return 1.0
        elif h == 1:
            return 2.0
        elif h == 2:
            return 3.0
        else:
            return 4.0

    return _ordinal(adpo_dims), _ordinal(aspo_dims)


def resolve_approach(adpo: float, aspo: float) -> str:
    """resolve_approach(4.0, 1.0) -> 'Adaptativa'"""
    if adpo >= 2.0 and aspo <= 2.0:
        return "Adaptativa"
    elif aspo >= 3.0 and adpo <= 2.0:
        return "Preditiva"
    else:
        return "Híbrida"


def build_decision_control_register(approach: str, context_data: dict, adpo: float, aspo: float) -> dict:
    """
    build_decision_control_register('Preditiva', {'compliance':4,'criticality':4,'team_autonomy':2,...}, 1.0, 4.0)
    -> {'binding_constraints': [{'constraint':'regulatory_compatible','value':True,'scope':'M',...},
                                 {'constraint':'gdpr_compliant','value':True,'scope':'T',...}],
        'acceptance_thresholds': [{'constraint':'requires_fixed_scope','value':True,'scope':'M',...}],
        'advisory_guidelines': []}
    """
    register = {"binding_constraints": [], "acceptance_thresholds": [], "advisory_guidelines": []}

    compliance = context_data.get('compliance', 1)
    criticality = context_data.get('criticality', 1)
    team_autonomy = context_data.get('team_autonomy', 1)

    if compliance >= 3:
        register["binding_constraints"].append({
            "constraint": "regulatory_compatible",
            "value": True,
            "scope": "M",
            "reason": f"Compliance score {compliance}/4 exige conformidade regulatória."
        })
    if compliance >= 4:
        register["binding_constraints"].append({
            "constraint": "gdpr_compliant",
            "value": True,
            "scope": "T",
            "reason": "Compliance máximo requer GDPR nas ferramentas."
        })

    if criticality >= 3:
        register["acceptance_thresholds"].append({
            "constraint": "requires_fixed_scope",
            "value": (approach == "Preditiva"),
            "scope": "M",
            "reason": f"Criticidade {criticality}/4 favorece âmbito definido em abordagem Preditiva."
        })

    if team_autonomy >= 3:
        register["advisory_guidelines"].append({
            "constraint": "prefers_low_process_overhead",
            "scope": "M",
            "reason": f"Autonomia de equipa {team_autonomy}/4 favorece metodologias ágeis leves."
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

    binding_constraints = {c["constraint"]: c["value"]
                           for c in decision_control_register.get("binding_constraints", []) if c["scope"] == "M"}
    acceptance_thresholds = {c["constraint"]: c["value"]
                             for c in decision_control_register.get("acceptance_thresholds", []) if c["scope"] == "M"}

    viable = []
    exclusions = []

    def _exclude(m, cause, detail):
        exclusions.append({"code": m.code, "name": m.name, "cause": cause, "detail": detail})

    for m in candidates:
        if "regulatory_compatible" in binding_constraints:
            if m.regulatory_compatible != binding_constraints["regulatory_compatible"]:
                _exclude(m, "binding_regulatory_incompatible",
                         "Binding constraint: regulatory_compatible exigido pelo decision-control register.")
                continue

        if "requires_fixed_scope" in acceptance_thresholds:
            required = acceptance_thresholds["requires_fixed_scope"]
            has_scope = m.requires_fixed_scope or False
            if required and not has_scope:
                _exclude(m, "acceptance_threshold_requires_fixed_scope",
                         "Acceptance threshold: âmbito fixo exigido, não suportado pela metodologia.")
                continue

        if m.eligible_as_primary_envelope is False:
            _exclude(m, "not_eligible_primary_envelope",
                     f"candidate_role='{m.candidate_role}', não elegível como envelope metodológico primário.")
            continue

        if not _approach_compatible(m.compatible_approaches, approach):
            _exclude(m, "approach_incompatible",
                     f"Abordagens compatíveis {m.compatible_approaches} não incluem '{approach}'.")
            continue

        adpo_min = m.posture_adpo_min if m.posture_adpo_min is not None else 2
        adpo_max = m.posture_adpo_max if m.posture_adpo_max is not None else 2
        aspo_min = m.posture_aspo_min if m.posture_aspo_min is not None else 2
        aspo_max = m.posture_aspo_max if m.posture_aspo_max is not None else 2
        tier = _posture_alignment_tier(adpo, aspo, adpo_min, adpo_max, aspo_min, aspo_max)
        if tier == 'distant':
            _exclude(m, "posture_distant",
                     f"(AdPO={adpo:.0f}, AsPO={aspo:.0f}) fora da região de postura declarada "
                     f"AdPO∈[{adpo_min},{adpo_max}] × AsPO∈[{aspo_min},{aspo_max}] (distância ≥ 2).")
            continue

        viable.append((m, tier))

    return viable, exclusions


def run_fit_m_level2(viable: list, engine_name: str = 'MAVT', weights: list = None) -> list:
    """
    run_fit_m_level2([(PRINCE2,'exact'), (PM2,'exact')], weights=[0.12,0.12,0.18,0.18,0.15,0.13,0.12])
    -> [{'code':'PRINCE2','score':0.7325,...}, {'code':'PM2','score':0.7025,...}]
    """
    if not viable:
        return []

    X = np.array([[getattr(m, c) or 0.5 for c in _MEB_CRITERIA] for m, _ in viable])
    weights = _resolve_weights(weights, 'MEB', _MEB_WEIGHTS_DEFAULT)

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
                "c1_responsiveness": round(m.score_c1_responsiveness or 0.5, 3),
                "c2_alignment": round(m.score_c2_alignment or 0.5, 3),
                "c3_traceability": round(m.score_c3_traceability or 0.5, 3),
                "c4_compliance": round(m.score_c4_compliance or 0.5, 3),
                "c5_pace_criticality": round(m.score_c5_pace_criticality or 0.5, 3),
                "c6_integration_risk": round(m.score_c6_integration_risk or 0.5, 3),
                "c7_distributed_support": round(m.score_c7_distributed_support or 0.5, 3),
            }
        })
    return sorted(result, key=lambda x: x["score"], reverse=True)


def get_envelope_component_candidates(primary_meth) -> list:
    """get_envelope_component_candidates(PRINCE2) -> [ISO21502 (normative_overlay), PMBOK6 (reference_overlay)]"""
    from ..models import MethodologyEvidenceBase

    if primary_meth is None:
        return []
    rows = MethodologyEvidenceBase.query.filter_by(is_active=True).all()
    return [m for m in rows
            if m.id != primary_meth.id
            and primary_meth.code in (m.compatible_as_component_of or [])]


# ── Etapa 4 ─────────────────────────────────────────────────────────────────

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

        if not (set(t.compatible_methodologies or []) & set(envelope_codes)):
            _exclude(t, "methodology_incompatible",
                     f"Não declara compatibilidade com o envelope metodológico ({', '.join(envelope_codes)}).")
            continue

        if selected_meth.posture not in (t.compatible_postures or []):
            _exclude(t, "posture_incompatible",
                     f"Não declara compatibilidade com a postura '{selected_meth.posture}'.")
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
            ({"code": t.code, "name": t.name, "contribution": round(getattr(t, attr) or 0.0, 2)}
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
                      weights: list = None) -> dict:
    """
    run_fit_t_level_b(viable_tools, top_n=2)
    -> {'Documentation':['CONFLUENCE'], 'Planning':['MS_PROJECT','PROJECTLIBRE'], 'Communication':['TEAMS','SLACK']}
    """
    if not viable_tools:
        return {}

    X = np.array([[getattr(t, c) or 0.5 for c in _TEB_CRITERIA] for t in viable_tools])

    engine = MCDMEngine(method=engine_name)
    ranked = engine.rank(X, _resolve_weights(weights, 'TEB', _TEB_WEIGHTS_DEFAULT))

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
                "cd1_traceability": round(t.contribution_cd1 or 0.5, 3),
                "cd2_verification": round(t.contribution_cd2 or 0.5, 3),
                "cd3_flow_control": round(t.contribution_cd3 or 0.5, 3),
                "cd4_discovery": round(t.contribution_cd4 or 0.5, 3),
                "cd5_risk_safety": round(t.contribution_cd5 or 0.5, 3),
                "cd6_compliance": round(t.contribution_cd6 or 0.5, 3),
                "cd7_integration": round(t.contribution_cd7 or 0.5, 3),
                "cd8_dependency": round(t.contribution_cd8 or 0.5, 3),
            }
        })

    by_category = {}
    for item in all_scored:
        cats = item["category"] if isinstance(item["category"], list) else [item["category"]]
        for cat in cats:
            by_category.setdefault(cat, []).append(item)

    return {cat: tools[:top_n] for cat, tools in by_category.items()}


# ── Sensitivity Analysis ──────────────────────────────────────────────────────

def run_sensitivity_analysis(ranking: list, n_mc: int = 500, weights: list = None) -> dict | None:
    """
    run_sensitivity_analysis(ranking_B, n_mc=500)
    -> {'top_name':'PRINCE2 Agile', 'robustness_pct':100.0, 'stable':True,
        'runner_up':'PM2 (Comissão Europeia)', 'runner_up_pct':100.0, 'per_criterion':[...7 entries...]}
    """
    if not ranking or len(ranking) < 2:
        return None
    if not all('criteria' in m for m in ranking):
        return None

    CRITERIA = ['c1_responsiveness', 'c2_alignment', 'c3_traceability', 'c4_compliance',
                'c5_pace_criticality', 'c6_integration_risk', 'c7_distributed_support']
    LABELS   = ['C1 Responsiveness', 'C2 Alignment', 'C3 Traceability', 'C4 Compliance',
                'C5 Pace/Criticality', 'C6 Integration Risk', 'C7 Distributed Support']
    N = len(CRITERIA)

    X = np.array([[m['criteria'].get(c, 0.5) for c in CRITERIA] for m in ranking])

    w0 = _resolve_weights(weights, 'MEB', _MEB_WEIGHTS_DEFAULT)

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

    rng = np.random.default_rng(42)
    samples = rng.dirichlet(np.ones(N), size=n_mc)
    top_count = 0
    runner_up_counts: dict[str, int] = {}

    for w in samples:
        ranked = MCDMEngine(method='MAVT').rank(X, w)
        winner_idx = ranked[0][0]
        if winner_idx == current_top:
            top_count += 1
            if len(ranked) > 1:
                name = ranking[ranked[1][0]]['name']
                runner_up_counts[name] = runner_up_counts.get(name, 0) + 1
        else:
            name = ranking[winner_idx]['name']
            runner_up_counts[name] = runner_up_counts.get(name, 0) + 1

    robustness = round(top_count / n_mc, 3)
    runner_up = max(runner_up_counts, key=runner_up_counts.get) if runner_up_counts else None
    runner_up_pct = round(runner_up_counts.get(runner_up, 0) / n_mc * 100, 1) if runner_up else 0.0

    return {
        'top_name': top_name,
        'robustness_score': robustness,
        'robustness_pct': round(robustness * 100, 1),
        'stable': robustness >= 0.60,
        'per_criterion': per_criterion,
        'runner_up': runner_up,
        'runner_up_pct': runner_up_pct,
        'n_simulations': n_mc,
    }
