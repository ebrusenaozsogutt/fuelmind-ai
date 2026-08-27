using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Commercial;
using FuelMind.Desktop.Dtos.Pumps;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class SalesHistoryViewModel(
    ICommercialService commercialService,
    IStationService stationService,
    IOperationsService operationsService,
    ApiClient apiClient) : ObservableObject
{
    private readonly List<SaleReadDto> _allSales = [];
    private CancellationTokenSource? _refreshCancellation;

    public ObservableCollection<SaleReadDto> Sales { get; } = [];
    [ObservableProperty] private SaleReadDto? _selectedSale;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;
    [ObservableProperty] private string _selectedSaleType = "Tümü";

    public IReadOnlyList<string> SaleTypes { get; } = ["Tümü", "Ticari", "Legacy"];
    public bool IsEmpty => !IsLoading && Sales.Count == 0 && string.IsNullOrEmpty(ErrorMessage);
    public string EmptyStateMessage => SelectedSaleType == "Legacy"
        ? "Legacy satış kaydı bulunmuyor."
        : SelectedSaleType == "Ticari"
            ? "Ticari satış kaydı bulunmuyor."
            : "Satış kaydı bulunmuyor.";

    [RelayCommand]
    public async Task LoadAsync()
    {
        if (IsLoading) return;
        IsLoading = true;
        ErrorMessage = null;
        RuntimeDiagnostics.Trace("Sales initial load started");
        try
        {
            var selectedId = SelectedSale?.Id;
            var salesTask = commercialService.GetSalesAsync();
            var customersTask = commercialService.GetCustomersAsync();
            var vehiclesTask = commercialService.GetVehiclesAsync();
            var cardsTask = commercialService.GetFuelCardsAsync();
            var fleetsTask = commercialService.GetFleetsAsync();
            var groupsTask = commercialService.GetFleetGroupsAsync();
            var driversTask = commercialService.GetDriversAsync();
            var stationsTask = stationService.GetActiveStationsAsync();
            var fuelTypesTask = stationService.GetFuelTypesAsync();
            var attendantsTask = operationsService.AttendantsAsync();
            var shiftsTask = operationsService.ShiftsAsync();
            await Task.WhenAll(salesTask, customersTask, vehiclesTask, cardsTask, fleetsTask, groupsTask, driversTask, stationsTask, fuelTypesTask, attendantsTask, shiftsTask);

            var sales = await salesTask;
            var customers = (await customersTask).ToDictionary(item => item.Id, item => $"{item.Code} · {item.Name}");
            var vehicles = (await vehiclesTask).ToDictionary(item => item.Id, item => item.Plate);
            var cards = (await cardsTask).ToDictionary(item => item.Id, item => $"{item.CardCode} · {item.DisplayName} ({item.UnitId})");
            var fleets = (await fleetsTask).ToDictionary(item => item.Id, item => $"{item.Code} · {item.Name}");
            var groups = (await groupsTask).ToDictionary(item => item.Id, item => $"{item.Code} · {item.Name}");
            var drivers = (await driversTask).ToDictionary(item => item.Id, item => item.FullName);
            var stations = (await stationsTask).ToDictionary(item => item.Id, item => item.DisplayName);
            var fuelTypes = (await fuelTypesTask).ToDictionary(item => item.Id, item => item.DisplayName);
            var attendants = (await attendantsTask).ToDictionary(item => item.Id, item => item.FullName);
            var shifts = (await shiftsTask).ToDictionary(item => item.Id, item => item.Name);

            // Pump requests are grouped by station, never by sale row.
            var pumpTasks = sales.Select(item => item.StationId).Distinct()
                .ToDictionary(id => id, id => apiClient.GetAsync<IReadOnlyList<PumpDto>>($"stations/{id}/pumps?limit=100"));
            await Task.WhenAll(pumpTasks.Values);
            var pumps = pumpTasks.Values.SelectMany(task => task.Result).ToDictionary(item => item.Id, item => item.Code);

            _allSales.Clear();
            foreach (var sale in sales)
            {
                sale.CustomerLabel = sale.CustomerId is int customerId && customers.TryGetValue(customerId, out var customer) ? customer : "Legacy / müşteri yok";
                sale.VehicleLabel = sale.VehicleId is int vehicleId && vehicles.TryGetValue(vehicleId, out var vehicle) ? vehicle : "Legacy / araç yok";
                sale.CardLabel = sale.FuelCardId is int cardId && cards.TryGetValue(cardId, out var card) ? card : "Legacy / kart yok";
                sale.FleetLabel = sale.FleetId is int fleetId && fleets.TryGetValue(fleetId, out var fleet) ? fleet : "—";
                sale.FleetGroupLabel = sale.FleetGroupId is int groupId && groups.TryGetValue(groupId, out var group) ? group : "—";
                sale.DriverLabel = sale.DriverId is int driverId && drivers.TryGetValue(driverId, out var driver) ? driver : "—";
                sale.StationLabel = stations.GetValueOrDefault(sale.StationId, $"İstasyon #{sale.StationId}");
                sale.PumpLabel = pumps.GetValueOrDefault(sale.PumpId, $"Pompa #{sale.PumpId}");
                sale.FuelTypeLabel = fuelTypes.GetValueOrDefault(sale.FuelTypeId, $"Yakıt #{sale.FuelTypeId}");
                sale.AttendantLabel = sale.AttendantName ?? (sale.AttendantId is int attendantId && attendants.TryGetValue(attendantId, out var attendant) ? attendant : "—");
                sale.ShiftLabel = sale.ShiftName ?? (sale.ShiftId is int shiftId && shifts.TryGetValue(shiftId, out var shift) ? shift : "—");
                _allSales.Add(sale);
            }

            ApplyFilter(selectedId);
            OnPropertyChanged(nameof(IsEmpty));
            RuntimeDiagnostics.Trace($"Sales response completed; collection count={Sales.Count}; IsEmpty={IsEmpty}");
        }
        catch (Exception ex) { RuntimeDiagnostics.Exception("Sales load", ex); ErrorMessage = ToMessage(ex); }
        finally { IsLoading = false; RuntimeDiagnostics.Trace($"Sales final UI state; IsLoading={IsLoading}; IsEmpty={IsEmpty}"); }
    }

    partial void OnSelectedSaleTypeChanged(string value)
    {
        ApplyFilter();
        OnPropertyChanged(nameof(EmptyStateMessage));
    }

    public void StartAutoRefresh()
    {
        if (_refreshCancellation is not null) return;
        _refreshCancellation = new CancellationTokenSource();
        _ = RefreshLoopAsync(_refreshCancellation.Token);
    }

    public void StopAutoRefresh()
    {
        _refreshCancellation?.Cancel();
        _refreshCancellation?.Dispose();
        _refreshCancellation = null;
    }

    private async Task RefreshLoopAsync(CancellationToken token)
    {
        try
        {
            while (!token.IsCancellationRequested)
            {
                await Task.Delay(TimeSpan.FromSeconds(3), token);
                if (!token.IsCancellationRequested) await LoadAsync();
            }
        }
        catch (OperationCanceledException) { }
    }

    private void ApplyFilter(int? selectedId = null)
    {
        selectedId ??= SelectedSale?.Id;
        var filtered = _allSales
            .Where(item => SelectedSaleType == "Tümü" || string.Equals(item.SaleKind, SelectedSaleType, StringComparison.OrdinalIgnoreCase))
            // Completion time is canonical for the history feed; simulation timestamps
            // remain displayed but cannot let legacy future rows hide new sales.
            .OrderByDescending(item => item.CreatedAt)
            .ThenByDescending(item => item.Id)
            .ToList();
        Sales.Clear();
        foreach (var sale in filtered) Sales.Add(sale);
        SelectedSale = selectedId is null
            ? Sales.FirstOrDefault()
            : Sales.FirstOrDefault(item => item.Id == selectedId) ?? Sales.FirstOrDefault();
        OnPropertyChanged(nameof(IsEmpty));
    }

    private static string ToMessage(Exception ex)
    {
        var api = ex as ApiException;
        var message = api?.Message ?? ex.Message;
        return api?.ErrorCode == "VALIDATION_ERROR" || message.Contains("Request validation failed", StringComparison.OrdinalIgnoreCase)
            ? "Satış verisi doğrulanamadı. Filtreleri kontrol edip tekrar deneyin."
            : message;
    }
}
