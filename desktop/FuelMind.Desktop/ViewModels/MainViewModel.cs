using CommunityToolkit.Mvvm.ComponentModel;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class MainViewModel : ObservableObject
{
    private readonly LoginViewModel _loginViewModel;
    private readonly State.AuthState _authState;
    private readonly LiveMonitoringViewModel _liveMonitoringViewModel;
    private readonly TanksViewModel _tanksViewModel;
    private readonly PumpsViewModel _pumpsViewModel;
    private readonly DashboardViewModel _dashboardViewModel;
    private readonly SimulatorViewModel _simulatorViewModel;
    private readonly TankDetailViewModel _tankDetailViewModel;
    private readonly PumpDetailViewModel _pumpDetailViewModel;
    private readonly AlarmsViewModel _alarmsViewModel;
    private readonly ModelManagementViewModel _modelManagementViewModel;
    private readonly Services.DetailNavigationService _detailNavigation;

    private readonly Services.AuthService _authService;

    public MainViewModel(LoginViewModel loginViewModel, State.AuthState authState, Services.AuthService authService, LiveMonitoringViewModel liveMonitoringViewModel, TanksViewModel tanksViewModel, PumpsViewModel pumpsViewModel, DashboardViewModel dashboardViewModel, SimulatorViewModel simulatorViewModel, TankDetailViewModel tankDetailViewModel, PumpDetailViewModel pumpDetailViewModel, AlarmsViewModel alarmsViewModel, ModelManagementViewModel modelManagementViewModel, Services.DetailNavigationService detailNavigation)
    {
        _loginViewModel = loginViewModel;
        _authState = authState;
        _authService = authService;
        _liveMonitoringViewModel = liveMonitoringViewModel;
        _tanksViewModel = tanksViewModel;
        _pumpsViewModel = pumpsViewModel;
        _dashboardViewModel = dashboardViewModel;
        _simulatorViewModel = simulatorViewModel;
        _alarmsViewModel = alarmsViewModel;
        _modelManagementViewModel = modelManagementViewModel;
        _tankDetailViewModel=tankDetailViewModel; _pumpDetailViewModel=pumpDetailViewModel; _detailNavigation=detailNavigation;
        _loginViewModel.LoginSucceeded += OnLoginSucceeded;
        CurrentViewModel = _loginViewModel;

        if (authState.IsAuthenticated && authState.CurrentUser is not null)
        {
            ShowShell(authState.CurrentUser);
        }
    }

    [ObservableProperty]
    private string _applicationTitle = "FuelMind AI";

    [ObservableProperty]
    private object? _currentViewModel;

    private void OnLoginSucceeded(object? sender, EventArgs e)
    {
        if (_authState.CurrentUser is not null)
        {
            ShowShell(_authState.CurrentUser);
        }
    }

    private void ShowShell(Dtos.Auth.CurrentUserResponseDto currentUser)
    {
        var shell = new AuthenticatedShellViewModel(currentUser, _authService, _liveMonitoringViewModel, _tanksViewModel, _pumpsViewModel, _dashboardViewModel, _simulatorViewModel, _tankDetailViewModel, _pumpDetailViewModel, _alarmsViewModel, _modelManagementViewModel, _detailNavigation);
        shell.LogoutRequested += (_, _) => CurrentViewModel = _loginViewModel;
        CurrentViewModel = shell;
    }
}
