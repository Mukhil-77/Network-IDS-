"""Machine learning pipeline: preprocessing, feature engineering, training, inference."""

from backend.ml.dataset_registry import (
    DatasetConfig,
    DatasetLoader,
    DatasetRegistry,
    FeatureMapping,
    CICIDS2017Loader,
    UNSWNB15Loader,
    dataset_registry,
)
from backend.ml.cross_dataset import (
    CrossDatasetResult,
    run_cross_dataset_experiment,
    run_bidirectional_experiment,
    compute_degradation,
)
from backend.ml.unseen_detection import (
    UnseenDetectionResult,
    UnseenPrediction,
    UnseenDetector,
    prepare_leave_one_class_out_dataset,
    run_leave_one_class_out_experiment,
    evaluate_unseen_detection,
    find_optimal_unknown_threshold,
)
from backend.ml.severity import (
    SeverityLevel,
    get_severity,
    get_severity_score,
    get_severity_color,
    severity_to_risk_score,
    get_risk_level,
    get_risk_color,
)
from backend.ml.risk_scoring import (
    RiskLevel,
    RiskFactors,
    PredictionResult,
    RiskScorer,
    ConfidenceRiskScorer,
    RISK_WEIGHTS,
    ATTACK_SEVERITY_MAP,
    get_attack_severity,
)
from backend.ml.shap_explainer import (
    SHAPExplanation,
    GlobalSHAPSummary,
    SHAPExplainer,
    create_shap_explainer,
    generate_explanation_text,
    format_explanation_for_ui,
    SHAP_AVAILABLE,
)
