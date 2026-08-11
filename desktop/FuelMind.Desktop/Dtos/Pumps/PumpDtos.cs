using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Pumps;

public sealed class PumpDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("tank_id")] public int TankId { get; init; }
    [JsonPropertyName("code")] public required string Code { get; init; }
    [JsonPropertyName("status")] public required string Status { get; init; }
    [JsonPropertyName("nominal_flow_rate")] public decimal NominalFlowRate { get; init; }
    [JsonPropertyName("minimum_flow_rate")] public decimal MinimumFlowRate { get; init; }
    [JsonPropertyName("maximum_motor_current")] public decimal MaximumMotorCurrent { get; init; }
    [JsonPropertyName("maximum_pressure")] public decimal MaximumPressure { get; init; }
    [JsonPropertyName("last_maintenance_at")] public DateTimeOffset? LastMaintenanceAt { get; init; }
    [JsonPropertyName("total_working_hours")] public decimal TotalWorkingHours { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    [JsonPropertyName("created_at")] public DateTimeOffset CreatedAt { get; init; }
}

public sealed class PumpCreateRequestDto
{
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("tank_id")] public int TankId { get; init; }
    [JsonPropertyName("code")] public required string Code { get; init; }
    [JsonPropertyName("status")] public string Status { get; init; } = "IDLE";
    [JsonPropertyName("nominal_flow_rate")] public decimal NominalFlowRate { get; init; }
    [JsonPropertyName("minimum_flow_rate")] public decimal MinimumFlowRate { get; init; }
    [JsonPropertyName("maximum_motor_current")] public decimal MaximumMotorCurrent { get; init; }
    [JsonPropertyName("maximum_pressure")] public decimal MaximumPressure { get; init; }
    [JsonPropertyName("last_maintenance_at")] public DateTimeOffset? LastMaintenanceAt { get; init; }
    [JsonPropertyName("total_working_hours")] public decimal TotalWorkingHours { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; } = true;
}

public sealed class PumpUpdateRequestDto
{
    [JsonPropertyName("station_id")] public int? StationId { get; init; }
    [JsonPropertyName("tank_id")] public int? TankId { get; init; }
    [JsonPropertyName("code")] public string? Code { get; init; }
    [JsonPropertyName("status")] public string? Status { get; init; }
    [JsonPropertyName("nominal_flow_rate")] public decimal? NominalFlowRate { get; init; }
    [JsonPropertyName("minimum_flow_rate")] public decimal? MinimumFlowRate { get; init; }
    [JsonPropertyName("maximum_motor_current")] public decimal? MaximumMotorCurrent { get; init; }
    [JsonPropertyName("maximum_pressure")] public decimal? MaximumPressure { get; init; }
    [JsonPropertyName("last_maintenance_at")] public DateTimeOffset? LastMaintenanceAt { get; init; }
    [JsonPropertyName("total_working_hours")] public decimal? TotalWorkingHours { get; init; }
    [JsonPropertyName("is_active")] public bool? IsActive { get; init; }
}
