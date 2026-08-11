using System.Text.Json;
using FuelMind.Desktop.Dtos.Live;

namespace FuelMind.Desktop.Services;

public sealed class LiveMessageParser(JsonSerializerOptions jsonOptions)
{
    public LiveMessageParseResult Parse(string rawJson)
    {
        try
        {
            var envelope = JsonSerializer.Deserialize<LiveMessageEnvelopeDto>(rawJson, jsonOptions);
            return envelope?.EventType switch
            {
                "connection_ready" => Create<ConnectionReadyDto>(rawJson, envelope.EventType),
                "simulation_tick" => Create<SimulationTickDto>(rawJson, envelope.EventType),
                "alarm_created" => Create<AlarmCreatedDto>(rawJson, envelope.EventType),
                "ping" => Create<PingDto>(rawJson, envelope.EventType),
                null or "" => LiveMessageParseResult.Invalid("Missing event_type."),
                _ => LiveMessageParseResult.Unknown(envelope.EventType),
            };
        }
        catch (JsonException) { return LiveMessageParseResult.Invalid("Invalid live message JSON."); }
    }
    private LiveMessageParseResult Create<T>(string rawJson, string eventType) => JsonSerializer.Deserialize<T>(rawJson, jsonOptions) is { } message ? LiveMessageParseResult.Parsed(eventType, message) : LiveMessageParseResult.Invalid("Empty live message.");
}
public sealed record LiveMessageParseResult(string? EventType, object? Message, string? Error, bool IsUnknown)
{ public static LiveMessageParseResult Parsed(string type, object message) => new(type, message, null, false); public static LiveMessageParseResult Unknown(string type) => new(type, null, null, true); public static LiveMessageParseResult Invalid(string error) => new(null, null, error, false); }
