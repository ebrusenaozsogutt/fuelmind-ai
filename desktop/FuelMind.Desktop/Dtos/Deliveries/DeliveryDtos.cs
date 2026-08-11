using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Deliveries;

public sealed class CreateDeliveryRequestDto
{
    [JsonPropertyName("tank_id")]
    public int TankId { get; init; }

    [JsonPropertyName("delivery_timestamp")]
    public DateTimeOffset DeliveryTimestamp { get; init; }

    [JsonPropertyName("quantity_liters")]
    public decimal QuantityLiters { get; init; }

    [JsonPropertyName("supplier_name")]
    public string SupplierName { get; init; } = "Demo stock preparation";
}
[JsonNumberHandling(JsonNumberHandling.AllowReadingFromString)]
public sealed class DeliveryDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("tank_id")] public int TankId { get; init; }
    [JsonPropertyName("delivery_timestamp")] public DateTimeOffset DeliveryTimestamp { get; init; }
    [JsonPropertyName("quantity_liters")] public decimal QuantityLiters { get; init; }
    [JsonPropertyName("level_before")] public decimal LevelBefore { get; init; }
    [JsonPropertyName("level_after")] public decimal LevelAfter { get; init; }
    [JsonPropertyName("supplier_name")] public string? SupplierName { get; init; }
    [JsonPropertyName("created_at")] public DateTimeOffset CreatedAt { get; init; }
}
