using System.Text.Json;
using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Models;

public class ModelVersionDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("model_type")] public required string ModelType { get; init; }
    [JsonPropertyName("model_family")] public required string ModelFamily { get; init; }
    [JsonPropertyName("version")] public required string Version { get; init; }
    [JsonPropertyName("trained_at")] public DateTimeOffset TrainedAt { get; init; }
    [JsonPropertyName("training_start_date")] public DateOnly TrainingStartDate { get; init; }
    [JsonPropertyName("training_end_date")] public DateOnly TrainingEndDate { get; init; }
    [JsonPropertyName("training_row_count")] public int TrainingRowCount { get; init; }
    [JsonPropertyName("feature_count")] public int? FeatureCount { get; init; }
    [JsonPropertyName("feature_names")] public IReadOnlyList<string> FeatureNames { get; init; } = [];
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    [JsonPropertyName("artifact_available")] public bool ArtifactAvailable { get; init; }
    [JsonPropertyName("artifact_file_name")] public required string ArtifactFileName { get; init; }
    [JsonPropertyName("artifact_size_bytes")] public long ArtifactSizeBytes { get; init; }
    [JsonPropertyName("artifact_schema_version")] public int? ArtifactSchemaVersion { get; init; }
    [JsonPropertyName("training_outlier_fraction")] public double? TrainingOutlierFraction { get; init; }
    [JsonPropertyName("validation_status")] public string? ValidationStatus { get; init; }
    [JsonPropertyName("scenario_detection_count")] public int? ScenarioDetectionCount { get; init; }
    [JsonPropertyName("scenario_total_count")] public int? ScenarioTotalCount { get; init; }
    [JsonPropertyName("normal_false_positive_rate")] public double? NormalFalsePositiveRate { get; init; }
    [JsonPropertyName("latest_sensor_reading_at")] public DateTimeOffset? LatestSensorReadingAt { get; init; }
    [JsonPropertyName("new_sensor_rows_since_training")] public long NewSensorRowsSinceTraining { get; init; }
}

public sealed class TrainAnomalyModelRequestDto
{
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("model_family")] public required string ModelFamily { get; init; }
    [JsonPropertyName("start_time")] public DateTimeOffset? StartTime { get; init; }
    [JsonPropertyName("end_time")] public DateTimeOffset? EndTime { get; init; }
    [JsonPropertyName("source_types")] public IReadOnlyList<string>? SourceTypes { get; init; }
}

public sealed class TrainAnomalyModelResponseDto : ModelVersionDto
{
    [JsonPropertyName("training_diagnostics")]
    public IReadOnlyDictionary<string, JsonElement> TrainingDiagnostics { get; init; }
        = new Dictionary<string, JsonElement>();
}
