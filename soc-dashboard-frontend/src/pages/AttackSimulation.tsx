import { useState, FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { testingService, SimulateAttackRequest } from "../services/testingService";

export function AttackSimulation() {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<SimulateAttackRequest>({
    attack_type: "DDoS",
    confidence: 99.5,
    source_ip: "192.168.1.100",
    destination_ip: "10.0.0.5",
    protocol: "TCP",
    severity: "High",
  });

  const historyQuery = useQuery({
    queryKey: ["simulationHistory"],
    queryFn: testingService.getHistory,
  });

  const simulateMutation = useMutation({
    mutationFn: testingService.simulateAttack,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["simulationHistory"] });
    },
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    simulateMutation.mutate(formData);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === "confidence" ? parseFloat(value) : value,
    }));
  };

  return (
    <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Attack Simulation</h1>
          <p className="text-gray-400 mt-2">
            Simulate attacks to verify the SOC platform's real-time detection and response capabilities.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
            <h2 className="text-lg font-medium text-white mb-4">Simulate Attack</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Attack Type</label>
                  <select
                    name="attack_type"
                    value={formData.attack_type}
                    onChange={handleInputChange}
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="BENIGN">BENIGN</option>
                    <option value="DDoS">DDoS</option>
                    <option value="DoS">DoS</option>
                    <option value="Port Scan">Port Scan</option>
                    <option value="Brute Force">Brute Force</option>
                    <option value="Bot">Bot</option>
                    <option value="Web Attack - Brute Force">Web Attack</option>
                    <option value="XSS">XSS</option>
                    <option value="SQL Injection">SQL Injection</option>
                    <option value="Infiltration">Infiltration</option>
                    <option value="Heartbleed">Heartbleed</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Severity</label>
                  <select
                    name="severity"
                    value={formData.severity}
                    onChange={handleInputChange}
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="Low">Low</option>
                    <option value="Medium">Medium</option>
                    <option value="High">High</option>
                    <option value="Critical">Critical</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Confidence (%)</label>
                  <input
                    type="number"
                    name="confidence"
                    value={formData.confidence}
                    onChange={handleInputChange}
                    min="0"
                    max="100"
                    step="0.1"
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Protocol</label>
                  <input
                    type="text"
                    name="protocol"
                    value={formData.protocol}
                    onChange={handleInputChange}
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Source IP</label>
                  <input
                    type="text"
                    name="source_ip"
                    value={formData.source_ip}
                    onChange={handleInputChange}
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Destination IP</label>
                  <input
                    type="text"
                    name="destination_ip"
                    value={formData.destination_ip}
                    onChange={handleInputChange}
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={simulateMutation.isPending}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors disabled:opacity-50"
                >
                  {simulateMutation.isPending ? "Simulating..." : "Simulate Attack"}
                </button>
              </div>
              {simulateMutation.isSuccess && (
                <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
                  <p className="text-sm text-green-400 text-center">Attack simulated successfully! Check the dashboard.</p>
                </div>
              )}
            </form>
          </div>

          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
            <h2 className="text-lg font-medium text-white mb-4">Simulation History</h2>
            {historyQuery.isLoading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-16 bg-gray-700 rounded-lg"></div>
                ))}
              </div>
            ) : historyQuery.data?.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No simulations run yet.
              </div>
            ) : (
              <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                {historyQuery.data?.map((record, idx) => (
                  <div key={idx} className="bg-gray-900/50 rounded-lg p-3 border border-gray-700/50 flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">{record.attack_type}</span>
                        <span className="px-2 py-0.5 rounded text-xs bg-gray-800 text-gray-400">{record.source_ip}</span>
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        {new Date(record.timestamp).toLocaleString()} by {record.user}
                      </div>
                    </div>
                    <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                      {record.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
    </div>
  );
}
