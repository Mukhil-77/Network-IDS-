"""Machine learning pipeline: preprocessing, feature engineering, training, inference."""

# Unseen detection
from backend.ml.unseen_detection import (
    UnseenDetectionResult,
    UnseenPrediction,
    UnseenDetector,
    prepare_leave_one_class_out_dataset,
    run_leave_one_class_out_experiment,
    evaluate_unseen_detection,
    find_optimal_unknown_threshold,
)

# Severity
from backend.ml.severity import (
    SeverityLevel,
    get_severity,
    get_severity_score,
    get_severity_color,
    severity_to_risk_score,
    get_risk_level,
    get_risk_color,
)

# Risk scoring
from backend.ml.risk_scoring import (
    RiskTier,
    SeverityLevel as RiskSeverityLevel,
    ThreatIntelContext,
    AssetContext,
    AlertContext,
    RiskScoreResult,
    RiskScorer,
    ATTACK_SEVERITY_MAP,
    get_attack_severity,
    compute_risk_score_for_alert,
)

# Explainability
from backend.ml.explainability import (
    FeatureContribution,
    ExplanationResult,
    PCAFeatureMapper,
    SHAPExplainer,
    explain_alert,
)

# Legacy SHAP explainer (backward compatibility)
from backend.ml.shap_explainer import (
    SHAPExplanation as LegacySHAPExplanation,
    GlobalSHAPSummary,
    SHAPExplainer as LegacySHAPExplainer,
    create_shap_explainer,
    generate_explanation_text,
    format_explanation_for_ui,
    SHAP_AVAILABLE,
)

# Calibration
from backend.ml.calibration import (
    CalibrationResult,
    expected_calibration_error,
    brier_score,
    compute_reliability_diagram,
    ConfidenceCalibrator,
    calibrate_model,
    compute_ece_per_class,
)

# Alert prioritization
from backend.ml.alert_prioritization import (
    PriorityLevel,
    PrioritizedAlert,
    Incident,
    AlertPrioritizer,
    prioritize_alerts_batch,
    create_incidents_from_alerts,
)

# Monitoring
from backend.ml.monitoring import (
    MetricPoint,
    TimeSeriesMetric,
    TimeWindow,
    MonitoringSystem,
    monitoring_system,
)

# Drift detection
from backend.ml.drift_detection import (
    DriftSeverity,
    DriftReport,
    ModelHealthReport,
    DriftDetector,
    PerformanceMonitor,
)

# Automated response
from backend.ml.automated_response import (
    ResponseActionType,
    ResponseStatus,
    ResponseScope,
    ResponseAction,
    ResponsePolicy,
    ResponseExecutionResult,
    ResponseExecutor,
    ResponseOrchestrator,
    DEFAULT_RESPONSE_POLICIES,
)

# Self-healing
from backend.ml.self_healing import (
    RecoveryStatus,
    RecoveryTrigger,
    RecoveryAction,
    RecoveryPlan,
    RecoveryExecutor,
    SelfHealingOrchestrator,
    DEFAULT_RECOVERY_PLANS,
)

# Deployment evaluation
from backend.ml.deployment_eval import (
    LatencyMetrics,
    ThroughputMetrics,
    ResourceMetrics,
    DeploymentEvaluationResult,
    LatencyTracker,
    ThroughputTracker,
    ResourceMonitor,
    DeploymentEvaluator,
    deployment_evaluator,
)

# Dataset abstraction
from backend.ml.datasets import (
    DatasetType,
    DatasetInfo,
    FeatureMapping,
    BaseDatasetLoader,
    CICIDS2017Loader,
    DatasetRegistry,
    dataset_registry,
    load_dataset_for_cross_evaluation,
    compute_cross_dataset_features,
    harmonize_all_datasets,
    get_cross_dataset_report,
)

# Cross-dataset evaluation
from backend.ml.cross_dataset import (
    CrossDatasetResult,
    run_cross_dataset_evaluation,
)

# Unseen detection
from backend.ml.unseen_detection import (
    UnseenDetectionResult,
    UnseenPrediction,
    UnseenDetector,
    prepare_leave_one_class_out_dataset,
    run_leave_one_class_out_experiment,
    evaluate_unseen_detection,
    find_optimal_unknown_threshold,
)

# Experiment dashboard
from backend.ml.experiment_dashboard import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentRunner,
    create_standard_experiments,
)

# Robustness
from backend.ml.robustness import (
    PerturbationType,
    PerturbationConfig,
    RobustnessResult,
    RobustnessTester,
    RobustnessGate,
)

# Self-healing
from backend.ml.self_healing import (
    RecoveryStatus,
    RecoveryTrigger,
    RecoveryAction,
    RecoveryPlan,
    RecoveryExecutor,
    SelfHealingOrchestrator,
    DEFAULT_RECOVERY_PLANS,
)

# Deployment evaluation
from backend.ml.deployment_eval import (
    LatencyMetrics,
    ThroughputMetrics,
    ResourceMetrics,
    DeploymentEvaluationResult,
    LatencyTracker,
    ThroughputTracker,
    ResourceMonitor,
    DeploymentEvaluator,
    deployment_evaluator,
)

# Robustness
from backend.ml.robustness import (
    PerturbationType,
    PerturbationConfig,
    RobustnessResult,
    RobustnessTester,
    RobustnessGate,
)

# Self-healing
from backend.ml.self_healing import (
    RecoveryStatus,
    RecoveryTrigger,
    RecoveryAction,
    RecoveryPlan,
    RecoveryExecutor,
    SelfHealingOrchestrator,
    DEFAULT_RECOVERY_PLANS,
)

# Deployment evaluation
from backend.ml.deployment_eval import (
    LatencyMetrics,
    ThroughputMetrics,
    ResourceMetrics,
    DeploymentEvaluationResult,
    LatencyTracker,
    ThroughputTracker,
    ResourceMonitor,
    DeploymentEvaluator,
    deployment_evaluator,
)

# Risk scoring
from backend.ml.risk_scoring import (
    RiskTier,
    SeverityLevel as RiskSeverityLevel,
    ThreatIntelContext,
    AssetContext,
    AlertContext,
    RiskScoreResult,
    RiskScorer,
    ATTACK_SEVERITY_MAP,
    get_attack_severity,
    compute_risk_score_for_alert,
)

# Explainability
from backend.ml.explainability import (
    FeatureContribution,
    ExplanationResult,
    PCAFeatureMapper,
    SHAPExplainer,
    explain_alert,
)

# Legacy SHAP explainer (backward compatibility)
from backend.ml.shap_explainer import (
    SHAPExplanation as LegacySHAPExplanation,
    GlobalSHAPSummary,
    SHAPExplainer as LegacySHAPExplainer,
    create_shap_explainer,
    generate_explanation_text,
    format_explanation_for_ui,
    SHAP_AVAILABLE,
)

# Calibration
from backend.ml.calibration import (
    CalibrationResult,
    expected_calibration_error,
    brier_score,
    compute_reliability_diagram,
    ConfidenceCalibrator,
    calibrate_model,
    compute_ece_per_class,
)

# Severity
from backend.ml.severity import (
    SeverityLevel,
    get_severity,
    get_severity_score,
    get_severity_color,
    severity_to_risk_score,
    get_risk_level,
    get_risk_color,
)

# Risk scoring
from backend.ml.risk_scoring import (
    RiskTier,
    SeverityLevel as RiskSeverityLevel,
    ThreatIntelContext,
    AssetContext,
    AlertContext,
    RiskScoreResult,
    RiskScorer,
    ATTACK_SEVERITY_MAP,
    get_attack_severity,
    compute_risk_score_for_alert,
)

# Explainability
from backend.ml.explainability import (
    FeatureContribution,
    ExplanationResult,
    PCAFeatureMapper,
    SHAPExplainer,
    explain_alert,
)

# Legacy SHAP explainer (backward compatibility)
from backend.ml.shap_explainer import (
    SHAPExplanation as LegacySHAPExplanation,
    GlobalSHAPSummary,
    SHAPExplainer as LegacySHAPExplainer,
    create_shap_explainer,
    generate_explanation_text,
    format_explanation_for_ui,
    SHAP_AVAILABLE,
)

# Calibration
from backend.ml.calibration import (
    CalibrationResult,
    expected_calibration_error,
    brier_score,
    compute_reliability_diagram,
    ConfidenceCalibrator,
    calibrate_model,
    compute_ece_per_class,
)

# Re-export existing modules
from backend.ml import (
    artifacts,
    calibration,
    confidence,
    constants,
    evaluation,
    feature_engineering,
    inference,
    notebook_model,
    predictor,
    preprocessing,
    schemas,
    severity,
    training,
    train_all_models,
    train_one,
    validator,
)