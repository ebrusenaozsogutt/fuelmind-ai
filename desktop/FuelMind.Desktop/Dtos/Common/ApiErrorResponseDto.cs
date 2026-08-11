using System.Text.Json;
using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Common;

public sealed class ApiErrorResponseDto
{
    [JsonPropertyName("error")]
    public ApiErrorDto? Error { get; init; }
}

public sealed class ApiErrorDto
{
    [JsonPropertyName("code")]
    public string? Code { get; init; }

    [JsonPropertyName("message")]
    public string? Message { get; init; }

    [JsonPropertyName("details")]
    public JsonElement? Details { get; init; }
}
