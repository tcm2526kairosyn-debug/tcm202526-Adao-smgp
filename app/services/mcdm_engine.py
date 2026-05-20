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
        """Weighted sum on min-max normalised matrix. V_k = sum(w_j * x_kj_norm)."""
        X = X.astype(float)
        if X.shape[0] == 1:
            # Single alternative — score is the raw weighted sum (no normalization needed)
            scores = X @ weights
            return [(0, float(scores[0]))]
        col_min = X.min(axis=0)
        col_max = X.max(axis=0)
        denom = col_max - col_min
        denom[denom == 0] = 1  # avoid division by zero when all scores equal
        X_norm = (X - col_min) / denom
        scores = X_norm @ weights
        return sorted(enumerate(scores.tolist()), key=lambda t: t[1], reverse=True)

    def _ahp(self, X: np.ndarray, weights: np.ndarray) -> list[tuple[int, float]]:
        """AHP stub — falls back to MAVT until pairwise matrix input is implemented."""
        return self._mavt(X, weights)
