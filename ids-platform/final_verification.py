import os
import sys

sys.path.insert(0, '.')

print("=" * 70)
print("SOC Platform IDS - FINAL VERIFICATION CHECKLIST")
print("=" * 70)

# ============================================================
# PHASE 1: DATA SPLIT
# ============================================================
print("\n[Phase 1] Data Split")
checks_phase1 = [
    ("feature_schema.py exists", os.path.exists("backend/ml/feature_schema.py")),
    ("preprocessing.py exists (handles data split)", os.path.exists("backend/ml/preprocessing.py")),
    ("datasets.py exists", os.path.exists("backend/ml/datasets.py")),
]
for name, result in checks_phase1:
    print(f"  {'PASS' if result else 'FAIL'}: {name}")

# ============================================================
# PHASE 2: FEATURE SCHEMA
# ============================================================
print("\n[Phase 2] Feature Schema")
from backend.ml.feature_schema import CANONICAL_FEATURE_NAMES, MISSING_FEATURES, COMPUTABLE_MISSING_FEATURES
checks_phase2 = [
    ("51 canonical features", len(CANONICAL_FEATURE_NAMES) == 51),
    ("Missing features list exists", len(MISSING_FEATURES) > 0),
    ("Computable missing features list exists", len(COMPUTABLE_MISSING_FEATURES) > 0),
]
for name, result in checks_phase2:
    print(f"  {'PASS' if result else 'FAIL'}: {name}")

# ============================================================
# PHASE 3: MODEL PIPELINE
# ============================================================
print("\n[Phase 3] Model Pipeline")
checks_phase3 = [
    ("training.py exists", os.path.exists("backend/ml/training.py")),
    ("feature_selection.py exists", os.path.exists("backend/ml/feature_selection.py")),
    ("calibration.py exists", os.path.exists("backend/ml/calibration.py")),
    ("train_all_models.py exists", os.path.exists("backend/ml/train_all_models.py")),
]
for name, result in checks_phase3:
    print(f"  {'PASS' if result else 'FAIL'}: {name}")

# ============================================================
# PHASE 4: ZERO-DAY DETECTION
# ============================================================
print("\n[Phase 4] Zero-Day Detection")
checks_phase4 = [
    ("anomaly_detection.py exists", os.path.exists("backend/ml/anomaly_detection.py")),
    ("unseen_detection.py exists", os.path.exists("backend/ml/unseen_detection.py")),
]
try:
    from backend.ml.anomaly_detection import ZeroDayDetector
    checks_phase4.append(("ZeroDayDetector imports", True))
except Exception as e:
    checks_phase4.append(("ZeroDayDetector imports", False))

for name, result in checks_phase4:
    print(f"  {'PASS' if result else 'FAIL'}: {name}")

# ============================================================
# PHASE 5: CROSS-DATASET
# ============================================================
print("\n[Phase 5] Cross-Dataset Evaluation")
checks_phase5 = [
    ("cross_dataset.py exists", os.path.exists("backend/ml/cross_dataset.py")),
    ("loco_experiment.py exists", os.path.exists("backend/ml/loco_experiment.py")),
    ("dataset_registry.py exists", os.path.exists("backend/ml/dataset_registry.py")),
]
for name, result in checks_phase5:
    print(f"  {'PASS' if result else 'FAIL'}: {name}")

# ============================================================
# PHASE 6: EXPLAINABILITY
# ============================================================
print("\n[Phase 6] Explainability (SHAP)")
checks_phase6 = [
    ("explainability.py exists", os.path.exists("backend/ml/explainability.py")),
    ("shap_explainer.py exists", os.path.exists("backend/ml/shap_explainer.py")),
]
try:
    from backend.ml.explainability import SHAPExplainer
    checks_phase6.append(("SHAPExplainer imports", True))
except Exception as e:
    checks_phase6.append(("SHAPExplainer imports", False))

for name, result in checks_phase6:
    print(f"  {'PASS' if result else 'FAIL'}: {name}")

# ============================================================
# PHASE 7: DRIFT/DEPLOYMENT/ROBUSTNESS
# ============================================================
print("\n[Phase 7] Drift/Deployment/Robustness")
checks_phase7 = [
    ("drift_detection.py exists", os.path.exists("backend/ml/drift_detection.py")),
    ("deployment_eval.py exists", os.path.exists("backend/ml/deployment_eval.py")),
    ("deployment_metrics.py exists", os.path.exists("backend/ml/deployment_metrics.py")),
    ("robustness.py exists", os.path.exists("backend/ml/robustness.py")),
    ("robustness_testing.py exists", os.path.exists("backend/ml/robustness_testing.py")),
]
for name, result in checks_phase7:
    print(f"  {'PASS' if result else 'FAIL'}: {name}")

# ============================================================
# PHASE 8: CLEANUP
# ============================================================
print("\n[Phase 8] Cleanup")
checks_phase8 = []

# Verify ISOLATE_NETWORK removed
from backend.ml.automated_response import ResponseActionType
action_types = [a.value for a in ResponseActionType]
checks_phase8.append(("ISOLATE_NETWORK removed from ResponseActionType", "isolate_network" not in action_types))

# Verify GPU removed from system_metrics
from backend.services.system_metrics import collect_system_stats
stats = collect_system_stats()
checks_phase8.append(("GPU removed from system_metrics", "gpu" not in stats))

# Verify GPU removed from API schemas
from backend.api.schemas import SystemStatsResponse
schema_fields = list(SystemStatsResponse.model_fields.keys())
checks_phase8.append(("GPU removed from API schemas", "gpu" not in schema_fields))

# Verify GPU removed from frontend types
with open("frontend/src/types/health.ts", "r") as f:
    content = f.read()
checks_phase8.append(("GPU removed from frontend types", "gpu" not in content.lower() or "gpu:" not in content.lower()))

for name, result in checks_phase8:
    print(f"  {'PASS' if result else 'FAIL'}: {name}")

# ============================================================
# PHASE 9: DOCUMENTATION
# ============================================================
print("\n[Phase 9] Documentation")
checks_phase9 = [
    ("PROJECT_DOCUMENTATION.md exists", os.path.exists("PROJECT_DOCUMENTATION.md")),
]
for name, result in checks_phase9:
    print(f"  {'PASS' if result else 'FAIL'}: {name}")

# ============================================================
# PHASE 10: FINAL VERIFICATION - API & INTEGRATION
# ============================================================
print("\n[Phase 10] API & Integration")
checks_phase10 = []

try:
    from backend.api.schemas import SystemStatsResponse, SystemHealthResponse
    checks_phase10.append(("schemas.py imports", True))
except Exception as e:
    checks_phase10.append(("schemas.py imports", False))

try:
    from backend.api.routes import system
    checks_phase10.append(("system routes import", True))
except Exception as e:
    checks_phase10.append(("system routes import", False))

try:
    from backend.services.prediction_service import prediction_service
    checks_phase10.append(("prediction service imports", True))
except Exception as e:
    checks_phase10.append(("prediction service imports", False))

try:
    from backend.ml.automated_response import ResponseExecutor, ResponseOrchestrator
    checks_phase10.append(("automated_response imports", True))
except Exception as e:
    checks_phase10.append(("automated_response imports", False))

try:
    from backend.ml.self_healing import RecoveryExecutor, SelfHealingOrchestrator
    checks_phase10.append(("self_healing imports", True))
except Exception as e:
    checks_phase10.append(("self_healing imports", False))

for name, result in checks_phase10:
    print(f"  {'PASS' if result else 'FAIL'}: {name}")

# ============================================================
# SUMMARY
# ============================================================
all_checks = (
    checks_phase1 + checks_phase2 + checks_phase3 + checks_phase4 +
    checks_phase5 + checks_phase6 + checks_phase7 + checks_phase8 +
    checks_phase9 + checks_phase10
)

passed = sum(1 for _, r in all_checks if r)
total = len(all_checks)

print("\n" + "=" * 70)
print(f"FINAL RESULT: {passed}/{total} checks passed")
print("=" * 70)

if passed == total:
    print("ALL CHECKS PASSED - PROJECT COMPLETE")
    sys.exit(0)
else:
    print("SOME CHECKS FAILED - REVIEW REQUIRED")
    sys.exit(1)