"""Machine learning pipeline: training, inference, validation."""

from backend.ml.artifacts import (
    ArtifactNotFoundError,
    load_model_bundle,
    save_model_bundle,
    latest_version_dir,
    list_versions,
    load_metadata,
    load_feature_names,
    load_scaler,
    load_model,
    load_encoder,
    load_imputer,
    load_cat_encoders,
)

from backend.ml.predictor import (
    Predictor,
    get_predictor,
    reload_predictor,
    reset_predictor,
    is_loaded,
    ModelNotLoadedError,
)

from backend.ml.inference import (
    predict,
    PredictionError,
    FeatureValidationFailed,
    InferencePipelineError,
)

from backend.ml.validator import (
    validate_features,
    validate_and_raise,
    build_ordered_frame,
    FeatureValidationError,
)

from backend.ml.schemas import (
    PredictionRequest,
    PredictionResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
    ModelMetadata,
)

from backend.ml.severity import (
    SeverityLevel,
    get_severity,
    ATTACK_SEVERITY_MAP as DEFAULT_SEVERITY_MAP,
)

from backend.ml.constants import (
    PROJECT_VERSION,
    RANDOM_STATE,
    TEST_SIZE,
)

from backend.ml.encoders import LabelEncoderExt

from backend.ml.feature_schema import (
    CANONICAL_FEATURE_NAMES,
    get_canonical_features,
    validate_feature_set,
)

# Re-export core modules
from backend.ml import artifacts, predictor, inference, validator, schemas, severity, constants, encoders, feature_schema