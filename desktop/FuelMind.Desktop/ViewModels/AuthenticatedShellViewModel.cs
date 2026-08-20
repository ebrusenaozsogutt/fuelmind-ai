using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Auth;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class AuthenticatedShellViewModel : ObservableObject
{
    private readonly AuthService _authService;
    private readonly LiveMonitoringViewModel _liveMonitoringViewModel;
    private readonly FieldTopologyViewModel _fieldTopologyViewModel;
    private readonly TanksViewModel _tanksViewModel;
    private readonly PumpsViewModel _pumpsViewModel;
    private readonly DashboardViewModel _dashboardViewModel;
    private readonly SimulatorViewModel _simulatorViewModel;
    private readonly TankDetailViewModel _tankDetail; private readonly PumpDetailViewModel _pumpDetail;
    private readonly AlarmsViewModel _alarms;
    private readonly ModelManagementViewModel _modelManagement;
    private readonly CustomersViewModel _customers; private readonly FuelCardsViewModel _fuelCards; private readonly FuelPricesViewModel _fuelPrices; private readonly SalesHistoryViewModel _salesHistory;
    private readonly EndOfDayAlarmReportViewModel _endOfDayAlarmReport;
    private readonly ReportsViewModel _reports;
    private readonly FaultsViewModel _faults;
    private readonly AttendantsViewModel _attendants;

    public AuthenticatedShellViewModel(CurrentUserResponseDto currentUser, AuthService authService, LiveMonitoringViewModel liveMonitoringViewModel, FieldTopologyViewModel fieldTopologyViewModel, TanksViewModel tanksViewModel, PumpsViewModel pumpsViewModel, DashboardViewModel dashboardViewModel, SimulatorViewModel simulatorViewModel, TankDetailViewModel tankDetail, PumpDetailViewModel pumpDetail, AlarmsViewModel alarms, ModelManagementViewModel modelManagement, CustomersViewModel customers, FuelCardsViewModel fuelCards, FuelPricesViewModel fuelPrices, SalesHistoryViewModel salesHistory, EndOfDayAlarmReportViewModel endOfDayAlarmReport, ReportsViewModel reports, FaultsViewModel faults, AttendantsViewModel attendants, DetailNavigationService nav)
    {
        CurrentUser = currentUser;
        _authService = authService;
        _liveMonitoringViewModel = liveMonitoringViewModel;
        _fieldTopologyViewModel = fieldTopologyViewModel;
        _tanksViewModel = tanksViewModel;
        _pumpsViewModel = pumpsViewModel;
        _dashboardViewModel = dashboardViewModel;
        _simulatorViewModel = simulatorViewModel;
        _alarms = alarms;
        _modelManagement = modelManagement;
        _customers=customers;_fuelCards=fuelCards;_fuelPrices=fuelPrices;_salesHistory=salesHistory;_endOfDayAlarmReport=endOfDayAlarmReport;_reports=reports;_faults=faults;_attendants=attendants;
        _tankDetail=tankDetail;_pumpDetail=pumpDetail; nav.TankRequested+=id=>{_tankDetail.Select(id);ShowPage(_tankDetail,"Tank Detail");};nav.PumpRequested+=id=>{_pumpDetail.Select(id);ShowPage(_pumpDetail,"Pump Detail");};nav.BackToTanksRequested+=()=>ShowPage(_tanksViewModel,"Tanklar");nav.BackToPumpsRequested+=()=>ShowPage(_pumpsViewModel,"Pompalar");
        nav.AlarmsRequested += filter => { _alarms.ApplyNavigationFilter(filter); ShowPage(_alarms, "Alarm Merkezi"); _ = _alarms.LoadAsync(); };
        nav.FaultRequested += id => { ShowPage(_faults, "Arıza Yönetimi"); _ = _faults.OpenFaultAsync(id); };
        nav.PumpsRequested += () => ShowPage(_pumpsViewModel, "Pompalar");
        nav.TanksRequested += () => ShowPage(_tanksViewModel, "Tanklar");
        nav.LiveRiskRequested += () => { ShowPage(_liveMonitoringViewModel, "Canlı İzleme"); _ = _liveMonitoringViewModel.ConnectForSelectedStationAsync(); };
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
    [RelayCommand] private void ShowFieldTopology() { ShowPage(_fieldTopologyViewModel, "Saha Topolojisi"); _ = _fieldTopologyViewModel.LoadAsync(); }
    [RelayCommand] private void ShowTanks() => ShowPage(_tanksViewModel, "Tanklar");
    [RelayCommand] private void ShowPumps() => ShowPage(_pumpsViewModel, "Pompalar");
    [RelayCommand] private void ShowAlarms() { ShowPage(_alarms, "Alarm Merkezi"); _ = _alarms.LoadAsync(); }
    [RelayCommand] private void ShowFaults() { ShowPage(_faults, "Arıza Yönetimi"); _ = _faults.LoadAsync(); }
    [RelayCommand] private void ShowAttendants() { ShowPage(_attendants, "Pompacı & Vardiya"); _ = _attendants.LoadAsync(); }
    [RelayCommand] private void ShowCustomers() { _salesHistory.StopAutoRefresh(); ShowPage(_customers, "Müşteriler"); _ = _customers.LoadAsync(); }
    [RelayCommand] private void ShowFuelCards() { _salesHistory.StopAutoRefresh(); ShowPage(_fuelCards, "Kartlar"); _ = _fuelCards.LoadAsync(); }
    [RelayCommand] private void ShowFuelPrices() { _salesHistory.StopAutoRefresh(); ShowPage(_fuelPrices, "Fiyat Yönetimi"); _ = _fuelPrices.LoadAsync(); }
    [RelayCommand] private void ShowSales() { ShowPage(_salesHistory, "Satışlar"); _ = _salesHistory.LoadAsync(); _salesHistory.StartAutoRefresh(); }
    [RelayCommand] private void ShowForecasts() => ShowPlaceholder("Tahminler");
    [RelayCommand] private void ShowOrders() => ShowPlaceholder("Sipariş Önerileri");
    [RelayCommand] private void ShowSimulator() { ShowPage(_simulatorViewModel, "Simülatör"); _ = _simulatorViewModel.RefreshActiveRunAsync(); }
    [RelayCommand] private void ShowReports() { ShowPage(_reports, "Raporlar"); _ = _reports.LoadAsync(); }
    [RelayCommand] private void ShowModelManagement() { ShowPage(_modelManagement, "AI Model Yönetimi"); _ = _modelManagement.LoadModelsAsync(); }
    [RelayCommand] private void ShowSettings() => ShowPlaceholder("Ayarlar");
    [RelayCommand] private void Logout()
    {
        _salesHistory.StopAutoRefresh();
        _authService.Logout();
        LogoutRequested?.Invoke(this, EventArgs.Empty);
    }

    private void ShowPlaceholder(string title) => ShowPage(new PlaceholderPageViewModel(title), title);
    private void ShowPage(object page, string title)
    {
        if (!ReferenceEquals(page, _salesHistory)) _salesHistory.StopAutoRefresh();
        CurrentPage = page;
        CurrentPageTitle = title;
    }
}
