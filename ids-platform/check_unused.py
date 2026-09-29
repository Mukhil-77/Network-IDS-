import os

for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.py') or f.endswith('.ts') or f.endswith('.tsx') or f.endswith('.json'):
            path = os.path.join(root, f)
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if 'GPU' in content or 'ISOLATE_NETWORK' in content:
                        print(f'{f}: GPU or ISOLATE_NETWORK found')
            except:
                pass