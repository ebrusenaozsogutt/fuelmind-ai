using System.Text.Json;

namespace FuelMind.Desktop.Dtos.Reports;

public sealed class ReportRowDto
{
    public string Date { get; init; } = ""; public string Station { get; init; } = ""; public string Pump { get; init; } = "";
    public string Nozzle { get; init; } = ""; public string Attendant { get; init; } = ""; public string Shift { get; init; } = "";
    public string Fuel { get; init; } = ""; public string Liters { get; init; } = ""; public string UnitPrice { get; init; } = "";
    public string TotalAmount { get; init; } = ""; public string Customer { get; init; } = ""; public string Plate { get; init; } = "";
    public string Card { get; init; } = ""; public string Status { get; init; } = ""; public string Details { get; init; } = "";
    public static ReportRowDto From(JsonElement item)
    {
        string Get(params string[] keys) { foreach (var key in keys) if (item.TryGetProperty(key, out var value)) return value.ToString(); return ""; }
        return new() { Date = Get("timestamp", "sale_timestamp", "detected_at", "started_at"), Station = Get("station"), Pump = Get("pump", "pump_code"), Nozzle = Get("nozzle", "nozzle_code"), Attendant = Get("attendant", "attendant_name"), Shift = Get("shift", "shift_name"), Fuel = Get("fuel_type", "fuel_type_name"), Liters = Get("liters", "quantity_liters", "total_liters"), UnitPrice = Get("unit_price"), TotalAmount = Get("total_amount"), Customer = Get("customer", "customer_name"), Plate = Get("plate"), Card = Get("card", "card_code"), Status = Get("sale_status", "status"), Details = item.ToString() };
    }
}
