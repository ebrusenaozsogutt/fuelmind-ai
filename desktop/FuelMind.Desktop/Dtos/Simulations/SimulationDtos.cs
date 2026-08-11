using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Simulations;

public sealed class CreateSimulationRequestDto
{
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("mode")] public string Mode { get; init; } = "REALTIME";
    [JsonPropertyName("simulation_start_time")] public DateTimeOffset SimulationStartTime { get; init; }
    [JsonPropertyName("tick_interval_ms")] public int TickIntervalMilliseconds { get; init; }
    [JsonPropertyName("simulation_step_seconds")] public int SimulationStepSeconds { get; init; }
    [JsonPropertyName("speed_multiplier")] public double SpeedMultiplier { get; init; }
    [JsonPropertyName("random_seed")] public int RandomSeed { get; init; }
    [JsonPropertyName("persist_every_n_ticks")] public int PersistEveryNTicks { get; init; }
}

public sealed class DatasetGenerationRequestDto
{
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("days")] public int Days { get; init; }
    [JsonPropertyName("simulation_start_time")] public DateTimeOffset SimulationStartTime { get; init; }
    [JsonPropertyName("simulation_step_seconds")] public int SimulationStepSeconds { get; init; }
    [JsonPropertyName("random_seed")] public int RandomSeed { get; init; }
}

public sealed class SimulationRunDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("mode")] public required string Mode { get; init; }
    [JsonPropertyName("status")] public required string Status { get; init; }
    [JsonPropertyName("simulation_start_time")] public DateTimeOffset SimulationStartTime { get; init; }
    [JsonPropertyName("current_simulation_time")] public DateTimeOffset? CurrentSimulationTime { get; init; }
    [JsonPropertyName("target_simulation_time")] public DateTimeOffset? TargetSimulationTime { get; init; }
    [JsonPropertyName("real_started_at")] public DateTimeOffset? RealStartedAt { get; init; }
    [JsonPropertyName("real_ended_at")] public DateTimeOffset? RealEndedAt { get; init; }
    [JsonPropertyName("progress_percent")] public double? ProgressPercent { get; init; }
    [JsonPropertyName("tick_interval_ms")] public int TickIntervalMilliseconds { get; init; }
    [JsonPropertyName("simulation_step_seconds")] public int SimulationStepSeconds { get; init; }
    [JsonPropertyName("speed_multiplier")] public double SpeedMultiplier { get; init; }
    [JsonPropertyName("random_seed")] public int RandomSeed { get; init; }
    [JsonPropertyName("persist_every_n_ticks")] public int PersistEveryNTicks { get; init; }
    [JsonPropertyName("sequence_number")] public int SequenceNumber { get; init; }
    [JsonPropertyName("generated_sensor_count")] public int GeneratedSensorCount { get; init; }
    [JsonPropertyName("generated_sale_count")] public int GeneratedSaleCount { get; init; }
    [JsonPropertyName("generated_delivery_count")] public int GeneratedDeliveryCount { get; init; }
    [JsonPropertyName("last_error")] public string? LastError { get; init; }
    [JsonPropertyName("created_by")] public int? CreatedBy { get; init; }
    [JsonPropertyName("created_at")] public DateTimeOffset CreatedAt { get; init; }
    [JsonPropertyName("updated_at")] public DateTimeOffset UpdatedAt { get; init; }
}

public sealed class SimulationRunStatisticsDto
{
    [JsonPropertyName("run_id")] public int RunId { get; init; }
    [JsonPropertyName("status")] public required string Status { get; init; }
    [JsonPropertyName("current_simulation_time")] public DateTimeOffset? CurrentSimulationTime { get; init; }
    [JsonPropertyName("target_simulation_time")] public DateTimeOffset? TargetSimulationTime { get; init; }
    [JsonPropertyName("progress_percent")] public double? ProgressPercent { get; init; }
    [JsonPropertyName("sequence_number")] public int SequenceNumber { get; init; }
    [JsonPropertyName("generated_sensor_count")] public int GeneratedSensorCount { get; init; }
    [JsonPropertyName("generated_sale_count")] public int GeneratedSaleCount { get; init; }
    [JsonPropertyName("generated_delivery_count")] public int GeneratedDeliveryCount { get; init; }
    [JsonPropertyName("real_started_at")] public DateTimeOffset? RealStartedAt { get; init; }
    [JsonPropertyName("real_ended_at")] public DateTimeOffset? RealEndedAt { get; init; }
}
