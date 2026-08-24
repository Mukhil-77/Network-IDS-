import { useState, useEffect } from "react";
import { captureService, type CaptureStatus } from "../../services/captureService";

export function CaptureControl() {
  const [status, setStatus] = useState<CaptureStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = async () => {
    try {
      const data = await captureService.status();
      setStatus(data);
    } catch (e) {
      console.error("Failed to fetch capture status", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    setLoading(true);
    try {
      await captureService.start();
      await fetchStatus();
    } catch (e) {
      console.error("Failed to start capture", e);
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await captureService.stop();
      await fetchStatus();
    } catch (e) {
      console.error("Failed to stop capture", e);
      setLoading(false);
    }
  };

  if (loading && !status) return <div className="p-4 bg-surface-raised rounded-xl animate-pulse h-24" />;

  return (
    <div className="rounded-xl border border-border bg-surface-raised p-4 flex flex-col justify-between h-full">
      <div>
        <h2 className="text-sm font-medium text-slate-300 mb-2">Live Packet Capture</h2>
        <div className="flex items-center gap-2 mb-4">
          <div className={`w-3 h-3 rounded-full ${status?.running ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
          <span className="text-sm text-slate-300">{status?.running ? 'Running' : 'Stopped'}</span>
        </div>
        {status?.running && (
          <p className="text-xs text-slate-400 mb-4">Active Flows: {status.active_flows}</p>
        )}
      </div>
      <div className="flex gap-2 mt-auto">
        {!status?.running ? (
          <button
            onClick={handleStart}
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 rounded transition-colors disabled:opacity-50"
          >
            Start Capture
          </button>
        ) : (
          <button
            onClick={handleStop}
            disabled={loading}
            className="w-full bg-red-600 hover:bg-red-700 text-white text-sm font-medium py-2 rounded transition-colors disabled:opacity-50"
          >
            Stop Capture
          </button>
        )}
      </div>
    </div>
  );
}
