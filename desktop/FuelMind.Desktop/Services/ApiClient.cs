using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using FuelMind.Desktop.Dtos.Common;
using FuelMind.Desktop.State;
using Microsoft.Extensions.Logging;

namespace FuelMind.Desktop.Services;

public sealed class ApiClient
{
    private readonly HttpClient _httpClient;
    private readonly JsonSerializerOptions _jsonOptions;
    private readonly AuthState _authState;
    private readonly ILogger<ApiClient> _logger;

    public ApiClient(HttpClient httpClient, JsonSerializerOptions jsonOptions, AuthState authState, ILogger<ApiClient> logger)
    {
        _httpClient = httpClient;
        _authState = authState;
        _logger = logger;
        _jsonOptions = new JsonSerializerOptions(jsonOptions)
        {
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        };
    }

    public Task<T> GetAsync<T>(string relativePath, CancellationToken cancellationToken = default) =>
        SendAsync<T>(HttpMethod.Get, relativePath, content: null, cancellationToken);

    public Task<TResponse> PostAsync<TRequest, TResponse>(
        string relativePath,
        TRequest request,
        CancellationToken cancellationToken = default) =>
        SendAsync<TResponse>(HttpMethod.Post, relativePath, CreateJsonContent(request), cancellationToken);

    public Task<TResponse> PostAsync<TResponse>(
        string relativePath,
        CancellationToken cancellationToken = default) =>
        SendAsync<TResponse>(HttpMethod.Post, relativePath, content: null, cancellationToken);

    public Task<TResponse> PutAsync<TRequest, TResponse>(
        string relativePath,
        TRequest request,
        CancellationToken cancellationToken = default) =>
        SendAsync<TResponse>(HttpMethod.Put, relativePath, CreateJsonContent(request), cancellationToken);

    public Task<TResponse> PatchAsync<TRequest, TResponse>(
        string relativePath,
        TRequest request,
        CancellationToken cancellationToken = default) =>
        SendAsync<TResponse>(HttpMethod.Patch, relativePath, CreateJsonContent(request), cancellationToken);

    public Task<TResponse> PatchAsync<TResponse>(
        string relativePath,
        CancellationToken cancellationToken = default) =>
        SendAsync<TResponse>(HttpMethod.Patch, relativePath, content: null, cancellationToken);

    public async Task DeleteAsync(string relativePath, CancellationToken cancellationToken = default)
    {
        using var response = await SendRequestAsync(
            HttpMethod.Delete, relativePath, content: null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
    }

    public async Task<byte[]> DownloadAsync(string relativePath, CancellationToken cancellationToken = default)
    {
        using var response = await SendRequestAsync(HttpMethod.Get, relativePath, content: null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return await response.Content.ReadAsByteArrayAsync(cancellationToken);
    }

    private async Task<T> SendAsync<T>(
        HttpMethod method,
        string relativePath,
        HttpContent? content,
        CancellationToken cancellationToken)
    {
        using var response = await SendRequestAsync(method, relativePath, content, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);

        await using var responseStream = await response.Content.ReadAsStreamAsync(cancellationToken);
        var result = await JsonSerializer.DeserializeAsync<T>(responseStream, _jsonOptions, cancellationToken);
        return result ?? throw new ApiException(
            response.StatusCode,
            "INVALID_RESPONSE",
            "The API returned an empty or invalid response body.");
    }

    private async Task<HttpResponseMessage> SendRequestAsync(
        HttpMethod method,
        string relativePath,
        HttpContent? content,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(method, relativePath)
        {
            Content = content,
        };

        // AuthenticationHandler attaches the same singleton AuthState token to every
        // typed HttpClient request. Keep this fallback for direct unit-test clients.
        if (request.Headers.Authorization is null && _authState.GetValidAccessToken() is { } token)
            request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue(_authState.TokenType ?? "Bearer", token);

        _logger.LogDebug("API request: {Method} {Path}", method, relativePath);
        var response = await _httpClient.SendAsync(request, cancellationToken);
        _logger.LogDebug("API response: {Method} {Path} {StatusCode}", method, relativePath, (int)response.StatusCode);
        if (method == HttpMethod.Post && string.Equals(relativePath, "deliveries", StringComparison.OrdinalIgnoreCase))
        {
            _logger.LogInformation("Delivery response status: {StatusCode}", (int)response.StatusCode);
        }
        return response;
    }

    private async Task EnsureSuccessAsync(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        if (response.IsSuccessStatusCode)
        {
            return;
        }

        ApiErrorResponseDto? errorResponse = null;
        try
        {
            await using var errorStream = await response.Content.ReadAsStreamAsync(cancellationToken);
            errorResponse = await JsonSerializer.DeserializeAsync<ApiErrorResponseDto>(
                errorStream, _jsonOptions, cancellationToken);
        }
        catch (JsonException)
        {
            // Use the HTTP status fallback below when a non-conforming response is received.
        }

        var error = errorResponse?.Error;
        throw new ApiException(
            response.StatusCode,
            error?.Code ?? "HTTP_ERROR",
            error?.Message ?? $"The API request failed with status {(int)response.StatusCode} ({response.ReasonPhrase}).",
            error?.Details);
    }

    private StringContent CreateJsonContent<TRequest>(TRequest request) =>
        new(JsonSerializer.Serialize(request, _jsonOptions), Encoding.UTF8, "application/json");
}
