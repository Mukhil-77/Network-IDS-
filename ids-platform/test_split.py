import pandas as pd
import numpy as np

np.random.seed(42)
n = 20000
df = pd.DataFrame({
    'PC1': np.random.randn(n),
    'PC2': np.random.randn(n),
    'PC3': np.random.randn(n),
    'Attack Type': np.random.choice(['BENIGN', 'DoS', 'DDoS', 'Port Scan', 'Bot', 'Brute Force'], n, p=[0.5, 0.1, 0.1, 0.1, 0.1, 0.1]),
    'day': np.random.choice(['Mon', 'Tue', 'Wed', 'Thu', 'Fri'], n),
    'timestamp': np.arange(n) * 0.01
})

from backend.ml.training import prepare_multiclass_dataset_chrono
dataset = prepare_multiclass_dataset_chrono(
    pd.DataFrame({
        'PC1': np.random.randn(20000),
        'PC2': np.random.randn(20000),
        'PC3': np.random.randn(20000),
        'Attack Type': np.random.choice(['BENIGN', 'DoS', 'DDoS', 'Port Scan', 'Bot', 'Brute Force'], 20000, p=[0.5, 0.1, 0.1, 0.1, 0.1, 0.1]),
        'day': np.random.choice(['Mon', 'Tue', 'Wed', 'Thu', 'Fri'], 20000),
        'timestamp': np.arange(20000) * 0.01
    })
)
print('Train shape:', dataset.X_train.shape)
print('Test shape:', dataset.X_test.shape)

# Check for data leakage
train_indices = set(dataset.X_train.index)
test_indices = set(dataset.X_test.index)
overlap = train_indices & test_indices
print(f'Row overlap between train and test: {len(overlap)}')