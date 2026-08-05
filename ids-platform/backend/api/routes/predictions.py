"""
ML prediction endpoint (documented path: api/routes/predictions.py).

The implementation lives in api/routes/predict.py (POST /predict): it takes
a PredictionRequest of raw flow features, runs them through the trained
scaler -> IncrementalPCA -> RandomForest pipeline, and returns a
PredictionResponse with label, confidence, severity and latency.

This module re-exports that router so the documented module name resolves to
a real, importable router. It is not included separately in api_router -
predict.router (identical object) already is, so endpoints are not
registered twice.
"""

from backend.api.routes.predict import router

__all__ = ["router"]
