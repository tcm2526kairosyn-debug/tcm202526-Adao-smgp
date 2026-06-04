import numpy as np
from .mcdm_engine import MCDMEngine

# Default weights: [assurance, agility, scalability, hybridisation, posture_alignment]
_MEB_WEIGHTS_DEFAULT = np.array([0.25, 0.25, 0.10, 0.10, 0.30])
# Default weights: [traceability, integration, flow_support, context_alignment]
_TEB_WEIGHTS_DEFAULT = np.array([0.30, 0.25, 0.25, 0.20])


def _load_weights(context: str, fallback: np.ndarray) -> np.ndarray:
    try:
        from ..models import MCDMWeights
        row = MCDMWeights.query.filter_by(context=context, is_active=True).first()
        if row and row.weights:
            return np.array(row.weights)
    except Exception:
        pass
    return fallback


# Keep module-level aliases for backwards compatibility
MEB_WEIGHTS = _MEB_WEIGHTS_DEFAULT
TEB_WEIGHTS = _TEB_WEIGHTS_DEFAULT


# ── Etapa 1 ───────────────────────────────────────────────────────────────────

def compute_indices(context_data: dict) -> tuple[float, float]:
    """
    Compute AgPI and AsPI as ordinal indices {1,2,3,4} per KairoSyn spec (Stage 2).
    Rule: count how many dimensions score >= 3, map that count to {1,2,3,4}.
    AgPI and AsPI are ordinal organisers, not cardinal averages.
    """
    agpi_dims = ['complexity', 'novelty', 'dynamism', 'team_autonomy']
    aspi_dims = ['criticality', 'compliance', 'traceability', 'stakeholder_formality']

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

    return _ordinal(agpi_dims), _ordinal(aspi_dims)


# ── Etapa 2 ───────────────────────────────────────────────────────────────────

def resolve_approach(agpi: float, aspi: float) -> str:
    """Apply KairoSyn transition rules to derive management approach."""
    if agpi >= 2.0 and aspi <= 2.0:
        return "Adaptativa"
    elif aspi >= 3.0 and agpi <= 2.0:
        return "Preditiva"
    else:
        return "Híbrida"


def build_governance_register(approach: str, context_data: dict, agpi: float, aspi: float) -> dict:
    """
    Classify constraints as Hard, Threshold or Soft based on diagnostic scores.
    Scope 'M' = applies to methodology selection.
    Scope 'T' = applies to tool selection.
    """
    register = {"hard": [], "threshold": [], "soft": []}

    compliance = context_data.get('compliance', 1)
    criticality = context_data.get('criticality', 1)
    team_autonomy = context_data.get('team_autonomy', 1)

    if compliance >= 3:
        register["hard"].append({
            "constraint": "regulatory_compatible",
            "value": True,
            "scope": "M",
            "reason": f"Compliance score {compliance}/4 exige conformidade regulatória."
        })
    if compliance >= 4:
        register["hard"].append({
            "constraint": "gdpr_compliant",
            "value": True,
            "scope": "T",
            "reason": "Compliance máximo requer GDPR nas ferramentas."
        })

    if criticality >= 3:
        register["threshold"].append({
            "constraint": "requires_fixed_scope",
            "value": (approach == "Preditiva"),
            "scope": "M",
            "reason": f"Criticidade {criticality}/4 favorece âmbito definido em abordagem Preditiva."
        })

    if team_autonomy >= 3:
        register["soft"].append({
            "constraint": "prefers_low_process_overhead",
            "scope": "M",
            "reason": f"Autonomia de equipa {team_autonomy}/4 favorece metodologias ágeis leves."
        })

    return register


# ── Posture alignment ─────────────────────────────────────────────────────────

def _posture_align_score(agpi: float, aspi: float, ag_posture: int, as_posture: int) -> float:
    """
    Chebyshev distance between project (AgPI, AsPI) and methodology posture.
    delta=0 → 1.0, delta=1 → 0.7, delta>=2 → 0.3
    """
    delta = max(abs(agpi - ag_posture), abs(aspi - as_posture))
    if delta == 0:
        return 1.0
    elif delta == 1:
        return 0.7
    else:
        return 0.3


def _context_align_score(agpi: float, aspi: float, agility_support: int, assurance_support: int) -> float:
    """Same Chebyshev logic for tool context alignment."""
    delta = max(abs(agpi - agility_support), abs(aspi - assurance_support))
    if delta == 0:
        return 1.0
    elif delta == 1:
        return 0.7
    else:
        return 0.3


# ── Etapa 3 ───────────────────────────────────────────────────────────────────

def run_fit_m_level1(governance_register: dict, agpi: float, aspi: float,
                     approach: str = 'Híbrida') -> list:
    """
    Filter MEB by Hard constraints only. All postures pass — posture_alignment
    in Level 2 naturally penalises mismatches without hard exclusion.
    Returns list of (MethodologyEvidenceBase, posture_align_score) tuples.
    """
    from ..models import MethodologyEvidenceBase

    candidates = MethodologyEvidenceBase.query.filter(
        MethodologyEvidenceBase.tier <= 2,
        MethodologyEvidenceBase.is_active == True
    ).all()

    hard_constraints = {c["constraint"]: c["value"]
                        for c in governance_register.get("hard", []) if c["scope"] == "M"}

    viable = []
    for m in candidates:
        # Hard constraint: regulatory
        if "regulatory_compatible" in hard_constraints:
            if m.regulatory_compatible != hard_constraints["regulatory_compatible"]:
                continue

        align_score = _posture_align_score(agpi, aspi,
                                           m.ag_posture or 2, m.as_posture or 2)
        viable.append((m, align_score))

    return viable


def _context_weights(base: np.ndarray, agpi: float, aspi: float) -> np.ndarray:
    """
    Adjust base MEB weights proportionally to AgPI/AsPI context pressure.

    Criteria order: [assurance, agility, scalability, hybridisation, posture_alignment]
    - assurance    scales up with AsPI (formal/governance pressure)
    - agility      scales up with AgPI (speed/flexibility pressure)
    - scalability  scales with average of both
    - hybridisation scales with complement (1 - |a-s|): maximised when balanced
    - posture_alignment is fixed (always important)
    """
    a = (agpi - 1) / 3  # 0..1 — normalised agility pressure
    s = (aspi - 1) / 3  # 0..1 — normalised assurance pressure

    ALPHA = 0.8
    h = 1 - abs(a - s)  # 1.0 when balanced, 0.0 at extremes
    multipliers = np.array([
        1 + ALPHA * s,              # assurance      ← AsPI
        1 + ALPHA * a,              # agility        ← AgPI
        1 + ALPHA * (a + s) / 2,   # scalability    ← both (neutral)
        1 + ALPHA * h,              # hybridisation  ← complement
        1.0,                        # posture_alignment — fixed
    ])
    adjusted = base * multipliers
    return adjusted / adjusted.sum()


def run_fit_m_level2(viable: list, governance_register: dict = None, engine_name: str = 'MAVT',
                     agpi: float = 2.0, aspi: float = 2.0) -> list:
    """
    Build X_M matrix (4 stored + posture_alignment) and rank via MCDM.
    viable: list of (MethodologyEvidenceBase, posture_align_score) from Level 1
    governance_register: dict with threshold constraints to apply as penalty
    Returns ranked list of dicts: [{id, code, name, posture, score, posture_alignment}]
    """
    if not viable:
        return []

    stored_criteria = ['score_assurance', 'score_agility', 'score_scalability', 'score_hybridisation']

    X_stored = np.array([[getattr(m, c) or 0.5 for c in stored_criteria] for m, _ in viable])
    X_align = np.array([[align_score] for _, align_score in viable])
    X = np.hstack([X_stored, X_align])

    base_w = _load_weights('MEB', _MEB_WEIGHTS_DEFAULT)
    weights = _context_weights(base_w, agpi, aspi)

    engine = MCDMEngine(method=engine_name)
    ranked_indices = engine.rank(X, weights)

    _TIER_BONUS = {1: 0.02, 2: 0.0}
    _THRESHOLD_PENALTY = 0.05  # 5% penalty per unmet threshold constraint

    # Extract threshold constraints for methodology selection (scope='M')
    threshold_constraints = {}
    if governance_register:
        for c in governance_register.get("threshold", []):
            if c.get("scope") == "M":
                threshold_constraints[c["constraint"]] = c["value"]

    result = []
    for idx, score in ranked_indices:
        m, align_score = viable[idx]
        adjusted = round(score + _TIER_BONUS.get(m.tier, 0.0), 4)

        # Apply threshold penalties
        penalty = 0.0
        if "requires_fixed_scope" in threshold_constraints:
            required = threshold_constraints["requires_fixed_scope"]
            has_scope = m.requires_fixed_scope or False
            if required and not has_scope:
                penalty += _THRESHOLD_PENALTY
            elif not required and has_scope:
                penalty += _THRESHOLD_PENALTY * 0.5  # lighter penalty if more restrictive than needed

        adjusted_with_penalty = round(max(0.0, adjusted - penalty), 4)

        result.append({
            "id": m.id,
            "code": m.code,
            "name": m.name,
            "posture": m.posture,
            "tier": m.tier,
            "score": adjusted_with_penalty,
            "misfit": round(1.0 - align_score, 3),
            "posture_alignment": align_score,
            "requires_fixed_scope": m.requires_fixed_scope or False,
            "threshold_penalty": round(penalty, 4),
            "description": m.description or "",
            "criteria": {
                "assurance": round(m.score_assurance or 0.5, 3),
                "agility": round(m.score_agility or 0.5, 3),
                "scalability": round(m.score_scalability or 0.5, 3),
                "hybridisation": round(m.score_hybridisation or 0.5, 3),
                "posture_alignment": round(align_score, 3),
            }
        })
    return sorted(result, key=lambda x: x["score"], reverse=True)


# ── Etapa 4 ───────────────────────────────────────────────────────────────────

def run_fit_t_level_a(selected_meth, governance_register: dict, agpi: float, aspi: float,
                      budget_eur: float = None) -> list:
    """
    Filter TEB by Hard constraints, methodology and posture compatibility.
    selected_meth: MethodologyEvidenceBase object
    Returns list of ToolEvidenceBase objects that passed.
    """
    from ..models import ToolEvidenceBase

    tools = ToolEvidenceBase.query.filter_by(is_active=True).all()
    hard_t = {c["constraint"]: c["value"]
              for c in governance_register.get("hard", []) if c["scope"] == "T"}

    viable = []
    for t in tools:
        # Hard constraint: GDPR
        if "gdpr_compliant" in hard_t:
            if t.gdpr_compliant != hard_t["gdpr_compliant"]:
                continue

        # Methodology compatibility
        if selected_meth.code not in (t.compatible_methodologies or []):
            continue

        # Posture compatibility
        if selected_meth.posture not in (t.compatible_postures or []):
            continue

        # Budget constraint (optional)
        if budget_eur is not None and t.cost_monthly_eur > budget_eur:
            continue

        viable.append(t)

    return viable


def run_fit_t_level_b(viable_tools: list, engine_name: str = 'MAVT',
                      agpi: float = 2.0, aspi: float = 2.0) -> list:
    """
    Build MCDM matrix (3 stored + context_alignment) for tools.
    Returns a portfolio (top tool per category).
    """
    if not viable_tools:
        return []

    stored_criteria = ['score_traceability', 'score_integration', 'score_flow_support']

    X_stored = np.array([[getattr(t, c) or 0.5 for c in stored_criteria] for t in viable_tools])
    X_align = np.array([[_context_align_score(agpi, aspi,
                                               t.agility_support or 2,
                                               t.assurance_support or 2)]
                        for t in viable_tools])
    X = np.hstack([X_stored, X_align])

    engine = MCDMEngine(method=engine_name)
    ranked = engine.rank(X, _load_weights('TEB', _TEB_WEIGHTS_DEFAULT))

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
            "score": round(score, 4)
        })

    # Greedy portfolio: pick top-scored tool per category
    portfolio = {}
    for item in all_scored:
        cat = item["category"]
        if cat not in portfolio:
            portfolio[cat] = item

    return list(portfolio.values())


# ── Sensitivity Analysis ──────────────────────────────────────────────────────

def run_sensitivity_analysis(ranking: list, agpi: float, aspi: float,
                              n_mc: int = 500) -> dict | None:
    """
    MCDM sensitivity analysis for the methodology ranking.

    For each weight criterion, sweeps the weight from 0→1 (redistributing others
    proportionally) to find the stability range where the top-ranked methodology
    remains #1. Runs n_mc Monte Carlo simulations with Dirichlet-sampled weight
    vectors for an overall robustness score.

    Returns None if ranking has < 2 alternatives or missing criteria scores.
    """
    if not ranking or len(ranking) < 2:
        return None
    if not all('criteria' in m for m in ranking):
        return None

    CRITERIA = ['assurance', 'agility', 'scalability', 'hybridisation', 'posture_alignment']
    LABELS   = ['Assurance', 'Agility', 'Scalability', 'Hybridisation', 'Postura']
    N = len(CRITERIA)

    X = np.array([[m['criteria'].get(c, 0.5) for c in CRITERIA] for m in ranking])

    base_w = _load_weights('MEB', _MEB_WEIGHTS_DEFAULT)
    w0 = _context_weights(base_w, agpi, aspi)

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

    # Per-criterion stability sweep (step = 0.01)
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

    # Monte Carlo robustness (Dirichlet uniform over weight simplex)
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
