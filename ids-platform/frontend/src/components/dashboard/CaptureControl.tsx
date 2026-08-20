import { useState, useEffect } from "react";
import { captureService, type CaptureInterface, type CaptureStatus } from "../../services/captureService";

const PROTOCOLS = [
  { value: "tcp", label: "TCP" },
  { value: "udp", label: "UDP" },
  { value: "icmp", label: "ICMP" },
];

const ALL = "all";

export function CaptureControl() {
  const [status, setStatus] = useState<CaptureStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [interfaces, setInterfaces] = useState<CaptureInterface[]>([]);
  const [selectedInterface, setSelectedInterface] = useState<string>("");
  const [selectedProtocols, setSelectedProtocols] = useState<string[]>(["tcp", "udp"]);
  const [error, setError] = useState<string | null>(null);

  const captureAll = selectedProtocols.includes(ALL);

  const ifaceDescription = (name: string | null): string => {
    if (!name) return "Default interface";
    const match = interfaces.find((i) => i.name === name) ?? interfaces.find((i) => i.name.includes(name));
    return match?.description ?? name;
  };

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

  useEffect(() => {
    captureService
      .interfaces()
      .then((list) => setInterfaces(list))
      .catch(() => setInterfaces([]));
  }, []);

  const toggleProtocol = (value: string) => {
    setSelectedProtocols((current) =>
      current.includes(value) ? current.filter((p) => p !== value) : [...current, value],
    );
  };

  const toggleAll = () => {
    setSelectedProtocols((current) => (current.includes(ALL) ? ["tcp", "udp"] : [ALL]));
  };

  const handleStart = async () => {
    setLoading(true);
    setError(null);
    try {
      await captureService.start({
        interfaceName: selectedInterface || undefined,
        protocols: selectedProtocols,
      });
      await fetchStatus();
    } catch (e) {
      console.error("Failed to start capture", e);
      setError("Failed to start capture. Check that you picked a valid adapter.");
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
        <div className="flex items-center gap-2 mb-2">
          <div className={`w-3 h-3 rounded-full ${status?.running ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
          <span className="text-sm text-slate-300">{status?.running ? 'Running' : 'Stopped'}</span>
        </div>
        {status?.running && (
          <>
            <p className="text-xs text-slate-400 mb-1">Active Flows: {status.active_flows}</p>
            <p className="text-xs text-slate-400 mb-1">
              Packets: <span className="font-mono text-slate-300">{status.packet_count}</span>
            </p>
            <p className="text-xs text-slate-400 mb-1">
              Interface: <span className="font-mono text-slate-300">{ifaceDescription(status.interface ?? null)}</span>
            </p>
            <p className="text-xs text-slate-400 mb-1">
              Protocols: <span className="font-mono text-slate-300">{status.protocols?.join(" + ") ?? "tcp + udp"}</span>
            </p>
            <p className="text-xs text-slate-400">
              Predictions:{" "}
              <span className="font-mono text-slate-300">{status.predictions_count}</span>
              {" · Avg latency: "}
              <span className="font-mono text-slate-300">
                {status.predictions_count > 0 ? `${status.average_prediction_latency_ms.toFixed(2)} ms` : "—"}
              </span>
            </p>
          </>
        )}
      </div>

      {!status?.running && (
        <div className="space-y-3 mt-2">
          <div>
            <label className="mb-1 block text-xs text-slate-500">Network adapter</label>
            <select
              value={selectedInterface}
              onChange={(e) => setSelectedInterface(e.target.value)}
              className="w-full rounded-md border border-border bg-surface-overlay px-2 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
            >
              <option value="">Default interface</option>
              {interfaces.map((iface) => (
                <option key={iface.name} value={iface.name} title={iface.name}>
                  {iface.description}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Protocols</label>
            <div className="flex flex-wrap gap-2">
              <label className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-slate-100">
                <input
                  type="checkbox"
                  checked={captureAll}
                  onChange={toggleAll}
                  className="accent-blue-500"
                />
                All protocols
              </label>
              {PROTOCOLS.map((p) => (
                <label
                  key={p.value}
                  className={`flex cursor-pointer items-center gap-1.5 text-xs ${
                    captureAll ? "text-slate-600" : "text-slate-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedProtocols.includes(p.value)}
                    onChange={() => toggleProtocol(p.value)}
                    disabled={captureAll}
                    className="accent-blue-500 disabled:opacity-40"
                  />
                  {p.label}
                </label>
              ))}
            </div>
          </div>
        </div>
      )}

      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}

      <div className="flex gap-2 mt-3">
        {!status?.running ? (
          <button
            onClick={handleStart}
            disabled={loading || selectedProtocols.length === 0}
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