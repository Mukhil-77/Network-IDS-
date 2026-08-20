import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { modelService } from "../services/modelService";

const ALGORITHMS = [
  { value: "random_forest", label: "Random Forest" },
  { value: "decision_tree", label: "Decision Tree" },
  { value: "knn", label: "K-Nearest Neighbors" },
  { value: "logistic_regression", label: "Logistic Regression" },
  { value: "svm", label: "SVM" },
];

export function Models() {
  const queryClient = useQueryClient();
  const [switching, setSwitching] = useState<string | null>(null);
  const [switchError, setSwitchError] = useState<string | null>(null);

  const [algorithm, setAlgorithm] = useState(ALGORITHMS[0].value);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const trainStatusQuery = useQuery({
    queryKey: ["modelTrainStatus"],
    queryFn: modelService.trainStatus,
    refetchInterval: (query) => (query.state.data?.training ? 2000 : false),
  });

  const infoQuery = useQuery({
    queryKey: ["modelInfo"],
    queryFn: modelService.getInfo,
  });

  const versionsQuery = useQuery({
    queryKey: ["modelVersions"],
    queryFn: modelService.listVersions,
    refetchInterval: (query) => (trainStatusQuery.data?.training ? 3000 : false),
  });

  const switchMutation = useMutation({
    mutationFn: modelService.switchVersion,
    onSuccess: () => {
      setSwitchError(null);
      // The active version changed, so both the info summary and the
      // version list carry stale "active" state.
      queryClient.invalidateQueries({ queryKey: ["modelInfo"] });
      queryClient.invalidateQueries({ queryKey: ["modelVersions"] });
    },
    onError: (error: Error) => setSwitchError(error.message),
  });

  const trainMutation = useMutation({
    mutationFn: modelService.train,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["modelTrainStatus"] });
    },
    onError: (error: Error) => setDeleteError(error.message),
  });

  const cancelMutation = useMutation({
    mutationFn: modelService.cancelTrain,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["modelTrainStatus"] });
    },
    onError: (error: Error) => setDeleteError(error.message),
  });

  const deleteMutation = useMutation({
    mutationFn: modelService.deleteVersion,
    onSuccess: () => {
      setDeleting(null);
      queryClient.invalidateQueries({ queryKey: ["modelVersions"] });
      queryClient.invalidateQueries({ queryKey: ["modelInfo"] });
    },
    onError: (error: Error) => {
      setDeleting(null);
      setDeleteError(error.message);
    },
  });

  const handleActivate = async (version: string) => {
    setSwitching(version);
    setSwitchError(null);
    try {
      await switchMutation.mutateAsync(version);
    } finally {
      setSwitching(null);
    }
  };

  const handleDelete = async (version: string) => {
    if (!window.confirm(`Delete model version ${version} from disk?`)) return;
    setDeleteError(null);
    setDeleting(version);
    await deleteMutation.mutateAsync(version);
  };

  const { data, isLoading, error } = infoQuery;
  const trainingStatus = trainStatusQuery.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">Machine Learning Models</h1>
        <p className="text-slate-400 mt-2">
          View active model information, compare trained versions, train new models in the background, and switch which version detection uses.
        </p>
      </div>

      {/* Train a new model */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-700">
          <h2 className="text-lg font-medium text-slate-100">Train a New Model</h2>
        </div>
        <div className="p-6">
          {trainingStatus?.training ? (
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                <p className="text-sm text-slate-300">
                  Training <span className="font-mono text-blue-400">{trainingStatus.algorithm}</span> in the background…
                  new versions appear in the table below when it finishes.
                </p>
              </div>
              <button
                type="button"
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="px-4 py-2 rounded-md text-sm font-medium border border-red-500/40 text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {cancelMutation.isPending ? "Stopping…" : "Stop Training"}
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={algorithm}
                onChange={(e) => setAlgorithm(e.target.value)}
                className="rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-slate-100 focus:border-blue-500 focus:outline-none"
              >
                {ALGORITHMS.map((a) => (
                  <option key={a.value} value={a.value}>{a.label}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => trainMutation.mutate(algorithm)}
                disabled={trainMutation.isPending || trainingStatus?.training}
                className="px-4 py-2 rounded-md text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {trainMutation.isPending ? "Starting…" : "Start Training"}
              </button>
              <button
                type="button"
                onClick={() => trainMutation.mutate("all")}
                disabled={trainMutation.isPending || trainingStatus?.training}
                className="px-4 py-2 rounded-md text-sm font-medium border border-blue-500/40 text-blue-400 hover:bg-blue-500/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Train All Families
              </button>
              <p className="text-xs text-gray-500">
                Runs on the dataset at <code className="font-mono">DATA_PATH</code> and saves every fitted
                variant as its own version. "Train All Families" trains every algorithm back-to-back.
              </p>
            </div>
          )}
          {trainingStatus?.cancelled && (
            <p className="mt-2 text-sm text-amber-400">
              Training was stopped by operator request. Versions saved before the stop remain in the table below.
            </p>
          )}
          {trainingStatus?.error && (
            <p className="mt-2 text-sm text-red-400">Last training run failed: {trainingStatus.error}</p>
          )}
        </div>
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
                <h2 className="text-lg font-medium text-slate-100">Active Model Details</h2>
                <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                  Active
                </span>
              </div>
            </div>
            <div className="p-6">
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-6">
                <div>
                  <dt className="text-sm font-medium text-gray-400">Model Name</dt>
                  <dd className="mt-1 text-sm text-slate-100">{data.model_name}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-400">Version</dt>
                  <dd className="mt-1 text-sm text-slate-100 font-mono">{data.version}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-400">Training Date</dt>
                  <dd className="mt-1 text-sm text-slate-100">{data.training_date}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-400">Scikit-learn Version</dt>
                  <dd className="mt-1 text-sm text-slate-100">{data.sklearn_version}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-400">Input Features</dt>
                  <dd className="mt-1 text-sm text-slate-100">{data.num_features}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-400">PCA Components</dt>
                  <dd className="mt-1 text-sm text-slate-100">{data.pca_components}</dd>
                </div>
              </dl>
            </div>
          </div>

          <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
            <div className="px-6 py-5 border-b border-gray-700">
              <h2 className="text-lg font-medium text-slate-100">Performance Metrics</h2>
            </div>
            <div className="p-6 space-y-6">
              <div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-gray-400">Accuracy</span>
                  <span className="text-slate-100 font-medium">{(data.accuracy * 100).toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${data.accuracy * 100}%` }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-700">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-slate-100">Trained Versions</h2>
            <span className="text-sm text-gray-400">{versionsQuery.data?.length ?? 0} on disk</span>
          </div>
        </div>

        {versionsQuery.isLoading ? (
          <div className="p-6 text-sm text-gray-400">Loading versions…</div>
        ) : versionsQuery.isError ? (
          <div className="p-6 text-sm text-red-400">Failed to load model versions.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase tracking-wide text-gray-500 border-b border-gray-700">
                <tr>
                  <th className="px-6 py-3 text-left font-medium">Version</th>
                  <th className="px-6 py-3 text-left font-medium">Model</th>
                  <th className="px-6 py-3 text-left font-medium">Dataset</th>
                  <th className="px-6 py-3 text-left font-medium">Trained</th>
                  <th className="px-6 py-3 text-right font-medium">Accuracy</th>
                  <th className="px-6 py-3 text-right font-medium">PCA</th>
                  <th className="px-6 py-3 text-right font-medium">Status</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {versionsQuery.data?.map((version) => (
                  <tr key={version.version} className={version.active ? "bg-green-500/[0.04]" : ""}>
                    <td className="px-6 py-3 font-mono text-slate-100">{version.version}</td>
                    <td className="px-6 py-3 text-gray-200">{version.model_name}</td>
                    <td className="px-6 py-3 text-gray-400">{version.dataset}</td>
                    <td className="px-6 py-3 text-gray-400">{version.training_date || "—"}</td>
                    <td className="px-6 py-3 text-right text-gray-200 font-mono">
                      {version.accuracy !== null ? `${(version.accuracy * 100).toFixed(1)}%` : "—"}
                    </td>
                    <td className="px-6 py-3 text-right text-gray-400 font-mono">
                      {version.pca_components ?? "—"}
                    </td>
                    <td className="px-6 py-3 text-right">
                      {version.active ? (
                        <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                          Active
                        </span>
                      ) : (
                        <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-gray-700/50 text-gray-300 border border-gray-600">
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-right whitespace-nowrap">
                      {!version.active && (
                        <button
                          type="button"
                          onClick={() => handleActivate(version.version)}
                          disabled={switching !== null}
                          className="px-3 py-1.5 rounded-md text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {switching === version.version ? "Switching…" : "Activate"}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDelete(version.version)}
                        disabled={deleting !== null}
                        className="ml-2 px-3 py-1.5 rounded-md text-xs font-medium border border-red-500/40 text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {deleting === version.version ? "Deleting…" : "Delete"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!versionsQuery.data?.length && (
              <div className="p-6 text-sm text-gray-400">No trained versions found on disk.</div>
            )}
          </div>
        )}

        {switchError && (
          <div className="px-6 py-3 border-t border-gray-700 bg-red-500/10 text-sm text-red-400">
            {switchError}
          </div>
        )}
        {deleteError && (
          <div className="px-6 py-3 border-t border-gray-700 bg-red-500/10 text-sm text-red-400">
            {deleteError}
          </div>
        )}
      </div>
    </div>
  );
}
