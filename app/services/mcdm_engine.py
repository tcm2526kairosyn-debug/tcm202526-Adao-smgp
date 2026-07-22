import numpy as np


class MCDMEngine:
    """Pluggable MCDM engine (RF08). Supports MAVT and AHP (stub)."""

    def __init__(self, method: str = 'MAVT'):
        if method not in ('MAVT', 'AHP'):
            raise ValueError(f"MCDM method '{method}' not supported. Use MAVT or AHP.")
        self.method = method

    def rank(self, X: np.ndarray, weights: np.ndarray) -> list[tuple[int, float]]:
        """
        Rank alternatives.

        X       : (n_alternatives, n_criteria) matrix of raw criterion scores
        weights : (n_criteria,) array — must sum to 1
        returns : list of (alternative_index, value_score) sorted descending
        """
        if self.method == 'MAVT':
            return self._mavt(X, weights)
        return self._ahp(X, weights)

    def _mavt(self, X: np.ndarray, weights: np.ndarray) -> list[tuple[int, float]]:
        """
        Weighted sum. V_k = sum(w_j * x_kj).

        X columns are already value functions on a fixed [0,1] scale (e.g. the
        C1-C7 / CD1-CD8 rubric anchors), so no min-max rescaling is applied —
        rescaling over the surviving candidate set would make each score
        depend on which other alternatives happened to pass Level 1/A, an
        artifact the value-function encoding is specifically meant to avoid.
        """
        X = X.astype(float)
        scores = X @ weights
        return sorted(enumerate(scores.tolist()), key=lambda t: t[1], reverse=True)

    def _ahp(self, X: np.ndarray, weights: np.ndarray) -> list[tuple[int, float]]:
        """AHP stub — falls back to MAVT until pairwise matrix input is implemented."""
        return self._mavt(X, weights)
