import sys
sys.path.insert(0, r'C:\Users\Mukhil\Downloads\files\ids-platform')
import os
os.chdir(r'C:\Users\Mukhil\Downloads\files\ids-platform')

from backend.ml.continuous_monitoring import ContinuousMonitor, MetricType
from datetime import datetime, timezone

class MockAlert:
    def __init__(self):
        self.severity = 'CRITICAL'
        self.timestamp = datetime.now(timezone.utc)
        self.source_ip = '192.168.1.1'
        self.risk_score = 95

monitor = ContinuousMonitor()
alert = type('Alert', (), {
    'severity': 'CRITICAL',
    'timestamp': datetime.now(timezone.utc),
    'source_ip': '192.168.1.1',
    'risk_score': 95
})()

monitor.record_alert(type('Alert', (), {
    'severity': 'CRITICAL',
    'timestamp': datetime.now(timezone.utc),
    'source_ip': '192.168.1.1',
    'risk_score': 95
}))

print('Continuous monitoring module loaded successfully')
print('Basic test passed')