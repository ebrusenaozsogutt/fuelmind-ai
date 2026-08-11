using System.Net;
using System.Text.Json;

namespace FuelMind.Desktop.Services;

public sealed class ApiException : Exception
{
    public ApiException(
        HttpStatusCode statusCode,
        string errorCode,
        string message,
        JsonElement? details = null)
        : base(message)
    {
        StatusCode = statusCode;
        ErrorCode = errorCode;
        Details = details;
    }

    public HttpStatusCode StatusCode { get; }

    public string ErrorCode { get; }

    public JsonElement? Details { get; }
}
