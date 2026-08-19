using System.Net.Http.Headers;
using System.Net.Http;
using FuelMind.Desktop.State;

namespace FuelMind.Desktop.Services;

/// <summary>Applies the one shared login session to every REST client request.</summary>
public sealed class AuthenticationHandler(AuthState authState) : DelegatingHandler
{
    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        var token = authState.GetValidAccessToken();
        if (!string.IsNullOrWhiteSpace(token))
        {
            request.Headers.Authorization = new AuthenticationHeaderValue(authState.TokenType ?? "Bearer", token);
        }
        return base.SendAsync(request, cancellationToken);
    }
}
