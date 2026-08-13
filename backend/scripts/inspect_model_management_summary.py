"""Print the real Model Management API summary without changing state."""

from fastapi.testclient import TestClient

from app.api.dependencies import require_operator_or_admin
from app.main import app


def main() -> None:
    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.get("/api/models")
            response.raise_for_status()
            models = response.json()
    finally:
        app.dependency_overrides.pop(require_operator_or_admin, None)

    for model in sorted(models, key=lambda item: item["version"]):
        print(
            f"{model['version']} status={'ACTIVE' if model['is_active'] else 'INACTIVE'} "
            f"range={model['training_start_date']}..{model['training_end_date']} "
            f"rows={model['training_row_count']} features={model['feature_count']} "
            f"outlier_fraction={model['training_outlier_fraction']} "
            f"normal_false_positive={model['normal_false_positive_rate']} "
            f"scenario={model['scenario_detection_count']}/{model['scenario_total_count']} "
            f"validation={model['validation_status']} "
            f"latest={model['latest_sensor_reading_at']} "
            f"new_rows={model['new_sensor_rows_since_training']}"
        )


if __name__ == "__main__":
    main()
