using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Live;

public sealed class SensorHistoryDto
{
    [JsonPropertyName("reading_timestamp")] public DateTimeOffset ReadingTimestamp { get; init; }
    [JsonPropertyName("flow_rate")] public decimal? FlowRate { get; init; }
    [JsonPropertyName("pressure")] public decimal? Pressure { get; init; }
    [JsonPropertyName("motor_current")] public decimal? MotorCurrent { get; init; }
    [JsonPropertyName("pump_temperature")] public decimal? PumpTemperature { get; init; }
}
