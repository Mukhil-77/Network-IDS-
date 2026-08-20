// Mirrors backend/api/schemas.py's ModelInfoResponse (GET /model/info and
// the response of POST /model/switch/{version}).

export interface ModelInfo {
  model_name: string;
  version: string;
  training_date: string;
  accuracy: number;
  num_features: number;
  pca_components: number;
  sklearn_version: string;
}

// Mirrors backend/api/schemas.py's ModelVersionSummary (GET /model/versions).
// training_date defaults to "" and accuracy/pca_components to null when the
// metadata bundle on disk omits them.
export interface ModelVersionSummary {
  version: string;
  model_name: string;
  dataset: string;
  training_date: string;
  accuracy: number | null;
  pca_components: number | null;
  active: boolean;
}

// Mirrors backend/api/schemas.py's ModelTrainStatusResponse
// (GET /model/train/status, POST /model/train, POST /model/train/cancel).
export interface ModelTrainStatus {
  training: boolean;
  algorithm: string | null;
  error: string | null;
  cancelled: boolean;
}