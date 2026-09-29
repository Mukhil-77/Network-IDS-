import sys
sys.path.insert(0, '.')
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

from backend.ml.loco_experiment import run_loco_experiment
results = run_loco_experiment(
    data_dir='data/raw',
    attack_families=['DoS', 'DDoS', 'Port Scan'],
    split_mode='chrono'
)
print('LOCO Results:')
for r in results:
    print('  ' + r['held_out_class'] + ': recall=' + str(round(r['held_out_recall'], 3)) + ', f1=' + str(round(r['held_out_f1'], 3)) + ', benign_fpr=' + str(round(r['benign_fpr'], 4)))