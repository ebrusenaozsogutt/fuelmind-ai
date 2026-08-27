using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Forecasts;

public sealed class ForecastDto
{
    [JsonPropertyName("forecast_date")] public DateOnly ForecastDate { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("fuel_type_id")] public int FuelTypeId { get; init; }
    [JsonPropertyName("fuel_type")] public string? FuelType { get; init; }
    [JsonPropertyName("predicted_demand")] public decimal PredictedDemand { get; init; }
    [JsonPropertyName("lower_bound")] public decimal LowerBound { get; init; }
    [JsonPropertyName("upper_bound")] public decimal UpperBound { get; init; }
    [JsonPropertyName("confidence_score")] public decimal ConfidenceScore { get; init; }
    [JsonPropertyName("model_version")] public string ModelVersion { get; init; } = "";
}

public sealed class ForecastPerformanceDto
{
    [JsonPropertyName("winner")] public string? Winner { get; init; }
    [JsonPropertyName("model_type")] public string? ModelType { get; init; }
    [JsonPropertyName("model_version")] public string? ModelVersion { get; init; }
    [JsonPropertyName("mae")] public decimal? Mae { get; init; }
    [JsonPropertyName("rmse")] public decimal? Rmse { get; init; }
    [JsonPropertyName("mape")] public decimal? Mape { get; init; }
    [JsonPropertyName("training_row_count")] public int? TrainingRowCount { get; init; }
}
