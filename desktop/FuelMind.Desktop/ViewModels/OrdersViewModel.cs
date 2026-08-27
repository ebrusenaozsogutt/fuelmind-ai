using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Orders;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Dtos.Tanks;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class OrdersViewModel : ObservableObject
{
    private readonly IOrderRecommendationService _orders; private readonly IStationService _stations; private readonly ApiClient _api; private readonly AuthState _auth;
    public OrdersViewModel(IOrderRecommendationService orders, IStationService stations, ApiClient api, AuthState auth) { _orders = orders; _stations = stations; _api = api; _auth = auth; RuntimeDiagnostics.Trace("OrdersViewModel constructor"); }
    public ObservableCollection<TankDto> Tanks { get; } = []; public ObservableCollection<StationDto> Stations { get; } = [];
    [ObservableProperty] private TankDto? _selectedTank; [ObservableProperty] private OrderRecommendationDto? _recommendation; [ObservableProperty] private bool _isLoading; [ObservableProperty] private string? _errorMessage;
    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage); public bool NoOrderRequired => Recommendation?.RecommendedQuantity == 0; public bool HasOrder => Recommendation is { RecommendedQuantity: > 0 }; public bool CanGenerate => string.Equals(_auth.CurrentUser?.Role, "ADMIN", StringComparison.OrdinalIgnoreCase); public string PriorityDisplay => Recommendation?.Priority switch { "CRITICAL" => "Kritik", "HIGH" => "Yüksek", "MEDIUM" => "Orta", _ => "Düşük" }; public decimal DisplayedCurrentStock => Recommendation?.CurrentStockLiters ?? SelectedTank?.CurrentLevelLiters ?? 0m; public decimal DisplayedMinimumSafeStock => Recommendation?.MinimumSafeStockLiters ?? SelectedTank?.MinimumSafeLevel ?? 0m;
    public async Task LoadAsync(CancellationToken ct = default)
    {
        if (IsLoading) { RuntimeDiagnostics.Trace("OrdersViewModel LoadAsync skipped: already loading"); return; }
        IsLoading = true; ErrorMessage = null;
        RuntimeDiagnostics.Trace("OrdersViewModel LoadAsync START");
        try
        {
            if (Stations.Count == 0) foreach (var s in await _stations.GetActiveStationsAsync(ct)) Stations.Add(s);
            if (Tanks.Count == 0) foreach (var s in Stations) foreach (var t in await _api.GetAsync<IReadOnlyList<TankDto>>($"stations/{s.Id}/tanks?is_active=true", ct)) Tanks.Add(t);
            SelectedTank ??= Tanks.FirstOrDefault();
            if (SelectedTank is not null) { RuntimeDiagnostics.Trace($"OrdersViewModel GET recommendation tank={SelectedTank.Id}"); Recommendation = await _orders.GetTankRecommendationAsync(SelectedTank.Id, ct); }
            else RuntimeDiagnostics.Trace("OrdersViewModel LoadAsync: no active tank available");
        }
        catch (Exception ex) { RuntimeDiagnostics.Exception("OrdersViewModel LoadAsync", ex); ErrorMessage = "Sipariş önerisi alınamadı."; }
        finally { IsLoading = false; NotifyState(); TraceState("LoadAsync END"); }
    }
    [RelayCommand] private Task RefreshAsync(CancellationToken ct) => LoadAsync(ct);
    [RelayCommand] private async Task GenerateAsync(CancellationToken ct) { if (!CanGenerate || SelectedTank is null) return; IsLoading = true; try { Recommendation = await _orders.GenerateTankRecommendationAsync(SelectedTank.Id, ct); } catch (Exception) { ErrorMessage = "Sipariş önerisi üretilemedi."; } finally { IsLoading = false; NotifyState(); } }
    partial void OnSelectedTankChanged(TankDto? value) { if (value is not null) _ = LoadAsync(); }
    internal void TraceState(string source) => RuntimeDiagnostics.Trace($"OrdersViewModel {source}; IsLoading={IsLoading}; Error={ErrorMessage ?? "<none>"}; Tanks={Tanks.Count}; SelectedTank={SelectedTank?.Id.ToString() ?? "<null>"}; RecommendationLoaded={Recommendation is not null}; Quantity={Recommendation?.RecommendedQuantity.ToString() ?? "<null>"}; HasOrder={HasOrder}; NoOrderRequired={NoOrderRequired}");
    private void NotifyState() { OnPropertyChanged(nameof(HasError)); OnPropertyChanged(nameof(NoOrderRequired)); OnPropertyChanged(nameof(HasOrder)); OnPropertyChanged(nameof(PriorityDisplay)); OnPropertyChanged(nameof(DisplayedCurrentStock)); OnPropertyChanged(nameof(DisplayedMinimumSafeStock)); }
}
