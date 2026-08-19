using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Live;

public sealed class ControllerLiveDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("code")] public string? Code { get; init; }
    [JsonPropertyName("name")] public string? Name { get; init; }
    [JsonPropertyName("controller_type")] public string? ControllerType { get; init; }
    [JsonPropertyName("status")] public string? Status { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    [JsonPropertyName("last_communication_at")] public DateTimeOffset? LastCommunicationAt { get; init; }
}

public sealed class CommunicationPortLiveDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("controller_id")] public int ControllerId { get; init; }
    [JsonPropertyName("port_number")] public int PortNumber { get; init; }
    [JsonPropertyName("name")] public string? Name { get; init; }
    [JsonPropertyName("port_type")] public string? PortType { get; init; }
    [JsonPropertyName("protocol")] public string? Protocol { get; init; }
    [JsonPropertyName("baud_rate")] public int? BaudRate { get; init; }
    [JsonPropertyName("status")] public string? Status { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    [JsonPropertyName("last_communication_at")] public DateTimeOffset? LastCommunicationAt { get; init; }
}

public sealed class ProbeLiveDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("tank_id")] public int TankId { get; init; }
    [JsonPropertyName("communication_port_id")] public int? CommunicationPortId { get; init; }
    [JsonPropertyName("code")] public string? Code { get; init; }
    [JsonPropertyName("name")] public string? Name { get; init; }
    [JsonPropertyName("status")] public string? Status { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    [JsonPropertyName("last_communication_at")] public DateTimeOffset? LastCommunicationAt { get; init; }
    [JsonPropertyName("fuel_height_mm")] public decimal? FuelHeightMm { get; init; }
    [JsonPropertyName("fuel_volume_liters")] public decimal? FuelVolumeLiters { get; init; }
    [JsonPropertyName("water_height_mm")] public decimal? WaterHeightMm { get; init; }
    [JsonPropertyName("water_volume_liters")] public decimal? WaterVolumeLiters { get; init; }
    [JsonPropertyName("temperature_celsius")] public decimal? TemperatureCelsius { get; init; }
    [JsonPropertyName("data_quality_score")] public decimal? DataQualityScore { get; init; }
    [JsonPropertyName("quality_flags")] public IReadOnlyList<string> QualityFlags { get; init; } = [];
    [JsonPropertyName("reading_timestamp")] public DateTimeOffset? ReadingTimestamp { get; init; }
}

public sealed class NozzleLiveDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("pump_id")] public int PumpId { get; init; }
    [JsonPropertyName("fuel_type_id")] public int FuelTypeId { get; init; }
    [JsonPropertyName("code")] public string? Code { get; init; }
    [JsonPropertyName("nozzle_number")] public int NozzleNumber { get; init; }
    [JsonPropertyName("status")] public string? Status { get; init; }
    [JsonPropertyName("totalizer_liters")] public decimal TotalizerLiters { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    [JsonPropertyName("fuel_type_code")] public string? FuelTypeCode { get; init; }
    [JsonPropertyName("fuel_type_name")] public string? FuelTypeName { get; init; }
}

public sealed class StationLiveStatusDto
{
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("latest_sequence")] public int? LatestSequence { get; init; }
    [JsonPropertyName("latest_reading_time")] public DateTimeOffset? LatestReadingTime { get; init; }
    [JsonPropertyName("tanks")] public IReadOnlyList<SensorHistoryDto> Tanks { get; init; } = [];
    [JsonPropertyName("pumps")] public IReadOnlyList<SensorHistoryDto> Pumps { get; init; } = [];
    [JsonPropertyName("controllers")] public IReadOnlyList<ControllerLiveDto> Controllers { get; init; } = [];
    [JsonPropertyName("ports")] public IReadOnlyList<CommunicationPortLiveDto> Ports { get; init; } = [];
    [JsonPropertyName("probes")] public IReadOnlyList<ProbeLiveDto> Probes { get; init; } = [];
    [JsonPropertyName("nozzles")] public IReadOnlyList<NozzleLiveDto> Nozzles { get; init; } = [];
}
