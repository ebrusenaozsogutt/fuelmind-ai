using System.Globalization;
using System.Text.Json;

namespace FuelMind.Desktop.Dtos.Reports;

/// <summary>Preserves every existing report field so each report can choose its own visible columns.</summary>
public sealed class ReportRowDto
{
    private readonly Dictionary<string, string> _values = new(StringComparer.OrdinalIgnoreCase);

    public string this[string key] => _values.GetValueOrDefault(key, "—");
    public IReadOnlyDictionary<string, string> Values => _values;

    // Kept for existing callers that use the original common report fields.
    public string Date => First("timestamp", "sale_timestamp", "detected_at", "started_at");
    public string Station => First("station");
    public string Pump => First("pump", "pump_code");
    public string Nozzle => First("nozzle", "nozzle_code");
    public string Attendant => First("attendant", "attendant_name");
    public string Shift => First("shift", "shift_name");
    public string Fuel => First("fuel_type", "fuel_type_name");
    public string Liters => First("liters", "quantity_liters", "total_liters");
    public string UnitPrice => First("unit_price");
    public string TotalAmount => First("total_amount");
    public string Customer => First("customer", "customer_name");
    public string Plate => First("plate");
    public string Card => First("card", "card_code");
    public string Status => First("sale_status", "status");
    public string Details => string.Join("; ", _values.Select(item => $"{item.Key}={item.Value}"));

    public static ReportRowDto From(JsonElement item)
    {
        var row = new ReportRowDto();
        if (item.ValueKind != JsonValueKind.Object)
        {
            row._values["result"] = Format(item);
            return row;
        }

        foreach (var property in item.EnumerateObject()) row._values[property.Name] = Format(property.Value);
        return row;
    }

    private string First(params string[] keys) => keys.Select(key => _values.GetValueOrDefault(key)).FirstOrDefault(value => !string.IsNullOrEmpty(value)) ?? "";

    private static string Format(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.Null or JsonValueKind.Undefined => "—",
        JsonValueKind.String => FormatString(value.GetString()),
        JsonValueKind.Array => string.Join(" | ", value.EnumerateArray().Select(Format)),
        JsonValueKind.Object => string.Join("; ", value.EnumerateObject().Select(item => $"{item.Name}: {Format(item.Value)}")),
        JsonValueKind.True => "Evet",
        JsonValueKind.False => "Hayır",
        _ => value.GetRawText(),
    };

    private static string FormatString(string? value)
    {
        if (string.IsNullOrWhiteSpace(value)) return "—";
        return DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var date)
            ? date.LocalDateTime.ToString("dd.MM.yyyy HH:mm", CultureInfo.CurrentCulture)
            : value;
    }
}

public sealed record ReportColumnDefinition(string Key, string Header, double Width = 1);
