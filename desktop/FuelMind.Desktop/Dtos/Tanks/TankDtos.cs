using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Tanks;

[JsonNumberHandling(JsonNumberHandling.AllowReadingFromString)]
public sealed class TankDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("fuel_type_id")] public int FuelTypeId { get; init; }
    [JsonPropertyName("code")] public required string Code { get; init; }
    [JsonPropertyName("capacity_liters")] public decimal CapacityLiters { get; init; }
    [JsonPropertyName("current_level_liters")] public decimal CurrentLevelLiters { get; init; }
    [JsonPropertyName("minimum_safe_level")] public decimal MinimumSafeLevel { get; init; }
    [JsonPropertyName("critical_level")] public decimal CriticalLevel { get; init; }
    [JsonPropertyName("water_level")] public decimal WaterLevel { get; init; }
    [JsonPropertyName("temperature")] public decimal? Temperature { get; init; }
    [JsonPropertyName("sensor_status")] public required string SensorStatus { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    [JsonPropertyName("created_at")] public DateTimeOffset CreatedAt { get; init; }
}

public sealed class TankCreateRequestDto
{
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("fuel_type_id")] public int FuelTypeId { get; init; }
    [JsonPropertyName("code")] public required string Code { get; init; }
    [JsonPropertyName("capacity_liters")] public decimal CapacityLiters { get; init; }
    [JsonPropertyName("current_level_liters")] public decimal CurrentLevelLiters { get; init; }
    [JsonPropertyName("minimum_safe_level")] public decimal MinimumSafeLevel { get; init; }
    [JsonPropertyName("critical_level")] public decimal CriticalLevel { get; init; }
    [JsonPropertyName("water_level")] public decimal WaterLevel { get; init; }
    [JsonPropertyName("temperature")] public decimal? Temperature { get; init; }
    [JsonPropertyName("sensor_status")] public string SensorStatus { get; init; } = "ACTIVE";
    [JsonPropertyName("is_active")] public bool IsActive { get; init; } = true;
}

public sealed class TankUpdateRequestDto
{
    [JsonPropertyName("station_id")] public int? StationId { get; init; }
    [JsonPropertyName("fuel_type_id")] public int? FuelTypeId { get; init; }
    [JsonPropertyName("code")] public string? Code { get; init; }
    [JsonPropertyName("capacity_liters")] public decimal? CapacityLiters { get; init; }
    [JsonPropertyName("current_level_liters")] public decimal? CurrentLevelLiters { get; init; }
    [JsonPropertyName("minimum_safe_level")] public decimal? MinimumSafeLevel { get; init; }
    [JsonPropertyName("critical_level")] public decimal? CriticalLevel { get; init; }
    [JsonPropertyName("water_level")] public decimal? WaterLevel { get; init; }
    [JsonPropertyName("temperature")] public decimal? Temperature { get; init; }
    [JsonPropertyName("sensor_status")] public string? SensorStatus { get; init; }
    [JsonPropertyName("is_active")] public bool? IsActive { get; init; }
}
