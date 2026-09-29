import numpy as np


class MCDMEngine:
    """MCDMEngine(method='MAVT')"""

    def __init__(self, method: str = 'MAVT'):
        if method not in ('MAVT', 'AHP'):
            raise ValueError(f"MCDM method '{method}' not supported. Use MAVT or AHP.")
        self.method = method

    def rank(self, X: np.ndarray, weights: np.ndarray) -> list[tuple[int, float]]:
        """
        rank(X=[[0.75,0.75,1.0,0.75,0.75,0.5,0.5],[0.5,0.75,1.0,0.75,0.75,0.5,0.5]],
             weights=[0.12,0.12,0.18,0.18,0.15,0.13,0.12]) -> [(0, 0.7325), (1, 0.7025)]
        """
        if self.method == 'MAVT':
            return self._mavt(X, weights)
        return self._ahp(X, weights)

    def _mavt(self, X: np.ndarray, weights: np.ndarray) -> list[tuple[int, float]]:
        """
        _mavt(X=[[0.75,0.75,1.0,0.75,0.75,0.5,0.5],[0.5,0.75,1.0,0.75,0.75,0.5,0.5]],
              weights=[0.12,0.12,0.18,0.18,0.15,0.13,0.12]) -> [(0, 0.7325), (1, 0.7025)]
        """
        X = X.astype(float)
        scores = X @ weights
        return sorted(enumerate(scores.tolist()), key=lambda t: t[1], reverse=True)

    def _ahp(self, X: np.ndarray, weights: np.ndarray) -> list[tuple[int, float]]:
        """_ahp(X, weights) -> self._mavt(X, weights)"""
        return self._mavt(X, weights)
