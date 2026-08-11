using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Dashboard;

public sealed class DashboardSummaryDto
{
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("daily_sales_liters")] public decimal DailySalesLiters { get; init; }
    [JsonPropertyName("active_alarms")] public int ActiveAlarms { get; init; }
    [JsonPropertyName("critical_alarms")] public int CriticalAlarms { get; init; }
    [JsonPropertyName("risky_equipment")] public int RiskyEquipment { get; init; }
    [JsonPropertyName("station_health_score")] public int StationHealthScore { get; init; }
}
