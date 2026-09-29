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

capped = df.copy()
print('Original shape:', capped.shape)
print('Index type:', type(capped.index))
print('Index has duplicates:', capped.index.duplicated().any())
print('Index unique:', capped.index.is_unique)
print('Timestamp unique:', capped['timestamp'].nunique() == len(capped))

# Check day column
print('Days:', capped['day'].unique())

# Test split for one day
day = 'Mon'
day_df = capped[capped['day'] == day].copy()
print('Day Mon shape:', day_df.shape)
print('Day Mon index unique:', day_df.index.is_unique)
print('Day Mon timestamp unique:', day_df['timestamp'].nunique() == len(day_df))

if 'timestamp' not in day_df.columns:
    raise ValueError(f'Day Mon data missing timestamp column')

day_df = day_df.sort_values('timestamp')
split_idx = int(len(day_df) * 0.7)
train_day = day_df.iloc[:split_idx].copy()
test_day = day_df.iloc[split_idx:].copy()

train_indices = set(train_day.index)
test_indices = set(test_day.index)
overlap = train_indices & test_indices
print(f'Day Mon: train={len(train_day)}, test={len(test_day)}, overlap={len(overlap)}')

if overlap:
    print('Overlap indices:', list(overlap)[:10])
    print('Train indices sample:', list(train_indices)[:10])
    print('Test indices sample:', list(test_indices)[:10])
    
    # Check if indices are actually the same objects
    for idx in list(overlap)[:5]:
        train_row = train_day.loc[idx] if idx in train_indices else None
        test_row = test_day.loc[idx] if idx in test_indices else None
        print(f'  Index {idx}: train_row={train_row is not None}, test_row={test_row is not None}')
        if train_row is not None and test_row is not None:
            print(f'  Are they equal? {train_row.equals(test_row)}')
            print(f'  Train row: {train_row.values[:5]}')
            print(f'  Test row: {test_row.values[:5]}')