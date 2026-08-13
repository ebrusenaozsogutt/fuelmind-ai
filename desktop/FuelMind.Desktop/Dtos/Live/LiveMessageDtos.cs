using System.Text.Json;
using System.Text.Json.Serialization;
using FuelMind.Desktop.Dtos.Alarms;

namespace FuelMind.Desktop.Dtos.Live;

public sealed class LiveMessageEnvelopeDto { [JsonPropertyName("event_type")] public string? EventType { get; init; } }
public sealed class ConnectionReadyDto { [JsonPropertyName("event_type")] public string? EventType { get; init; } [JsonPropertyName("station_id")] public int StationId { get; init; } [JsonPropertyName("generated_at")] public DateTimeOffset GeneratedAt { get; init; } }
public sealed class PingDto { [JsonPropertyName("event_type")] public string? EventType { get; init; } [JsonPropertyName("generated_at")] public DateTimeOffset GeneratedAt { get; init; } }
public sealed class AlarmCreatedDto { [JsonPropertyName("event_type")] public string? EventType { get; init; } [JsonPropertyName("alarm_id")] public int AlarmId { get; init; } [JsonPropertyName("station_id")] public int StationId { get; init; } [JsonPropertyName("tank_id")] public int? TankId { get; init; } [JsonPropertyName("pump_id")] public int? PumpId { get; init; } [JsonPropertyName("alarm_type")] public string? AlarmType { get; init; } [JsonPropertyName("severity")] public string? Severity { get; init; } [JsonPropertyName("title")] public string? Title { get; init; } [JsonPropertyName("description")] public string? Description { get; init; } [JsonPropertyName("anomaly_type")] public string? AnomalyType { get; init; } [JsonPropertyName("recommended_action")] public string? RecommendedAction { get; init; } [JsonPropertyName("probable_causes")] public IReadOnlyList<AlarmCauseDto>? ProbableCauses { get; init; } [JsonPropertyName("anomaly_score")] public decimal? AnomalyScore { get; init; } [JsonPropertyName("risk_level")] public string? RiskLevel { get; init; } [JsonPropertyName("decision_source")] public string? DecisionSource { get; init; } [JsonPropertyName("model_version")] public string? ModelVersion { get; init; } [JsonPropertyName("model_outlier")] public bool? ModelOutlier { get; init; } [JsonPropertyName("triggered_rules")] public IReadOnlyList<string> TriggeredRules { get; init; } = []; [JsonPropertyName("findings")] public IReadOnlyList<AlarmFindingDto> Findings { get; init; } = []; [JsonPropertyName("recommended_checks")] public IReadOnlyList<string> RecommendedChecks { get; init; } = []; [JsonPropertyName("data_quality_note")] public string? DataQualityNote { get; init; } [JsonPropertyName("status")] public string? Status { get; init; } [JsonPropertyName("detected_at")] public DateTimeOffset DetectedAt { get; init; } }
public sealed class SimulationTickDto
{
    [JsonPropertyName("event_type")] public string? EventType { get; init; }
    [JsonPropertyName("simulation_run_id")] public int SimulationRunId { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("simulation_time")] public DateTimeOffset SimulationTime { get; init; }
    [JsonPropertyName("sequence")] public int Sequence { get; init; }
    [JsonPropertyName("tanks")] public IReadOnlyList<TankLiveDataDto> Tanks { get; init; } = [];
    [JsonPropertyName("pumps")] public IReadOnlyList<PumpLiveDataDto> Pumps { get; init; } = [];
    [JsonPropertyName("sales")] public IReadOnlyList<LiveSaleDto> Sales { get; init; } = [];
    [JsonPropertyName("events")] public IReadOnlyList<LiveEventDto> Events { get; init; } = [];
    [JsonPropertyName("active_scenarios")] public IReadOnlyList<JsonElement> ActiveScenarios { get; init; } = [];
    [JsonPropertyName("ai_results")] public IReadOnlyList<LiveAnomalyResultDto> AiResults { get; init; } = [];
    [JsonPropertyName("generated_at")] public DateTimeOffset GeneratedAt { get; init; }
}
public sealed class AnomalyEvaluationDto
{
    [JsonPropertyName("event_type")] public string? EventType { get; init; }
    [JsonPropertyName("simulation_run_id")] public int SimulationRunId { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("simulation_time")] public DateTimeOffset SimulationTime { get; init; }
    [JsonPropertyName("sequence")] public int Sequence { get; init; }
    [JsonPropertyName("results")] public IReadOnlyList<LiveAnomalyResultDto> Results { get; init; } = [];
}
public sealed class TankLiveDataDto { [JsonPropertyName("tank_id")] public int TankId { get; init; } [JsonPropertyName("fuel_type_id")] public int FuelTypeId { get; init; } [JsonPropertyName("code")] public string? Code { get; init; } [JsonPropertyName("true_level_liters")] public decimal TrueLevelLiters { get; init; } [JsonPropertyName("measured_level_liters")] public decimal MeasuredLevelLiters { get; init; } [JsonPropertyName("capacity_liters")] public decimal CapacityLiters { get; init; } [JsonPropertyName("temperature")] public decimal? Temperature { get; init; } [JsonPropertyName("water_level")] public decimal WaterLevel { get; init; } [JsonIgnore] public LiveAnomalyResultDto? AiAnalysis { get; set; } }
public sealed class PumpLiveDataDto { [JsonPropertyName("pump_id")] public int PumpId { get; init; } [JsonPropertyName("tank_id")] public int TankId { get; init; } [JsonPropertyName("status")] public string? Status { get; init; } [JsonPropertyName("flow_rate")] public decimal FlowRate { get; init; } [JsonPropertyName("pressure")] public decimal Pressure { get; init; } [JsonPropertyName("motor_current")] public decimal MotorCurrent { get; init; } [JsonPropertyName("temperature")] public decimal? Temperature { get; init; } [JsonPropertyName("error_count")] public int ErrorCount { get; init; } [JsonPropertyName("working_duration")] public decimal WorkingDuration { get; init; } [JsonIgnore] public LiveAnomalyResultDto? AiAnalysis { get; set; } }
public sealed class LiveAnomalyResultDto
{
    [JsonPropertyName("entity_type")] public string? EntityType { get; init; }
    [JsonPropertyName("entity_id")] public int EntityId { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("timestamp")] public DateTimeOffset Timestamp { get; init; }
    [JsonPropertyName("ai_state")] public string? AiState { get; init; }
    [JsonPropertyName("risk_score")] public decimal? RiskScore { get; init; }
    [JsonPropertyName("risk_level")] public string? RiskLevel { get; init; }
    [JsonPropertyName("decision_source")] public string? DecisionSource { get; init; }
    [JsonPropertyName("severity")] public string? Severity { get; init; }
    [JsonPropertyName("anomaly_type")] public string? AnomalyType { get; init; }
    [JsonPropertyName("model_outlier")] public bool? ModelOutlier { get; init; }
    [JsonPropertyName("triggered_rules")] public IReadOnlyList<string> TriggeredRules { get; init; } = [];
    [JsonPropertyName("findings")] public IReadOnlyList<AlarmFindingDto> Findings { get; init; } = [];
    public IReadOnlyList<string> FindingsDisplay => Findings.Select(finding => finding.DisplayText).ToArray();
    [JsonPropertyName("probable_causes")] public IReadOnlyList<string> ProbableCauses { get; init; } = [];
    [JsonPropertyName("recommended_checks")] public IReadOnlyList<string> RecommendedChecks { get; init; } = [];
    [JsonPropertyName("data_quality_note")] public string? DataQualityNote { get; init; }
    [JsonPropertyName("model_version")] public string? ModelVersion { get; init; }
    [JsonPropertyName("decision_function")] public double? DecisionFunction { get; init; }
    [JsonPropertyName("is_anomaly")] public bool IsAnomaly { get; init; }
    public string RiskDisplay => RiskScore is decimal score ? $"{score:N0} / 100" : "—";
    public string StateDisplay => AiState switch { "WARMING_UP" => "Geçmiş verisi toplanıyor…", "NO_ACTIVE_MODEL" => "Aktif yapay zekâ modeli yok", "UNAVAILABLE" => "Yapay zekâ geçici olarak kullanılamıyor", _ => RiskLevel ?? "Henüz hesaplanmadı" };
    public string PumpBadgeDisplay => RiskScore is decimal score
        ? $"Risk: {score:N0} ({RiskLevel ?? "Hesaplandı"})"
        : StateDisplay;
    public string DecisionSourceDisplay => DecisionSource switch
    {
        "RULE" => "Kural",
        "MODEL" => "Yapay zekâ modeli",
        "HYBRID" => "Kural + yapay zekâ",
        "DATA_QUALITY" => "Veri kalitesi",
        _ => "Henüz belirlenmedi",
    };
}
public sealed class LiveSaleDto { [JsonPropertyName("sale_id")] public string? SaleId { get; init; } [JsonPropertyName("pump_id")] public int PumpId { get; init; } [JsonPropertyName("tank_id")] public int TankId { get; init; } [JsonPropertyName("fuel_type_id")] public int FuelTypeId { get; init; } [JsonPropertyName("quantity_liters")] public decimal QuantityLiters { get; init; } [JsonPropertyName("started_at")] public DateTimeOffset StartedAt { get; init; } [JsonPropertyName("completed_at")] public DateTimeOffset CompletedAt { get; init; } }
public sealed class LiveEventDto { [JsonPropertyName("event_type")] public string? EventType { get; init; } [JsonPropertyName("target_type")] public string? TargetType { get; init; } [JsonPropertyName("target_id")] public int TargetId { get; init; } [JsonPropertyName("event_timestamp")] public DateTimeOffset EventTimestamp { get; init; } [JsonPropertyName("payload")] public JsonElement Payload { get; init; } }
