// Mirrors backend/api/schemas.py's ModelInfoResponse (GET /model/info).

export interface ModelInfo {
  model_name: string;
  version: string;
  training_date: string;
  accuracy: number;
  num_features: number;
  pca_components: number;
  sklearn_version: string;
}
