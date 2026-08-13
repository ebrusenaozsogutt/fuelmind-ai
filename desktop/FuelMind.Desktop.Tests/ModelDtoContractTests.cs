using System.Text.Json;
using System.Text.Json.Serialization;
using FuelMind.Desktop.Dtos.Models;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class ModelDtoContractTests
{
    [Fact]
    public void ModelListResponse_DeserializesBackendSnakeCaseContract()
    {
        const string json = """
            [{
              "id": 12,
              "model_type": "isolation_forest",
              "model_family": "pump",
              "version": "v0012",
              "trained_at": "2026-08-12T06:42:00Z",
              "training_start_date": "2026-05-14",
              "training_end_date": "2026-08-12",
              "training_row_count": 18420,
              "feature_count": null,
              "feature_names": [],
              "is_active": true,
              "artifact_available": true,
              "artifact_file_name": "isolation_forest_pump_v0012.joblib",
              "artifact_size_bytes": 1066541,
              "artifact_schema_version": null,
              "training_outlier_fraction": 0.0312,
              "validation_status": null,
              "scenario_detection_count": null,
              "scenario_total_count": null,
              "normal_false_positive_rate": null,
              "latest_sensor_reading_at": "2026-08-19T08:30:00Z",
              "new_sensor_rows_since_training": 14230
            }]
            """;

        var result = JsonSerializer.Deserialize<List<ModelVersionDto>>(json);

        var model = Assert.Single(result!);
        Assert.Equal("isolation_forest", model.ModelType);
        Assert.Equal("pump", model.ModelFamily);
        Assert.Equal(DateTimeOffset.Parse("2026-08-12T06:42:00Z"), model.TrainedAt);
        Assert.Equal(new DateOnly(2026, 5, 14), model.TrainingStartDate);
        Assert.Equal(new DateOnly(2026, 8, 12), model.TrainingEndDate);
        Assert.Null(model.FeatureCount);
        Assert.Null(model.ArtifactSchemaVersion);
        Assert.True(model.IsActive);
        Assert.Equal(0.0312, model.TrainingOutlierFraction);
        Assert.Equal(14230, model.NewSensorRowsSinceTraining);
        Assert.Equal(DateTimeOffset.Parse("2026-08-19T08:30:00Z"), model.LatestSensorReadingAt);
    }

    [Fact]
    public void TrainingRequest_SerializesExactBackendPropertyNamesAndOmitsNulls()
    {
        var options = new JsonSerializerOptions
        {
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        };
        var request = new TrainAnomalyModelRequestDto
        {
            StationId = 7,
            ModelFamily = "tank",
            SourceTypes = ["SIMULATION"],
        };

        using var document = JsonDocument.Parse(JsonSerializer.Serialize(request, options));
        var root = document.RootElement;

        Assert.Equal(7, root.GetProperty("station_id").GetInt32());
        Assert.Equal("tank", root.GetProperty("model_family").GetString());
        Assert.Equal("SIMULATION", root.GetProperty("source_types")[0].GetString());
        Assert.False(root.TryGetProperty("start_time", out _));
        Assert.False(root.TryGetProperty("end_time", out _));
    }
}
