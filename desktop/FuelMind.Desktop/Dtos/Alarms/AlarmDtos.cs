using System.Text.Json.Serialization;
namespace FuelMind.Desktop.Dtos.Alarms;
public sealed class AlarmDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("tank_id")] public int? TankId { get; init; }
    [JsonPropertyName("pump_id")] public int? PumpId { get; init; }
    [JsonPropertyName("alarm_type")] public string? AlarmType { get; init; }
    [JsonPropertyName("severity")] public string? Severity { get; init; }
    [JsonPropertyName("title")] public string? Title { get; init; }
    [JsonPropertyName("description")] public string? Description { get; init; }
    [JsonPropertyName("recommended_action")] public string? RecommendedAction { get; init; }
    [JsonPropertyName("probable_causes")] public IReadOnlyList<AlarmCauseDto>? ProbableCauses { get; init; }
    [JsonPropertyName("status")] public string? Status { get; init; }
    [JsonPropertyName("detected_at")] public DateTimeOffset DetectedAt { get; init; }
    [JsonPropertyName("resolution_note")] public string? ExistingResolutionNote { get; init; }
    public string TargetDisplay => PumpId is int pumpId ? $"Pompa #{pumpId}" : TankId is int tankId ? $"Tank #{tankId}" : $"İstasyon #{StationId}";
    public string RecommendedActionDisplay => string.IsNullOrWhiteSpace(RecommendedAction) ? "Öneri bulunamadı." : RecommendedAction;
}
public sealed class AlarmCauseDto { [JsonPropertyName("description")] public string? Description { get; init; } }
public sealed record AlarmResolutionRequest([property: JsonPropertyName("resolution_note")] string? ResolutionNote);
