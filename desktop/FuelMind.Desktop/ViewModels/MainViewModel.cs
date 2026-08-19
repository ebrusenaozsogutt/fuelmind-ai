using CommunityToolkit.Mvvm.ComponentModel;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class MainViewModel : ObservableObject
{
    private readonly LoginViewModel _loginViewModel;
    private readonly State.AuthState _authState;
    private readonly LiveMonitoringViewModel _liveMonitoringViewModel;
    private readonly FieldTopologyViewModel _fieldTopologyViewModel;
    private readonly TanksViewModel _tanksViewModel;
    private readonly PumpsViewModel _pumpsViewModel;
    private readonly DashboardViewModel _dashboardViewModel;
    private readonly SimulatorViewModel _simulatorViewModel;
    private readonly TankDetailViewModel _tankDetailViewModel;
    private readonly PumpDetailViewModel _pumpDetailViewModel;
    private readonly AlarmsViewModel _alarmsViewModel;
    private readonly ModelManagementViewModel _modelManagementViewModel;
    private readonly CustomersViewModel _customersViewModel;
    private readonly FuelCardsViewModel _fuelCardsViewModel;
    private readonly FuelPricesViewModel _fuelPricesViewModel;
    private readonly SalesHistoryViewModel _salesHistoryViewModel;
    private readonly EndOfDayAlarmReportViewModel _endOfDayAlarmReportViewModel;
    private readonly ReportsViewModel _reportsViewModel;
    private readonly FaultsViewModel _faultsViewModel;
    private readonly AttendantsViewModel _attendantsViewModel;
    private readonly Services.DetailNavigationService _detailNavigation;

    private readonly Services.AuthService _authService;

    public MainViewModel(LoginViewModel loginViewModel, State.AuthState authState, Services.AuthService authService, LiveMonitoringViewModel liveMonitoringViewModel, FieldTopologyViewModel fieldTopologyViewModel, TanksViewModel tanksViewModel, PumpsViewModel pumpsViewModel, DashboardViewModel dashboardViewModel, SimulatorViewModel simulatorViewModel, TankDetailViewModel tankDetailViewModel, PumpDetailViewModel pumpDetailViewModel, AlarmsViewModel alarmsViewModel, ModelManagementViewModel modelManagementViewModel, CustomersViewModel customersViewModel, FuelCardsViewModel fuelCardsViewModel, FuelPricesViewModel fuelPricesViewModel, SalesHistoryViewModel salesHistoryViewModel, EndOfDayAlarmReportViewModel endOfDayAlarmReportViewModel, ReportsViewModel reportsViewModel, FaultsViewModel faultsViewModel, AttendantsViewModel attendantsViewModel, Services.DetailNavigationService detailNavigation)
    {
        _loginViewModel = loginViewModel;
        _authState = authState;
        _authService = authService;
        _liveMonitoringViewModel = liveMonitoringViewModel;
        _fieldTopologyViewModel = fieldTopologyViewModel;
        _tanksViewModel = tanksViewModel;
        _pumpsViewModel = pumpsViewModel;
        _dashboardViewModel = dashboardViewModel;
        _simulatorViewModel = simulatorViewModel;
        _alarmsViewModel = alarmsViewModel;
        _modelManagementViewModel = modelManagementViewModel;
        _customersViewModel = customersViewModel; _fuelCardsViewModel = fuelCardsViewModel; _fuelPricesViewModel = fuelPricesViewModel; _salesHistoryViewModel = salesHistoryViewModel; _endOfDayAlarmReportViewModel = endOfDayAlarmReportViewModel; _reportsViewModel = reportsViewModel; _faultsViewModel = faultsViewModel; _attendantsViewModel = attendantsViewModel;
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
        var shell = new AuthenticatedShellViewModel(currentUser, _authService, _liveMonitoringViewModel, _fieldTopologyViewModel, _tanksViewModel, _pumpsViewModel, _dashboardViewModel, _simulatorViewModel, _tankDetailViewModel, _pumpDetailViewModel, _alarmsViewModel, _modelManagementViewModel, _customersViewModel, _fuelCardsViewModel, _fuelPricesViewModel, _salesHistoryViewModel, _endOfDayAlarmReportViewModel, _reportsViewModel, _faultsViewModel, _attendantsViewModel, _detailNavigation);
        shell.LogoutRequested += (_, _) => CurrentViewModel = _loginViewModel;
        CurrentViewModel = shell;
    }
}
