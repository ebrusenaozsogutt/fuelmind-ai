using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Faults;

public sealed class FaultDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("alarm_id")] public int? AlarmId { get; init; }
    [JsonPropertyName("target_type")] public string TargetType { get; init; } = "";
    [JsonPropertyName("target_id")] public int TargetId { get; init; }
    [JsonPropertyName("fault_type")] public string FaultType { get; init; } = "";
    [JsonPropertyName("fault_code")] public string FaultCode { get; init; } = "";
    [JsonPropertyName("title")] public string Title { get; init; } = "";
    [JsonPropertyName("description")] public string? Description { get; init; }
    [JsonPropertyName("cause")] public string? Cause { get; init; }
    [JsonPropertyName("status")] public string Status { get; init; } = "";
    [JsonPropertyName("started_at")] public DateTimeOffset StartedAt { get; init; }
    [JsonPropertyName("detected_at")] public DateTimeOffset DetectedAt { get; init; }
    [JsonPropertyName("resolved_at")] public DateTimeOffset? ResolvedAt { get; init; }
    [JsonPropertyName("resolution_note")] public string? ResolutionNote { get; init; }
    [JsonPropertyName("resolved_by")] public int? ResolvedBy { get; init; }
    [JsonPropertyName("resolved_by_name")] public string? ResolvedByName { get; init; }
}

public sealed class FaultCreateDto
{
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("alarm_id")] public int? AlarmId { get; init; }
    [JsonPropertyName("target_type")] public string TargetType { get; init; } = "";
    [JsonPropertyName("target_id")] public int TargetId { get; init; }
    [JsonPropertyName("fault_type")] public string FaultType { get; init; } = "";
    [JsonPropertyName("fault_code")] public string FaultCode { get; init; } = "";
    [JsonPropertyName("title")] public string Title { get; init; } = "";
    [JsonPropertyName("description")] public string? Description { get; init; }
    [JsonPropertyName("cause")] public string? Cause { get; init; }
    [JsonPropertyName("started_at")] public DateTimeOffset StartedAt { get; init; } = DateTimeOffset.UtcNow;
    [JsonPropertyName("detected_at")] public DateTimeOffset DetectedAt { get; init; } = DateTimeOffset.UtcNow;
}

public sealed class FaultResolutionDto { [JsonPropertyName("resolution_note")] public string ResolutionNote { get; init; } = ""; }
public sealed record FaultTargetOption(int Id, string DisplayName);

internal sealed class DeviceControllerTargetDto { [JsonPropertyName("id")] public int Id { get; init; } [JsonPropertyName("code")] public string Code { get; init; } = ""; [JsonPropertyName("name")] public string Name { get; init; } = ""; }
internal sealed class CommunicationPortTargetDto { [JsonPropertyName("id")] public int Id { get; init; } [JsonPropertyName("station_id")] public int StationId { get; init; } [JsonPropertyName("port_number")] public int PortNumber { get; init; } [JsonPropertyName("name")] public string Name { get; init; } = ""; }
internal sealed class NozzleTargetDto { [JsonPropertyName("id")] public int Id { get; init; } [JsonPropertyName("pump_id")] public int PumpId { get; init; } [JsonPropertyName("code")] public string Code { get; init; } = ""; [JsonPropertyName("nozzle_number")] public int NozzleNumber { get; init; } }
internal sealed class ProbeTargetDto { [JsonPropertyName("id")] public int Id { get; init; } [JsonPropertyName("tank_id")] public int TankId { get; init; } [JsonPropertyName("code")] public string Code { get; init; } = ""; [JsonPropertyName("name")] public string Name { get; init; } = ""; }
