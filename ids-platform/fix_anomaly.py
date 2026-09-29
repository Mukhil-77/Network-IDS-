import re

with open('backend/ml/anomaly_detection.py', 'r') as f:
    content = f.read()

# Fix 1: Fix the return statement indentation in compare_detection_methods
content = content.replace(
    'return results_dict\n        """Save both models."""',
    '        return results_dict\n        """Save both models."""'
)

# Fix 2: Fix the save method indentation
content = content.replace(
    '    def save(self, path: Union[str, Path]) -> None:\n        """Save both models."""\n        import joblib\n        joblib.dump({\n            \'supervised_model\': self.supervised_model,\n            \'anomaly_detector\': self.anomaly_detector,\n            \'unknown_threshold\': self.unknown_threshold,\n            \'low_confidence_threshold\': self.low_confidence_threshold,\n        }, path)\n        logger.info(f"Saved ZeroDayDetector to {path}")\n    def load(cls, path: Union[str, Path]) -> "ZeroDayDetector":',
    '    def save(self, path: Union[str, Path]) -> None:\n        """Save both models."""\n        import joblib\n        joblib.dump({\n            \'supervised_model\': self.supervised_model,\n            \'anomaly_detector\': self.anomaly_detector,\n            \'unknown_threshold\': self.unknown_threshold,\n            \'low_confidence_threshold\': self.low_confidence_threshold,\n        }, path)\n        logger.info(f"Saved ZeroDayDetector to {path}")'
)

with open('backend/ml/anomaly_detection.py', 'w') as f:
    f.write(content)

print('Fixed')