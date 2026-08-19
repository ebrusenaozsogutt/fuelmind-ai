using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Live;

public sealed class SensorHistoryDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("tank_id")] public int? TankId { get; init; }
    [JsonPropertyName("pump_id")] public int? PumpId { get; init; }
    [JsonPropertyName("communication_port_id")] public int? CommunicationPortId { get; init; }
    [JsonPropertyName("reading_timestamp")] public DateTimeOffset ReadingTimestamp { get; init; }
    [JsonPropertyName("flow_rate")] public decimal? FlowRate { get; init; }
    [JsonPropertyName("pressure")] public decimal? Pressure { get; init; }
    [JsonPropertyName("motor_current")] public decimal? MotorCurrent { get; init; }
    [JsonPropertyName("pump_temperature")] public decimal? PumpTemperature { get; init; }
}
