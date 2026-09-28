import sys
sys.path.insert(0, r'C:\Users\Mukhil\Downloads\files\ids-platform')
import time

from backend.packet_capture.capture import PacketCapture
from backend.packet_capture.flow_manager import FlowManager
from backend.detection.detection_service import DetectionService
from backend.services.alert_service import alert_service
from backend.services.capture_service import capture_service
import time

print('=== Debugging Detection Pipeline ===')

# Check if capture service is running
print(f'Capture service running: {capture_service.capture is not None}')
if capture_service.capture:
    print(f'  Capture running: {capture_service.capture.running}')
    print(f'  Packet count: {getattr(capture_service.capture, "packet_count", 0)}')

# Check flow manager
if capture_service.flow_manager:
    print(f'Active flows: {capture_service.flow_manager.active_flow_count()}')

# Check detection service
print(f'Detection service model loaded: {capture_service.detection_service is not None}')
if capture_service.detection_service:
    print(f'  Model loaded: {capture_service.detection_service.prediction_service.is_model_loaded()}')

# Check alert service
print(f'Alert service alerts in memory: {len(alert_service._alerts) if hasattr(alert_service, "_alerts") else "N/A"}')

# Check database for alerts
from backend.database.connection import session_scope
from backend.database.repositories.alerts import AlertRepository
with session_scope() as db:
    from backend.database.repositories.alerts import AlertRepository
    alerts = AlertRepository(db).get_latest(10)
    print(f'Recent alerts in DB: {len(alerts)}')
    for a in alerts[:3]:
        print(f'  {a.attack_type} | {a.severity} | {a.source_ip} -> {a.destination_ip} | flow_id: {a.flow_id}')

# Check if detection service is processing
if capture_service.detection_service:
    ds = capture_service.detection_service
    print(f'Detection service model loaded: {ds.prediction_service.is_model_loaded()}')
    if hasattr(ds, '_executor'):
        print(f'  Executor: {ds._executor}')
        print(f'  Pending tasks: {ds._executor._work_queue.qsize() if hasattr(ds._executor, "_work_queue") else "N/A"}')