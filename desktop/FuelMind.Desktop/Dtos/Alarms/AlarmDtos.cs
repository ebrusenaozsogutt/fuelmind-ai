using System.Text.Json;
using System.Text.Json.Serialization;
using System.Globalization;

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
    [JsonPropertyName("anomaly_score")] public decimal? AnomalyScore { get; init; }
    [JsonPropertyName("risk_level")] public string? RiskLevel { get; init; }
    [JsonPropertyName("decision_source")] public string? DecisionSource { get; init; }
    [JsonPropertyName("anomaly_type")] public string? AnomalyType { get; init; }
    [JsonPropertyName("model_version")] public string? ModelVersion { get; init; }
    [JsonPropertyName("model_outlier")] public bool? ModelOutlier { get; init; }
    [JsonPropertyName("triggered_rules_json")] public IReadOnlyList<string>? TriggeredRules { get; init; }
    [JsonPropertyName("findings_json")] public IReadOnlyList<AlarmFindingDto>? Findings { get; init; }
    [JsonPropertyName("recommended_checks_json")] public IReadOnlyList<string>? RecommendedChecks { get; init; }
    [JsonPropertyName("data_quality_note")] public string? DataQualityNote { get; init; }
    [JsonPropertyName("status")] public string? Status { get; init; }
    [JsonPropertyName("detected_at")] public DateTimeOffset DetectedAt { get; init; }
    [JsonPropertyName("resolution_note")] public string? ExistingResolutionNote { get; init; }

    public string TargetDisplay => PumpId is int pumpId
        ? $"Pompa #{pumpId}"
        : TankId is int tankId ? $"Tank #{tankId}" : $"İstasyon #{StationId}";
    public string TitleDisplay => AlarmUiText.Title(AlarmType, Title);
    public string AlarmTypeDisplay => AlarmUiText.AlarmType(AlarmType);
    public string DescriptionDisplay => AlarmUiText.Description(AlarmType, Description);
    public string RecommendedActionDisplay => AlarmUiText.RecommendedAction(AlarmType, RecommendedAction);
    public string ProbableCausesDisplay => string.Join("; ", ProbableCauses?
        .Select(cause => cause.DisplayDescription)
        .Where(text => !string.IsNullOrWhiteSpace(text)) ?? []);
    public string StatusDisplay => AlarmUiText.Status(Status);
    public string SeverityDisplay => AlarmUiText.Severity(Severity);
    public IReadOnlyList<string> FindingsDisplay => Findings?
        .Select(finding => finding.DisplayText)
        .Where(text => !string.IsNullOrWhiteSpace(text))
        .ToArray() ?? [];
    public IReadOnlyList<string> RecommendedChecksDisplay => AlarmUiText.LocalizeList(RecommendedChecks);
    public string? DataQualityNoteDisplay => AlarmUiText.Localize(DataQualityNote);
    public string AiRiskDisplay => AnomalyScore is decimal score ? $"{score:N0} / 100" : "—";
    public string RiskLevelDisplay => AlarmUiText.RiskLevel(RiskLevel);
    public string ModelVersionDisplay => string.IsNullOrWhiteSpace(ModelVersion) ? "—" : ModelVersion;
    public string AnomalyTypeDisplay => AlarmUiText.AnomalyType(AnomalyType);
    public bool HasAiAnalysis =>
        AnomalyScore is not null
        || !string.IsNullOrWhiteSpace(RiskLevel)
        || !string.IsNullOrWhiteSpace(DecisionSource)
        || !string.IsNullOrWhiteSpace(ModelVersion)
        || (Findings?.Count ?? 0) > 0
        || (RecommendedChecks?.Count ?? 0) > 0
        || !string.IsNullOrWhiteSpace(DataQualityNote);
    public bool HasNoAiAnalysis => !HasAiAnalysis;
    public string DecisionSourceDisplay => DecisionSource switch
    {
        "RULE" => "Kural — Fiziksel veya kural tabanlı sınır ihlali",
        "MODEL" => "Yapay zekâ modeli — Erken uyarı",
        "HYBRID" => "Hibrit — Kural ve yapay zekâ aynı yönde anomali tespit etti",
        "DATA_QUALITY" => "Veri kalitesi — Değerlendirme sınırlı",
        _ => "—",
    };
}

public sealed class AlarmCauseDto
{
    [JsonPropertyName("description")] public string? Description { get; init; }
    public string DisplayDescription => AlarmUiText.Localize(Description) ?? "Neden belirtilmedi.";
}

[JsonConverter(typeof(AlarmFindingDtoConverter))]
public sealed class AlarmFindingDto
{
    [JsonPropertyName("feature_name")] public string? FeatureName { get; init; }
    [JsonPropertyName("display_name")] public string? DisplayName { get; init; }
    [JsonPropertyName("current_value")] public decimal? CurrentValue { get; init; }
    [JsonPropertyName("reference_value")] public decimal? ReferenceValue { get; init; }
    [JsonPropertyName("absolute_difference")] public decimal? AbsoluteDifference { get; init; }
    [JsonPropertyName("percent_difference")] public decimal? PercentDifference { get; init; }
    [JsonPropertyName("direction")] public string? Direction { get; init; }
    [JsonPropertyName("message")] public string? Message { get; init; }

    public string DisplayText => AlarmUiText.Finding(this);
}

/// <summary>Reads both structured Stage 8.6 findings and legacy string findings.</summary>
public sealed class AlarmFindingDtoConverter : JsonConverter<AlarmFindingDto>
{
    public override AlarmFindingDto Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType == JsonTokenType.String)
        {
            return new AlarmFindingDto { Message = reader.GetString() };
        }

        if (reader.TokenType != JsonTokenType.StartObject)
        {
            throw new JsonException("Alarm finding must be an object or a text value.");
        }

        using var document = JsonDocument.ParseValue(ref reader);
        var item = document.RootElement;
        return new AlarmFindingDto
        {
            FeatureName = String(item, "feature_name"),
            DisplayName = String(item, "display_name"),
            CurrentValue = Decimal(item, "current_value"),
            ReferenceValue = Decimal(item, "reference_value"),
            AbsoluteDifference = Decimal(item, "absolute_difference"),
            PercentDifference = Decimal(item, "percent_difference"),
            Direction = String(item, "direction"),
            Message = String(item, "message"),
        };
    }

    public override void Write(Utf8JsonWriter writer, AlarmFindingDto value, JsonSerializerOptions options)
    {
        writer.WriteStartObject();
        Write(writer, "feature_name", value.FeatureName);
        Write(writer, "display_name", value.DisplayName);
        Write(writer, "current_value", value.CurrentValue);
        Write(writer, "reference_value", value.ReferenceValue);
        Write(writer, "absolute_difference", value.AbsoluteDifference);
        Write(writer, "percent_difference", value.PercentDifference);
        Write(writer, "direction", value.Direction);
        Write(writer, "message", value.Message);
        writer.WriteEndObject();
    }

    private static string? String(JsonElement element, string property) =>
        element.TryGetProperty(property, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() : null;

    private static decimal? Decimal(JsonElement element, string property) =>
        element.TryGetProperty(property, out var value) && value.ValueKind == JsonValueKind.Number
            && value.TryGetDecimal(out var parsed) ? parsed : null;

    private static void Write(Utf8JsonWriter writer, string property, string? value)
    {
        if (value is not null) writer.WriteString(property, value);
    }

    private static void Write(Utf8JsonWriter writer, string property, decimal? value)
    {
        if (value is decimal number) writer.WriteNumber(property, number);
    }
}

internal static class AlarmUiText
{
    private static readonly IReadOnlyDictionary<string, string> Titles = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
    {
        ["LOW_FLOW"] = "Pompa Debi Düşüşü",
        ["HIGH_MOTOR_CURRENT"] = "Yüksek Motor Akımı",
        ["HIGH_PRESSURE"] = "Yüksek Hat Basıncı",
        ["HIGH_WATER_LEVEL"] = "Yüksek Tank Su Seviyesi",
        ["SENSOR_STUCK"] = "Sensör Verisi Sabit",
        ["SENSOR_SPIKE"] = "Ani Sensör Değişimi",
        ["TANK_SALES_MISMATCH"] = "Tank ve Satış Uyuşmazlığı",
        ["LOW_DATA_QUALITY"] = "Düşük Veri Kalitesi",
        ["AI_ANOMALY"] = "Yapay Zekâ Erken Uyarısı",
    };

    private static readonly IReadOnlyDictionary<string, (string Description, string Action)> Guidance =
        new Dictionary<string, (string, string)>(StringComparer.OrdinalIgnoreCase)
        {
            ["LOW_FLOW"] = ("Pompa çalışırken debi, tanımlı alt sınırın altında kaldı.", "Pompa filtresini, hat basıncını ve pompa performansını kontrol edin."),
            ["HIGH_MOTOR_CURRENT"] = ("Pompa motor akımı, tanımlı çalışma sınırını aştı.", "Motor yükünü, mekanik sürtünmeyi ve pompanın çalışma koşullarını kontrol edin."),
            ["HIGH_PRESSURE"] = ("Pompa hat basıncı, tanımlı üst sınırı aştı.", "Hat basıncını, vana durumunu ve olası tıkanıklıkları kontrol edin."),
            ["HIGH_WATER_LEVEL"] = ("Tank su seviyesi kritik çalışma sınırının üzerine çıktı.", "Tank su seviyesini doğrulayın ve yakıt-su ayrışmasını kontrol edin."),
            ["SENSOR_STUCK"] = ("Satış sürerken ölçülen tank seviyesi olağandışı süre boyunca değişmedi.", "Tank seviye sensörünü ve sensör iletişimini kontrol edin."),
            ["SENSOR_SPIKE"] = ("Ölçümdeki ani değişim fiziksel akışla açıklanamıyor.", "Sensör bağlantısını ve kalibrasyonunu kontrol edin."),
            ["TANK_SALES_MISMATCH"] = ("Tank seviyesindeki düşüş satışlarla açıklanan miktardan daha fazla.", "Satış kayıtlarını tank seviyesiyle karşılaştırın; olası sızıntı veya ölçüm hatasını araştırın."),
            ["LOW_DATA_QUALITY"] = ("Etkilenen ekipmanın ölçümlerinde veri kalitesi sorunu algılandı.", "Sensör verisini, iletişimi ve son veri kalitesi işaretlerini kontrol edin."),
            ["AI_ANOMALY"] = ("Öğrenilen normal çalışma davranışından anlamlı bir sapma algılandı.", "Yapay zekâ bulgularını ve önerilen kontrolleri inceleyin."),
        };

    private static readonly IReadOnlyDictionary<string, string> LegacyTranslations =
        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["Filter blockage"] = "Filtre tıkanıklığı",
            ["Filter restriction"] = "Filtre kısıtlaması",
            ["Pump performance loss"] = "Pompa performans kaybı",
            ["Line pressure problem"] = "Hat basıncı sorunu",
            ["Excess motor load"] = "Aşırı motor yükü",
            ["Mechanical friction"] = "Mekanik sürtünme",
            ["Pump wear"] = "Pompa aşınması",
            ["Closed valve"] = "Kapalı vana",
            ["Line blockage"] = "Hat tıkanıklığı",
            ["Pressure sensor deviation"] = "Basınç sensörü sapması",
            ["Check the pump filter."] = "Pompa filtresini kontrol edin.",
            ["Pump flow rate is 43% below normal."] = "Pompa debisi normal seviyenin %43 altında.",
            ["Motor current is above its normal median reference."] = "Motor akımı öğrenilen olağan davranış aralığının üzerinde.",
            ["Sensor-data reliability is low; treat the AI risk as supporting information only."] = "Sensör verisinin güvenilirliği düşük; yapay zekâ riskini yalnızca destekleyici bilgi olarak değerlendirin.",
        };

    public static string Title(string? type, string? fallback) =>
        type is not null && Titles.TryGetValue(type, out var value)
            ? value
            : string.IsNullOrWhiteSpace(fallback) ? "Operasyon Uyarısı" : fallback;

    public static string AlarmType(string? value) => Title(value, value?.Replace('_', ' '));
    public static string Description(string? type, string? fallback) =>
        type is not null && Guidance.TryGetValue(type, out var value)
            ? value.Description
            : Localize(fallback) ?? "Açıklama bulunamadı.";
    public static string RecommendedAction(string? type, string? fallback) =>
        type is not null && Guidance.TryGetValue(type, out var value)
            ? value.Action
            : Localize(fallback) ?? "Öneri bulunamadı.";

    public static string Status(string? value) => value?.ToUpperInvariant() switch
    {
        "NEW" => "Yeni",
        "ACKNOWLEDGED" => "Onaylandı",
        "INVESTIGATING" => "İnceleniyor",
        "RESOLVED" => "Çözüldü",
        "FALSE_POSITIVE" => "Yanlış Alarm",
        _ => "—",
    };

    public static string Severity(string? value) => value?.ToUpperInvariant() switch
    {
        "LOW" => "Düşük",
        "MEDIUM" => "Orta",
        "HIGH" => "Yüksek",
        "CRITICAL" => "Kritik",
        _ => "—",
    };

    public static string RiskLevel(string? value) => value?.ToUpperInvariant() switch
    {
        "NORMAL" => "Normal",
        "WATCH" => "İzle",
        "MEDIUM" => "Orta",
        "HIGH" => "Yüksek",
        "CRITICAL" => "Kritik",
        _ => "—",
    };

    public static string AnomalyType(string? value) => value?.ToUpperInvariant() switch
    {
        "EQUIPMENT_ANOMALY" => "Ekipman anomalisi",
        "PROCESS_ANOMALY" => "Süreç anomalisi",
        "DATA_QUALITY" => "Veri kalitesi",
        null or "" => "—",
        _ => value.Replace('_', ' '),
    };

    public static string? Localize(string? value) =>
        string.IsNullOrWhiteSpace(value) ? value : LegacyTranslations.TryGetValue(value, out var translated) ? translated : value;

    public static IReadOnlyList<string> LocalizeList(IReadOnlyList<string>? values) =>
        values?.Select(item => Localize(item) ?? string.Empty).Where(item => item.Length > 0).ToArray() ?? [];

    public static string Finding(AlarmFindingDto finding)
    {
        if (finding.CurrentValue is not decimal current || finding.ReferenceValue is not decimal reference)
        {
            return Localize(finding.Message) ?? "Bulgu ayrıntısı bulunamadı.";
        }

        var name = string.IsNullOrWhiteSpace(finding.DisplayName) ? "Ölçüm" : finding.DisplayName;
        var unit = FindingUnit(finding.FeatureName);
        var percent = finding.PercentDifference is decimal difference
            ? $"%{Math.Abs(difference).ToString("N0", CultureInfo.InvariantCulture)} {FindingDirection(finding.Direction, difference)}"
            : "Referansla sayısal olarak karşılaştırılamıyor";
        return $"{name}\nMevcut: {current.ToString("N1", CultureInfo.InvariantCulture)}{unit}\nNormal referans: {reference.ToString("N1", CultureInfo.InvariantCulture)}{unit}\nSapma: {percent}";
    }

    private static string FindingDirection(string? direction, decimal difference) =>
        (direction ?? (difference < 0 ? "LOW" : "HIGH")).ToUpperInvariant() switch
        {
            "LOW" => "düşük",
            "HIGH" => "yüksek",
            _ => "farklı",
        };

    private static string FindingUnit(string? featureName) => featureName?.ToLowerInvariant() switch
    {
        "flow_rate" or "flow_rate_change_5min" or "average_flow_rate_30min" => " L/dk",
        "pressure" or "pressure_std_30min" => " bar",
        "motor_current" or "motor_current_change_5min" => " A",
        "pump_temperature" or "temperature" => " °C",
        "tank_level" or "true_tank_level" or "water_level" => " L",
        _ => string.Empty,
    };
}

public sealed record AlarmResolutionRequest(
    [property: JsonPropertyName("resolution_note")] string? ResolutionNote);
