using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Stations;

public sealed class StationDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("code")] public required string Code { get; init; }
    [JsonPropertyName("name")] public required string Name { get; init; }
    [JsonPropertyName("city")] public required string City { get; init; }
    [JsonPropertyName("district")] public required string District { get; init; }
    [JsonPropertyName("address")] public required string Address { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    [JsonPropertyName("created_at")] public DateTimeOffset CreatedAt { get; init; }
}

public sealed class StationCreateRequestDto
{
    [JsonPropertyName("code")] public required string Code { get; init; }
    [JsonPropertyName("name")] public required string Name { get; init; }
    [JsonPropertyName("city")] public required string City { get; init; }
    [JsonPropertyName("district")] public required string District { get; init; }
    [JsonPropertyName("address")] public required string Address { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; } = true;
}

public sealed class StationUpdateRequestDto
{
    [JsonPropertyName("code")] public string? Code { get; init; }
    [JsonPropertyName("name")] public string? Name { get; init; }
    [JsonPropertyName("city")] public string? City { get; init; }
    [JsonPropertyName("district")] public string? District { get; init; }
    [JsonPropertyName("address")] public string? Address { get; init; }
    [JsonPropertyName("is_active")] public bool? IsActive { get; init; }
}
