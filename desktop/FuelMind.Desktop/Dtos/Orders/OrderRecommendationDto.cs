using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Orders;

public sealed class OrderRecommendationDto
{
    [JsonPropertyName("tank_id")] public int TankId { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("current_stock_liters")] public decimal CurrentStockLiters { get; init; }
    [JsonPropertyName("minimum_safe_stock_liters")] public decimal MinimumSafeStockLiters { get; init; }
    [JsonPropertyName("recommended_quantity")] public decimal RecommendedQuantity { get; init; }
    [JsonPropertyName("recommended_order_date")] public DateOnly RecommendedOrderDate { get; init; }
    [JsonPropertyName("recommended_delivery_date")] public DateOnly RecommendedDeliveryDate { get; init; }
    [JsonPropertyName("critical_stock_date")] public DateOnly? CriticalStockDate { get; init; }
    [JsonPropertyName("confidence_score")] public decimal ConfidenceScore { get; init; }
    [JsonPropertyName("priority")] public string Priority { get; init; } = "LOW";
    [JsonPropertyName("status")] public string Status { get; init; } = "";
    [JsonPropertyName("explanation")] public string? Explanation { get; init; }
}
