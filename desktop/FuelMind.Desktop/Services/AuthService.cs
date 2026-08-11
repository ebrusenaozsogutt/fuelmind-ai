using FuelMind.Desktop.Dtos.Auth;
using FuelMind.Desktop.State;
using Microsoft.Extensions.Logging;

namespace FuelMind.Desktop.Services;

public sealed class AuthService
{
    private readonly ApiClient _apiClient;
    private readonly AuthState _authState;
    private readonly ILogger<AuthService> _logger;

    public AuthService(ApiClient apiClient, AuthState authState, ILogger<AuthService> logger)
    {
        _apiClient = apiClient;
        _authState = authState;
        _logger = logger;
    }

    public async Task<CurrentUserResponseDto> LoginAsync(
        string username,
        string password,
        CancellationToken cancellationToken = default)
    {
        var stage = "LOGIN_REQUEST";
        _authState.Clear();
        try
        {
            _logger.LogDebug("Authentication flow stage: {Stage}", stage);
            var token = await _apiClient.PostAsync<LoginRequestDto, TokenResponseDto>(
                "auth/login",
                new LoginRequestDto { Username = username, Password = password },
                cancellationToken);
            stage = "LOGIN_RESPONSE_RECEIVED";
            _logger.LogDebug("Authentication flow stage: {Stage}", stage);
            _authState.SetAuthentication(token);
            stage = "TOKEN_STORED";
            _logger.LogDebug("Authentication flow stage: {Stage}", stage);
            _logger.LogDebug("Authentication flow stage: {Stage}", "AUTH_ME_REQUEST");
            return await LoadCurrentUserAsync(cancellationToken);
        }
        catch (Exception exception)
        {
            _logger.LogWarning(exception, "Authentication flow failed at stage {Stage}", stage);
            _authState.Clear();
            throw;
        }
    }

    public async Task<CurrentUserResponseDto> LoadCurrentUserAsync(
        CancellationToken cancellationToken = default)
    {
        try
        {
            var currentUser = await _apiClient.GetAsync<CurrentUserResponseDto>("auth/me", cancellationToken);
            _authState.SetCurrentUser(currentUser);
            _logger.LogDebug("Authentication flow stage: {Stage}", "AUTH_ME_SUCCESS");
            return currentUser;
        }
        catch (Exception exception)
        {
            _logger.LogWarning(exception, "Authentication flow failed at stage AUTH_ME_REQUEST");
            _authState.Clear();
            throw;
        }
    }

    public void Logout() => _authState.Clear();
}
