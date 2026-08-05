"""Tests for GET /model/info."""


def test_model_info_returns_404_when_no_model_loaded(client):
    response = client.get("/model/info")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "model_missing"


def test_model_info_returns_expected_fields(client_with_model):
    response = client_with_model.get("/model/info")
    assert response.status_code == 200
    body = response.json()

    expected_fields = {
        "model_name", "version", "training_date", "accuracy",
        "num_features", "pca_components", "sklearn_version",
    }
    assert expected_fields.issubset(body.keys())
    assert body["version"] == "v1"
    assert isinstance(body["num_features"], int)
    assert isinstance(body["accuracy"], float)
