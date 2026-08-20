using System.Collections.Specialized;
using System.ComponentModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Dashboard;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class DashboardViewModel : ObservableObject
{
    private readonly LiveDataStore _liveDataStore;
    private readonly ApiClient _apiClient;
    private readonly DetailNavigationService _navigation;
    private readonly LiveWebSocketService? _liveWebSocketService;

    public DashboardViewModel(LiveDataStore liveDataStore, ApiClient apiClient, DetailNavigationService navigation)
        : this(liveDataStore, apiClient, navigation, null)
    {
    }

    public DashboardViewModel(LiveDataStore liveDataStore, ApiClient apiClient, DetailNavigationService navigation, LiveWebSocketService? liveWebSocketService)
    {
        _liveDataStore = liveDataStore;
        _apiClient = apiClient;
        _navigation = navigation;
        _liveWebSocketService = liveWebSocketService;
        _liveDataStore.PropertyChanged += OnLiveDataStorePropertyChanged;
        _liveDataStore.Tanks.CollectionChanged += OnLiveCollectionChanged;
        _liveDataStore.Pumps.CollectionChanged += OnLiveCollectionChanged;
        RefreshLiveMetrics();
    }

    [ObservableProperty] private string _totalStock = "Veri yok";
    [ObservableProperty] private string _activePumpCount = "Veri yok";
    [ObservableProperty] private string _lowestStockTank = "Veri yok";
    [ObservableProperty] private string _operationSummary = "Canli baglanti yok";
    [ObservableProperty] private string _dailySales = "Veri yok";
    [ObservableProperty] private string _activeAlarms = "Veri yok";
    [ObservableProperty] private string _criticalAlarms = "Veri yok";
    [ObservableProperty] private string _riskEquipment = "Veri yok";
    [ObservableProperty] private string _stationHealthScore = "Veri yok";
    [ObservableProperty] private string _aiRiskScore = "Veri yok";
    [ObservableProperty] private string _aiRiskLevel = "Veri yok";
    [ObservableProperty] private string _highRiskEquipment = "Veri yok";
    [ObservableProperty] private string _mostRiskyEquipment = "Veri yok";
    [ObservableProperty] private string _lastAiAssessment = "Veri yok";

    public IReadOnlyList<TankLiveDataDto> Tanks => _liveDataStore.Tanks;
    public IReadOnlyList<PumpLiveDataDto> Pumps => _liveDataStore.Pumps;
    public bool HasTanks => _liveDataStore.Tanks.Count > 0;
    public bool HasPumps => _liveDataStore.Pumps.Count > 0;
    public string ConnectionDisplay => _liveDataStore.ConnectionState.ToString();
    public string ConnectionStatusLabel => _liveDataStore.ConnectionState == LiveConnectionState.Connected
        ? "CANLI"
        : "BAĞLANTI";
    public string AverageTankFill => _liveDataStore.Tanks.Count == 0
        ? "Veri yok"
        : $"%{_liveDataStore.Tanks.Where(t => t.CapacityLiters > 0).Select(t => t.MeasuredLevelLiters / t.CapacityLiters * 100m).DefaultIfEmpty().Average():N0}";

    public async Task RefreshSummaryAsync()
    {
        var stationId = _liveDataStore.SelectedStationId;
        if (stationId <= 0)
        {
            DailySales = ActiveAlarms = CriticalAlarms = RiskEquipment = StationHealthScore =
                AiRiskScore = AiRiskLevel = HighRiskEquipment = MostRiskyEquipment = LastAiAssessment = "Veri yok";
            return;
        }

        try
        {
            await EnsureLiveConnectionAsync(stationId);
            var summary = await _apiClient.GetAsync<DashboardSummaryDto>($"stations/{stationId}/dashboard-summary");
            DailySales = $"{summary.DailySalesLiters:N1} L";
            ActiveAlarms = summary.ActiveAlarms.ToString();
            CriticalAlarms = summary.CriticalAlarms.ToString();
            RiskEquipment = summary.RiskyEquipment.ToString();
            StationHealthScore = summary.StationHealthScore is int health ? $"{health}/100" : "Veri yok";
            AiRiskScore = summary.StationRiskScore is decimal risk ? $"{risk:N0}/100" : "Veri yok";
            AiRiskLevel = RiskLevelText(summary.StationRiskLevel);
            HighRiskEquipment = summary.HighOrCriticalRiskCount.ToString();
            MostRiskyEquipment = summary.MostRiskyEquipment ?? "Veri yok";
            LastAiAssessment = summary.LastAiAssessmentAt?.ToLocalTime().ToString("dd.MM.yyyy HH:mm") ?? "Veri yok";
        }
        catch (Exception)
        {
            DailySales = ActiveAlarms = CriticalAlarms = RiskEquipment = StationHealthScore =
                AiRiskScore = AiRiskLevel = HighRiskEquipment = MostRiskyEquipment = LastAiAssessment = "Veri yok";
        }
    }

    private async Task EnsureLiveConnectionAsync(int stationId)
    {
        if (_liveWebSocketService is null ||
            (_liveWebSocketService.ConnectionState == LiveConnectionState.Connected &&
             _liveWebSocketService.ConnectedStationId == stationId))
        {
            return;
        }

        if (_liveWebSocketService.ConnectionState is not LiveConnectionState.Disconnected)
        {
            await _liveWebSocketService.DisconnectAsync();
        }

        await _liveWebSocketService.ConnectAsync(stationId);
    }

    private void OnLiveDataStorePropertyChanged(object? sender, PropertyChangedEventArgs eventArgs)
    {
        if (eventArgs.PropertyName is nameof(LiveDataStore.ConnectionState) or nameof(LiveDataStore.ConnectedStationId) or nameof(LiveDataStore.SelectedStationId) or nameof(LiveDataStore.LastSequence) or nameof(LiveDataStore.LastMessageAt))
        {
            RefreshLiveMetrics();
            if (eventArgs.PropertyName is nameof(LiveDataStore.ConnectedStationId) or nameof(LiveDataStore.SelectedStationId)) _ = RefreshSummaryAsync();
        }
    }

    private void OnLiveCollectionChanged(object? sender, NotifyCollectionChangedEventArgs eventArgs) => RefreshLiveMetrics();

    private void RefreshLiveMetrics()
    {
        var tanks = _liveDataStore.Tanks;
        var pumps = _liveDataStore.Pumps;
        TotalStock = tanks.Count == 0 ? "Veri yok" : $"{tanks.Sum(tank => tank.MeasuredLevelLiters):N0} L";
        ActivePumpCount = pumps.Count == 0
            ? "Veri yok"
            : $"{pumps.Count(pump => string.Equals(pump.Status, "ACTIVE", StringComparison.OrdinalIgnoreCase))} / {pumps.Count}";
        var lowestTank = tanks.Where(tank => tank.CapacityLiters > 0).OrderBy(tank => tank.MeasuredLevelLiters / tank.CapacityLiters).FirstOrDefault();
        LowestStockTank = lowestTank is null ? "Veri yok" : $"{lowestTank.Code ?? $"Tank {lowestTank.TankId}"} - %{lowestTank.MeasuredLevelLiters / lowestTank.CapacityLiters * 100m:N0}";
        OperationSummary = _liveDataStore.ConnectedStationId is not int stationId
            ? "Canli baglanti yok"
            : $"Istasyon {stationId} bagli - {tanks.Count} tank - {pumps.Count} pompa - Sira {_liveDataStore.LastSequence?.ToString() ?? "Veri yok"} - Son paket {_liveDataStore.LastMessageAt?.ToLocalTime().ToString("HH:mm:ss") ?? "Veri yok"}";
        OnPropertyChanged(nameof(Tanks));
        OnPropertyChanged(nameof(Pumps));
        OnPropertyChanged(nameof(HasTanks));
        OnPropertyChanged(nameof(HasPumps));
        OnPropertyChanged(nameof(AverageTankFill));
        OnPropertyChanged(nameof(ConnectionDisplay));
        OnPropertyChanged(nameof(ConnectionStatusLabel));
    }

    private static string RiskLevelText(string? value) => value?.ToUpperInvariant() switch
    {
        "NORMAL" => "Normal", "WATCH" => "İzle", "MEDIUM" => "Orta",
        "HIGH" => "Yüksek", "CRITICAL" => "Kritik", _ => "Veri yok",
    };

    [RelayCommand] private void OpenActiveAlarms() => _navigation.ShowAlarms(new AlarmNavigationFilter());
    [RelayCommand] private void OpenCriticalAlarms() => _navigation.ShowAlarms(new AlarmNavigationFilter("CRITICAL"));
    [RelayCommand] private void OpenPumps() => _navigation.ShowPumps();
    [RelayCommand] private void OpenTanks() => _navigation.ShowTanks();
    [RelayCommand] private void OpenRiskyEquipment() => _navigation.ShowLiveRisk();
}
