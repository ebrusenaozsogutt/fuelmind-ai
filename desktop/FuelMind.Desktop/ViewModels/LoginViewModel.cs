using System.Net;
using System.Net.Http;
using System.Text.Json;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class LoginViewModel : ObservableObject
{
    private readonly AuthService _authService;
    private readonly LoginPreferenceStore _preferenceStore;

    public LoginViewModel(AuthService authService, LoginPreferenceStore preferenceStore)
    {
        _authService = authService;
        _preferenceStore = preferenceStore;
        var preferences = _preferenceStore.Load();
        RememberMe = preferences.RememberMe;
        Username = preferences.RememberMe ? preferences.Username : string.Empty;
    }

    [ObservableProperty]
    private string _username = string.Empty;

    [ObservableProperty]
    private bool _isBusy;

    [ObservableProperty]
    private string? _errorMessage;

    [ObservableProperty]
    private bool _isPasswordVisible;

    [ObservableProperty]
    private bool _rememberMe;

    public event EventHandler? LoginSucceeded;

    [RelayCommand(CanExecute = nameof(CanLogin))]
    private async Task LoginAsync(string? password)
    {
        ErrorMessage = null;
        var normalizedUsername = Username.Trim();
        if (string.IsNullOrWhiteSpace(normalizedUsername))
        {
            ErrorMessage = "Kullanıcı adı gereklidir.";
            return;
        }

        if (string.IsNullOrEmpty(password))
        {
            ErrorMessage = "Şifre gereklidir.";
            return;
        }

        IsBusy = true;
        try
        {
            await _authService.LoginAsync(normalizedUsername, password);
            if (RememberMe) _preferenceStore.Save(normalizedUsername);
            else _preferenceStore.Clear();
            LoginSucceeded?.Invoke(this, EventArgs.Empty);
        }
        catch (ApiException exception) when (exception.StatusCode == HttpStatusCode.Unauthorized)
        {
            ErrorMessage = "Kullanıcı adı veya şifre hatalı.";
        }
        catch (HttpRequestException)
        {
            ErrorMessage = "FuelMind API'ye bağlanılamadı. Backend servisinin çalıştığını kontrol edin.";
        }
        catch (TaskCanceledException)
        {
            ErrorMessage = "Sunucudan zamanında yanıt alınamadı.";
        }
        catch (JsonException)
        {
            ErrorMessage = "Sunucudan alınan yanıt işlenemedi.";
        }
        catch (ApiException exception)
        {
            if (exception.ErrorCode != "VALIDATION_ERROR")
            {
                ErrorMessage = "Giriş yapılırken beklenmeyen bir hata oluştu.";
                return;
            }

            ErrorMessage = exception.ErrorCode == "VALIDATION_ERROR"
                ? exception.Message
                : "Giriş yapılırken bir hata oluştu. Lütfen tekrar deneyin.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private bool CanLogin() => !IsBusy;

    partial void OnIsBusyChanged(bool value) => LoginCommand.NotifyCanExecuteChanged();
    partial void OnRememberMeChanged(bool value)
    {
        if (!value) _preferenceStore.Clear();
    }
}
