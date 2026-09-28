import sys
sys.path.insert(0, r'C:\Users\Mukhil\Downloads\files\ids-platform')
import os
os.chdir(r'C:\Users\Mukhil\Downloads\files\ids-platform')

from backend.ml.threshold_tuning import ThresholdOptimizer, run_threshold_experiment, SensitivityLevel
from backend.ml.training import prepare_multiclass_dataset, train_all_multiclass_models
import pandas as pd
import numpy as np

np.random.seed(42)
n_samples = 1000
n_features = 10
X = np.random.randn(n_samples, n_features)
y = np.random.choice(['BENIGN', 'DoS', 'PortScan', 'DDoS'], size=n_samples, p=[0.5, 0.2, 0.2, 0.1])
df = pd.DataFrame(X, columns=[f'PC{i}' for i in range(n_features)])
df['Attack Type'] = y

dataset = prepare_multiclass_dataset(df, min_class_count=50, cap_threshold=1000, cap_per_class=500, test_size=0.3, random_state=42)

from backend.ml.training import train_knn_models
models = train_knn_models(dataset)
model = models[0].model

from backend.ml.threshold_tuning import ThresholdOptimizer, run_threshold_experiment
optimizer = ThresholdOptimizer(model, dataset.X_test, dataset.y_test)

print('Testing threshold optimizer...')
metrics = optimizer.evaluate_threshold(0.5)
print(f'Baseline (0.5): accuracy={metrics.accuracy:.4f}, f1_macro={metrics.f1_macro:.4f}, fpr={metrics.fpr:.4f}, fnr={metrics.fnr:.4f}')

for t in [0.3, 0.5, 0.7]:
    m = optimizer.evaluate_threshold(t)
    print(f'Threshold {t:.1f}: acc={m.accuracy:.3f}, f1={m.f1_macro:.3f}, fpr={m.fpr:.3f}, fnr={m.fnr:.3f}')

results = run_threshold_experiment(model, dataset.X_test, dataset.y_test)
for sens, exp in results.items():
    print(f'\n{sens}:')
    print(f'  Threshold: {exp.config.confidence_threshold:.2f}')
    print(f'  F1-macro: {exp.baseline_metrics.f1_macro:.4f} -> {exp.optimized_metrics.f1_macro:.4f} ({exp.improvement["f1_macro"]:+.4f})')
    print(f'  FPR: {exp.baseline_metrics.fpr:.4f} -> {exp.optimized_metrics.fpr:.4f} ({exp.improvement["fpr_change"]:+.4f})')
    print(f'  FNR: {exp.baseline_metrics.fnr:.4f} -> {exp.optimized_metrics.fnr:.4f} ({exp.improvement["fnr_change"]:+.4f})')