"""
Shared encoder classes for model persistence.
These classes must be importable at load time for joblib to deserialize them.
"""

from sklearn.preprocessing import LabelEncoder


class LabelEncoderExt:
    """LabelEncoder that handles unseen categories by mapping to 'Unknown'."""
    def __init__(self):
        self.label_encoder = LabelEncoder()
        self.classes_ = None

    def fit(self, data):
        self.label_encoder = self.label_encoder.fit(list(data) + ['Unknown'])
        self.classes_ = self.label_encoder.classes_
        return self

    def transform(self, data):
        data = data.astype(str) if hasattr(data, 'astype') else [str(x) for x in data]
        unknown_mask = ~data.isin(self.label_encoder.classes_) if hasattr(data, 'isin') else [x not in self.label_encoder.classes_ for x in data]
        if hasattr(data, 'loc'):
            data = data.copy()
            data[unknown_mask] = 'Unknown'
        else:
            data = ['Unknown' if m else x for x, m in zip(data, unknown_mask)]
        return self.label_encoder.transform(data)

    def fit_transform(self, data):
        return self.fit(data).transform(data)