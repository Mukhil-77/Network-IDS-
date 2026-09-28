import sys
sys.path.insert(0, r'C:\Users\Mukhil\Downloads\files\ids-platform')
import os
os.chdir(r'C:\Users\Mukhil\Downloads\files\ids-platform')

from backend.ml.shap_explainer import create_shap_explainer
from backend.ml.artifacts import load_model_bundle
import pandas as pd
import numpy as np

bundle = load_model_bundle('models/v4')
model = bundle['model']
feature_names = bundle['feature_names']
print('Model:', type(model).__name__)

explainer = create_shap_explainer(model_path='models/v4')
print('Explainer type:', type(explainer._explainer).__name__)

np.random.seed(42)
sample = pd.DataFrame([np.random.randn(len(bundle["feature_names"]))], columns=bundle['feature_names'])

# Get predicted class from model
pred = model.predict(sample)
pred_class = pred[0]
print('Predicted class:', pred_class)

exp = create_shap_explainer(model_path='models/v4').explain_instance(sample.iloc[0], predicted_class=pred_class)
print('Explanation generated')
print('Top features:', len(exp.top_features))
for f in exp.top_features[:3]:
    print(f'  {f["feature"]}: shap={f["shap_value"]:.4f}, impact={f["impact"]}')