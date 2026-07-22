import numpy as np
from .mcdm_engine import MCDMEngine

# Default weights over C1-C7 (Stage 3 Level 2 fit criteria). Explicit and
# elicited — never amplified automatically by AdPO/AsPO (see alignment note:
# Level 1 determines admissibility, Level 2 determines preference; the same
# contextual signal must not enter the MAVT matrix through both levels).
_MEB_WEIGHTS_DEFAULT = np.array([0.12, 0.12, 0.18, 0.18, 0.15, 0.13, 0.12])
# Default weights over CD1-CD8 (Stage 4 Level B capability dimensions).
_TEB_WEIGHTS_DEFAULT = np.array([0.15, 0.12, 0.13, 0.10, 0.10, 0.15, 0.15, 0.10])

# Level 2 / Level B criteria — the ONLY columns fed into the MAVT matrix.
_MEB_CRITERIA = ['score_c1_responsiveness', 'score_c2_alignment', 'score_c3_traceability',
                 'score_c4_compliance', 'score_c5_pace_criticality',
                 'score_c6_integration_risk', 'score_c7_distributed_support']
_TEB_CRITERIA = ['contribution_cd1', 'contribution_cd2', 'contribution_cd3', 'contribution_cd4',
                 'contribution_cd5', 'contribution_cd6', 'contribution_cd7', 'contribution_cd8']

# Numeric misfit shown for audit/display only — derived from the Level 1/A
# posture-alignment TIER (exact/adjacent/distant). It is never summed into the
# Level 2/B MAVT score.
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


def build_decision_control_register(approach: str, context_data: dict, agpi: float, aspi: float) -> dict:
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


# ── Posture alignment (Level 1 / Level A classification — audit only) ────────

def _posture_alignment_tier(agpi: float, aspi: float, ag_posture: int, as_posture: int) -> str:
    """
    Chebyshev distance between project (AdPO, AsPO) and candidate posture,
    reduced to a classification tier. Used for Level 1/A admissibility and
    audit display — it must NOT be fed into the Level 2/B MAVT matrix, since
    posture already shaped admissibility here (avoids double-counting the
    same contextual signal).
    """
    delta = max(abs(agpi - ag_posture), abs(aspi - as_posture))
    if delta == 0:
        return 'exact'
    elif delta == 1:
        return 'adjacent'
    else:
        return 'distant'


def _approach_compatible(m_posture: str, approach: str) -> bool:
    """
    approach_compatible(m, approach) — Level 1 admissibility check.
    A methodology whose nominal posture is 'Híbrida' bridges both regimes, and
    an exact match is always compatible. A purely Adaptativa methodology is
    incompatible with a Preditiva approach and vice-versa.
    """
    if not m_posture or not approach:
        return True
    if m_posture == approach or m_posture == 'Híbrida' or approach == 'Híbrida':
        return True
    return False


# ── Etapa 3 — Stage 3: Dual-Level Fit ─────────────────────────────────────────

def run_fit_m_level1(decision_control_register: dict, agpi: float, aspi: float,
                     approach: str = 'Híbrida') -> list:
    """
    Level 1 — non-compensatory screening. Determines which methodologies may be
    compared in Level 2. A high score on any criterion cannot compensate for
    failing admissibility here. Applies, in order:
      (a) Binding constraints (hard)      — regulatory_compatible
      (b) Acceptance thresholds           — requires_fixed_scope: binary
          exclusion, enforced here rather than as a Level 2 score penalty
      (c) candidate_role compatibility    — excludes reference/normative
          overlays and complementary-engineering methods from competing as an
          autonomous primary methodological envelope
      (d) approach compatibility          — excludes methodologies whose
          nominal posture directly contradicts the resolved approach
      (e) posture alignment               — Chebyshev distance reduced to a
          tier; 'distant' is excluded here (incompatible), 'exact'/'adjacent'
          pass through and are retained only for audit — never re-scored in
          Level 2

    Returns list of (MethodologyEvidenceBase, alignment_tier) tuples.
    """
    from ..models import MethodologyEvidenceBase

    candidates = MethodologyEvidenceBase.query.filter(
        MethodologyEvidenceBase.is_active == True
    ).all()

    hard_constraints = {c["constraint"]: c["value"]
                        for c in decision_control_register.get("hard", []) if c["scope"] == "M"}
    threshold_constraints = {c["constraint"]: c["value"]
                             for c in decision_control_register.get("threshold", []) if c["scope"] == "M"}

    viable = []
    for m in candidates:
        # (a) Binding constraint: regulatory
        if "regulatory_compatible" in hard_constraints:
            if m.regulatory_compatible != hard_constraints["regulatory_compatible"]:
                continue

        # (b) Acceptance threshold: requires_fixed_scope — binary, not compensatory
        if "requires_fixed_scope" in threshold_constraints:
            required = threshold_constraints["requires_fixed_scope"]
            has_scope = m.requires_fixed_scope or False
            if required and not has_scope:
                continue

        # (c) candidate_role — only candidates eligible as a primary envelope compete
        if m.eligible_as_primary_envelope is False:
            continue

        # (d) approach compatibility
        if not _approach_compatible(m.posture, approach):
            continue

        # (e) posture alignment — 'distant' is incompatible, excluded here
        tier = _posture_alignment_tier(agpi, aspi, m.ag_posture or 2, m.as_posture or 2)
        if tier == 'distant':
            continue

        viable.append((m, tier))

    return viable


def run_fit_m_level2(viable: list, decision_control_register: dict = None, engine_name: str = 'MAVT') -> list:
    """
    Level 2 — compensatory prioritisation via MAVT over C1-C7 only.
    viable: list of (MethodologyEvidenceBase, alignment_tier) from Level 1.
    Weights are explicit and elicited (MCDMWeights('MEB')); there is no
    automatic reweighting by AdPO/AsPO and no tier/notoriety bonus — both were
    channels through which the same contextual signal re-entered the score.
    Returns ranked list of dicts: [{id, code, name, posture, score, criteria}]
    """
    if not viable:
        return []

    X = np.array([[getattr(m, c) or 0.5 for c in _MEB_CRITERIA] for m, _ in viable])
    weights = _load_weights('MEB', _MEB_WEIGHTS_DEFAULT)

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
            "tier": m.tier,
            "score": round(score, 4),
            "misfit": _MISFIT_BY_TIER.get(tier, 0.7),        # audit only — not part of the score
            "posture_alignment_tier": tier,
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


# ── Etapa 4 ───────────────────────────────────────────────────────────────────

def run_fit_t_level_a(selected_meth, decision_control_register: dict, agpi: float, aspi: float,
                      budget_eur: float = None) -> list:
    """
    Filter TEB by Hard constraints, methodology and posture compatibility.
    selected_meth: MethodologyEvidenceBase object
    Returns list of ToolEvidenceBase objects that passed.
    """
    from ..models import ToolEvidenceBase

    tools = ToolEvidenceBase.query.filter_by(is_active=True).all()
    hard_t = {c["constraint"]: c["value"]
              for c in decision_control_register.get("hard", []) if c["scope"] == "T"}

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


def run_fit_t_level_b(viable_tools: list, engine_name: str = 'MAVT', top_n: int = 3) -> dict:
    """
    Level B — compensatory prioritisation via MAVT over CD1-CD8 only.
    viable_tools: list of ToolEvidenceBase from Level A (already admissible).
    Weights are explicit and elicited (MCDMWeights('TEB')); no posture/context
    alignment column is fed into the matrix (posture compatibility was already
    enforced in Level A — see run_fit_t_level_a).
    Returns top_n ranked tools per category so the user can choose.
    Format: {category: [tool_dict, ...]} sorted by score descending.
    """
    if not viable_tools:
        return {}

    X = np.array([[getattr(t, c) or 0.5 for c in _TEB_CRITERIA] for t in viable_tools])

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

    # Group by category, keep top_n per category (already sorted by score from engine)
    by_category = {}
    for item in all_scored:
        cats = item["category"] if isinstance(item["category"], list) else [item["category"]]
        for cat in cats:
            by_category.setdefault(cat, []).append(item)

    return {cat: tools[:top_n] for cat, tools in by_category.items()}


# ── Sensitivity Analysis ──────────────────────────────────────────────────────

def run_sensitivity_analysis(ranking: list, n_mc: int = 500) -> dict | None:
    """
    MCDM sensitivity analysis for the methodology ranking, over the explicit
    C1-C7 weight vector actually used in Level 2 (no AdPO/AsPO reweighting).

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

    CRITERIA = ['c1_responsiveness', 'c2_alignment', 'c3_traceability', 'c4_compliance',
                'c5_pace_criticality', 'c6_integration_risk', 'c7_distributed_support']
    LABELS   = ['C1 Responsiveness', 'C2 Alignment', 'C3 Traceability', 'C4 Compliance',
                'C5 Pace/Criticality', 'C6 Integration Risk', 'C7 Distributed Support']
    N = len(CRITERIA)

    X = np.array([[m['criteria'].get(c, 0.5) for c in CRITERIA] for m in ranking])

    w0 = _load_weights('MEB', _MEB_WEIGHTS_DEFAULT)

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
