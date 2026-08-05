"""Tests for POST /predict."""


def test_predict_returns_404_when_no_model_loaded(client, valid_feature_payload):
    response = client.post("/predict", json={"features": valid_feature_payload})
    assert response.status_code == 404
    assert response.json()["error"] == "model_missing"


def test_predict_success_returns_full_response_shape(client_with_model, valid_feature_payload):
    response = client_with_model.post("/predict", json={"features": valid_feature_payload})
    assert response.status_code == 200
    body = response.json()

    assert body["prediction"] in {"BENIGN", "DoS"}
    assert 0.0 <= body["confidence"] <= 100.0
    assert body["severity"] in {"Low", "Medium", "High", "Critical"}
    assert body["model_version"] == "v1"
    assert body["latency_ms"] >= 0.0
    assert "timestamp" in body


def test_predict_missing_features_returns_422(client_with_model, valid_feature_payload):
    incomplete = dict(list(valid_feature_payload.items())[:2])  # drop most required features
    response = client_with_model.post("/predict", json={"features": incomplete})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_input"
    assert any(err["error_type"] == "missing_feature" for err in body["detail"])


def test_predict_unexpected_feature_returns_422(client_with_model, valid_feature_payload):
    payload = dict(valid_feature_payload)
    payload["Totally Unexpected Column"] = 1.0
    response = client_with_model.post("/predict", json={"features": payload})

    assert response.status_code == 422
    body = response.json()
    assert any(err["error_type"] == "unexpected_feature" for err in body["detail"])


def test_predict_malformed_body_returns_400(client_with_model):
    response = client_with_model.post("/predict", json={"wrong_key": {}})

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "validation_error"


def test_predict_infinite_feature_value_returns_422(client_with_model, valid_feature_payload):
    # A non-numeric *string* (e.g. "abc") never reaches validator.py's
    # invalid_type check: PredictionRequest.features is typed dict[str, float],
    # so Pydantic itself rejects it at the request-schema level -> 400 (see
    # test_predict_malformed_body_returns_400). Infinity, however, is a value
    # Pydantic's float type accepts - so this is the realistic case that
    # actually reaches, and is caught by, our own feature validator -> 422.
    #
    # httpx's json=... helper enforces strict JSON (rejects non-finite floats
    # client-side before the request is even sent), so the body is built
    # manually here with Python's json module (allow_nan=True, matching what
    # Python's own json.loads on the server side will happily parse back).
    import json as json_module

    payload = dict(valid_feature_payload)
    first_key = next(iter(payload))
    payload[first_key] = float("inf")

    body_str = json_module.dumps({"features": payload}, allow_nan=True)
    response = client_with_model.post(
        "/predict", content=body_str, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    body = response.json()
    assert any(err["error_type"] == "infinite_value" for err in body["detail"])


def test_predict_sets_request_id_header(client_with_model, valid_feature_payload):
    response = client_with_model.post("/predict", json={"features": valid_feature_payload})
    assert "X-Request-ID" in response.headers
