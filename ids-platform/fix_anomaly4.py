with open('backend/ml/anomaly_detection.py', 'r') as f:
    lines = f.readlines()

# Fix the indentation issues
new_lines = []
for i, line in enumerate(open('backend/ml/anomaly_detection.py').readlines()):
    if i == 508:  # 'return results_dict\n' - should be indented by 8 spaces
        new_lines.append('        return results_dict\n')
    elif i == 509:  # empty line
        new_lines.append('\n')
    elif i == 510:  # '    def save(self, path: Union[str, Path]) -> None:'
        new_lines.append('    def save(self, path: Union[str, Path]) -> None:\n')
    elif i == 511:  # '        """Save both models."""'
        new_lines.append('        """Save both models."""\n')
    elif i == 512:  # '        import joblib\n'
        new_lines.append('        import joblib\n')
    elif i == 514:  # "            'supervised_model': self.supervised_model,\n"
        new_lines.append('            \'supervised_model\': self.supervised_model,\n')
    elif i == 515:  # "            'anomaly_detector': self.anomaly_detector,\n"
        new_lines.append("            'anomaly_detector': self.anomaly_detector,\n")
    elif i == 516:  # "            'unknown_threshold': self.unknown_threshold,\n"
        new_lines.append("            'unknown_threshold': self.unknown_threshold,\n")
    elif i == 516:  # "            'low_confidence_threshold': self.low_confidence_threshold,\n"
        new_lines.append("            'low_confidence_threshold': self.low_confidence_threshold,\n")
    elif i == 516:  # '        }, path)\n'
        new_lines.append('        }, path)\n')
    elif i == 520:  # '        logger.info(f"Saved ZeroDayDetector to {path}")\n'
        new_lines.append('        logger.info(f"Saved ZeroDayDetector to {path}")\n')
    elif i == 517:  # '    def load(cls, path: Union[str, Path]) -> "ZeroDayDetector":\n'
        new_lines.append('    def load(cls, path: Union[str, Path]) -> "ZeroDayDetector":\n')
    else:
        new_lines.append(line)

with open('backend/ml/anomaly_detection.py', 'w') as f:
    f.writelines(new_lines)

print('Fixed')