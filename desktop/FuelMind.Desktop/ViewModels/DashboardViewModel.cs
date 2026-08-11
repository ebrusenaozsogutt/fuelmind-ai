using System.Collections.Specialized;
using System.ComponentModel;
using CommunityToolkit.Mvvm.ComponentModel;
using FuelMind.Desktop.Dtos.Dashboard;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class DashboardViewModel : ObservableObject
{
    private readonly LiveDataStore _liveDataStore;
    private readonly ApiClient _apiClient;

    public DashboardViewModel(LiveDataStore liveDataStore, ApiClient apiClient)
    {
        _liveDataStore = liveDataStore;
        _apiClient = apiClient;
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

    public async Task RefreshSummaryAsync()
    {
        if (_liveDataStore.ConnectedStationId is not int stationId)
        {
            DailySales = ActiveAlarms = CriticalAlarms = RiskEquipment = StationHealthScore = "Veri yok";
            return;
        }

        try
        {
            var summary = await _apiClient.GetAsync<DashboardSummaryDto>($"stations/{stationId}/dashboard-summary");
            DailySales = $"{summary.DailySalesLiters:N1} L";
            ActiveAlarms = summary.ActiveAlarms.ToString();
            CriticalAlarms = summary.CriticalAlarms.ToString();
            RiskEquipment = summary.RiskyEquipment.ToString();
            StationHealthScore = $"{summary.StationHealthScore}/100";
        }
        catch (Exception)
        {
            DailySales = ActiveAlarms = CriticalAlarms = RiskEquipment = StationHealthScore = "Veri yok";
        }
    }

    private void OnLiveDataStorePropertyChanged(object? sender, PropertyChangedEventArgs eventArgs)
    {
        if (eventArgs.PropertyName is nameof(LiveDataStore.ConnectionState) or nameof(LiveDataStore.ConnectedStationId) or nameof(LiveDataStore.LastSequence) or nameof(LiveDataStore.LastMessageAt))
        {
            RefreshLiveMetrics();
            if (eventArgs.PropertyName == nameof(LiveDataStore.ConnectedStationId)) _ = RefreshSummaryAsync();
        }
    }

    private void OnLiveCollectionChanged(object? sender, NotifyCollectionChangedEventArgs eventArgs) => RefreshLiveMetrics();

    private void RefreshLiveMetrics()
    {
        var tanks = _liveDataStore.Tanks;
        var pumps = _liveDataStore.Pumps;
        TotalStock = tanks.Count == 0 ? "Veri yok" : $"{tanks.Sum(tank => tank.MeasuredLevelLiters):N0} L";
        ActivePumpCount = pumps.Count == 0 ? "Veri yok" : pumps.Count(pump => string.Equals(pump.Status, "ACTIVE", StringComparison.OrdinalIgnoreCase)).ToString();
        var lowestTank = tanks.Where(tank => tank.CapacityLiters > 0).OrderBy(tank => tank.MeasuredLevelLiters / tank.CapacityLiters).FirstOrDefault();
        LowestStockTank = lowestTank is null ? "Veri yok" : $"{lowestTank.Code ?? $"Tank {lowestTank.TankId}"} - %{lowestTank.MeasuredLevelLiters / lowestTank.CapacityLiters * 100m:N0}";
        OperationSummary = _liveDataStore.ConnectedStationId is not int stationId
            ? "Canli baglanti yok"
            : $"Istasyon {stationId} bagli - {tanks.Count} tank - {pumps.Count} pompa - Sira {_liveDataStore.LastSequence?.ToString() ?? "Veri yok"} - Son paket {_liveDataStore.LastMessageAt?.ToLocalTime().ToString("HH:mm:ss") ?? "Veri yok"}";
    }
}
