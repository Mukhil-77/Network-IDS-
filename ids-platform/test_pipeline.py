import sys
sys.path.insert(0, r'C:\Users\Mukhil\Downloads\files\ids-platform')
import time

# Quick test to verify the full pipeline
from backend.packet_capture.capture import PacketCapture
from backend.packet_capture.flow_manager import FlowManager
from backend.detection.detection_service import DetectionService
from backend.services.alert_service import alert_service
import time

print('=== Testing Full Pipeline ===')

try:
    fm = FlowManager()
    pc = PacketCapture(flow_manager=fm, interface='Wi-Fi', backend='scapy', bpf_filter='tcp or udp')
    pc.start()
    time.sleep(5)
    pc.stop()
    print(f'Packets captured: {pc.packet_count}')
    print(f'Active flows: {fm.active_flow_count()}')
    
    # Check database for alerts
    from backend.database.connection import session_scope
    from backend.database.repositories.alerts import AlertRepository
    with session_scope() as db:
        from backend.database.repositories.alerts import AlertRepository
        alerts = AlertRepository(db).get_latest(10)
        print(f'Recent alerts in DB: {len(alerts)}')
        for a in alerts[:3]:
            print(f'  {a.attack_type} | {a.severity} | {a.source_ip} -> {a.destination_ip} | flow_id: {a.flow_id}')
    
    # Check live alerts in memory
    print(f'Alerts in memory: {len(alert_service._alerts) if hasattr(alert_service, "_alerts") else "N/A"}')
    
    print('Pipeline test complete!')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()