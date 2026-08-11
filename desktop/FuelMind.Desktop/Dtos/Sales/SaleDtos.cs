using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Sales;

[JsonNumberHandling(JsonNumberHandling.AllowReadingFromString)]
public sealed class SaleDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("sale_timestamp")] public DateTimeOffset SaleTimestamp { get; init; }
    [JsonPropertyName("quantity_liters")] public decimal QuantityLiters { get; init; }
    [JsonPropertyName("total_amount")] public decimal TotalAmount { get; init; }
}
