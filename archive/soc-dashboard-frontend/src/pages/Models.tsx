import { useQuery } from "@tanstack/react-query";
import { modelService } from "../services/modelService";

export function Models() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["modelInfo"],
    queryFn: modelService.getInfo,
  });

  return (
    <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Machine Learning Models</h1>
          <p className="text-gray-400 mt-2">
            View active model information and detection metrics.
          </p>
        </div>

        {isLoading ? (
          <div className="animate-pulse space-y-4">
            <div className="h-64 bg-gray-800 rounded-xl border border-gray-700"></div>
          </div>
        ) : error ? (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6">
            <h3 className="text-red-400 font-medium">Failed to load model info</h3>
            <p className="text-sm text-red-400/80 mt-1">{(error as Error).message}</p>
          </div>
        ) : data ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
              <div className="px-6 py-5 border-b border-gray-700">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-medium text-white">Active Model Details</h2>
                  <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                    Active
                  </span>
                </div>
              </div>
              <div className="p-6">
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-6">
                  <div>
                    <dt className="text-sm font-medium text-gray-400">Model Name</dt>
                    <dd className="mt-1 text-sm text-white">{data.model_name}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-400">Version</dt>
                    <dd className="mt-1 text-sm text-white font-mono">{data.version}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-400">Scikit-learn Version</dt>
                    <dd className="mt-1 text-sm text-white">{data.sklearn_version}</dd>
                  </div>
                </dl>
              </div>
            </div>

            <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
              <div className="px-6 py-5 border-b border-gray-700">
                <h2 className="text-lg font-medium text-white">Performance Metrics</h2>
              </div>
              <div className="p-6 space-y-6">
                <div>
                  <div className="flex items-center justify-between text-sm mb-2">
                    <span className="text-gray-400">Accuracy</span>
                    <span className="text-white font-medium">{(data.accuracy * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${data.accuracy * 100}%` }}></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : null}
    </div>
  );
}
