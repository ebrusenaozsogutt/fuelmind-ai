using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Auth;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class AuthenticatedShellViewModel : ObservableObject
{
    private readonly AuthService _authService;
    private readonly LiveMonitoringViewModel _liveMonitoringViewModel;
    private readonly TanksViewModel _tanksViewModel;
    private readonly PumpsViewModel _pumpsViewModel;
    private readonly DashboardViewModel _dashboardViewModel;
    private readonly SimulatorViewModel _simulatorViewModel;
    private readonly TankDetailViewModel _tankDetail; private readonly PumpDetailViewModel _pumpDetail;
    private readonly AlarmsViewModel _alarms;
    private readonly ModelManagementViewModel _modelManagement;

    public AuthenticatedShellViewModel(CurrentUserResponseDto currentUser, AuthService authService, LiveMonitoringViewModel liveMonitoringViewModel, TanksViewModel tanksViewModel, PumpsViewModel pumpsViewModel, DashboardViewModel dashboardViewModel, SimulatorViewModel simulatorViewModel, TankDetailViewModel tankDetail, PumpDetailViewModel pumpDetail, AlarmsViewModel alarms, ModelManagementViewModel modelManagement, DetailNavigationService nav)
    {
        CurrentUser = currentUser;
        _authService = authService;
        _liveMonitoringViewModel = liveMonitoringViewModel;
        _tanksViewModel = tanksViewModel;
        _pumpsViewModel = pumpsViewModel;
        _dashboardViewModel = dashboardViewModel;
        _simulatorViewModel = simulatorViewModel;
        _alarms = alarms;
        _modelManagement = modelManagement;
        _tankDetail=tankDetail;_pumpDetail=pumpDetail; nav.TankRequested+=id=>{_tankDetail.Select(id);ShowPage(_tankDetail,"Tank Detail");};nav.PumpRequested+=id=>{_pumpDetail.Select(id);ShowPage(_pumpDetail,"Pump Detail");};nav.BackToTanksRequested+=()=>ShowPage(_tanksViewModel,"Tanklar");nav.BackToPumpsRequested+=()=>ShowPage(_pumpsViewModel,"Pompalar");
        CurrentPage = _dashboardViewModel;
        _alarms.AlarmsChanged += (_, _) => _ = _dashboardViewModel.RefreshSummaryAsync();
        _ = _dashboardViewModel.RefreshSummaryAsync();
    }

    public CurrentUserResponseDto CurrentUser { get; }
    public string CurrentUserName => CurrentUser.FullName;
    public string CurrentUserRole => CurrentUser.Role;

    [ObservableProperty]
    private object? _currentPage;

    [ObservableProperty]
    private string _currentPageTitle = "Dashboard";

    public event EventHandler? LogoutRequested;

    [RelayCommand] private void ShowDashboard() { ShowPage(_dashboardViewModel, "Dashboard"); _ = _dashboardViewModel.RefreshSummaryAsync(); }
    [RelayCommand]
    private void ShowLiveMonitoring()
    {
        ShowPage(_liveMonitoringViewModel, "Canlı İzleme");
        _ = _liveMonitoringViewModel.ConnectForSelectedStationAsync();
    }
    [RelayCommand] private void ShowTanks() => ShowPage(_tanksViewModel, "Tanklar");
    [RelayCommand] private void ShowPumps() => ShowPage(_pumpsViewModel, "Pompalar");
    [RelayCommand] private void ShowAlarms() { ShowPage(_alarms, "Alarm Merkezi"); _ = _alarms.LoadAsync(); }
    [RelayCommand] private void ShowForecasts() => ShowPlaceholder("Tahminler");
    [RelayCommand] private void ShowOrders() => ShowPlaceholder("Sipariş Önerileri");
    [RelayCommand] private void ShowSimulator() { ShowPage(_simulatorViewModel, "Simülatör"); _ = _simulatorViewModel.RefreshActiveRunAsync(); }
    [RelayCommand] private void ShowReports() => ShowPlaceholder("Raporlar");
    [RelayCommand] private void ShowModelManagement() { ShowPage(_modelManagement, "AI Model Yönetimi"); _ = _modelManagement.LoadModelsAsync(); }
    [RelayCommand] private void ShowSettings() => ShowPlaceholder("Ayarlar");
    [RelayCommand] private void Logout()
    {
        _authService.Logout();
        LogoutRequested?.Invoke(this, EventArgs.Empty);
    }

    private void ShowPlaceholder(string title) => ShowPage(new PlaceholderPageViewModel(title), title);
    private void ShowPage(object page, string title) { CurrentPage = page; CurrentPageTitle = title; }
}
