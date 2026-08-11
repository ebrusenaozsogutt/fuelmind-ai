using CommunityToolkit.Mvvm.ComponentModel;
using FuelMind.Desktop.Dtos.Auth;

namespace FuelMind.Desktop.State;

public sealed partial class AuthState : ObservableObject
{
    [ObservableProperty]
    private string? _accessToken;

    [ObservableProperty]
    private string? _tokenType;

    [ObservableProperty]
    private DateTimeOffset? _expiresAt;

    [ObservableProperty]
    private CurrentUserResponseDto? _currentUser;

    public bool IsAuthenticated => GetValidAccessToken() is not null && CurrentUser is not null;

    public void SetAuthentication(TokenResponseDto token)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(token.AccessToken);

        AccessToken = token.AccessToken;
        TokenType = token.TokenType;
        ExpiresAt = DateTimeOffset.UtcNow.AddSeconds(token.ExpiresIn);
        OnPropertyChanged(nameof(IsAuthenticated));
    }

    public void SetCurrentUser(CurrentUserResponseDto currentUser)
    {
        CurrentUser = currentUser ?? throw new ArgumentNullException(nameof(currentUser));
        OnPropertyChanged(nameof(IsAuthenticated));
    }

    public string? GetValidAccessToken()
    {
        if (string.IsNullOrWhiteSpace(AccessToken) || ExpiresAt is null || ExpiresAt <= DateTimeOffset.UtcNow)
        {
            return null;
        }

        return AccessToken;
    }

    public void Clear()
    {
        AccessToken = null;
        TokenType = null;
        ExpiresAt = null;
        CurrentUser = null;
        OnPropertyChanged(nameof(IsAuthenticated));
    }
}
