using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Commercial;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using FuelMind.Desktop.Dtos.Stations;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class FuelPricesViewModel(ICommercialService commercialService, IStationService stationService, AuthState authState) : ObservableObject
{
    public ObservableCollection<FuelPriceReadDto> Prices { get; } = [];
    public ObservableCollection<StationDto> Stations { get; } = [];
    public ObservableCollection<FuelTypeDto> FuelTypes { get; } = [];
    [ObservableProperty] private FuelPriceReadDto? _selectedPrice;
    [ObservableProperty] private int _stationId;
    [ObservableProperty] private int _fuelTypeId;
    [ObservableProperty] private StationDto? _selectedStation;
    [ObservableProperty] private FuelTypeDto? _selectedFuelType;
    [ObservableProperty] private decimal _unitPrice;
    [ObservableProperty] private DateTimeOffset _effectiveFrom = DateTimeOffset.UtcNow;
    [ObservableProperty] private bool _isEditing;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;
    public bool IsEmpty => !IsLoading && Prices.Count == 0 && string.IsNullOrEmpty(ErrorMessage);
    public bool IsAdmin => string.Equals(authState.CurrentUser?.Role, "ADMIN", StringComparison.OrdinalIgnoreCase);
    partial void OnSelectedStationChanged(StationDto? value) { if (value is not null) StationId = value.Id; }
    partial void OnSelectedFuelTypeChanged(FuelTypeDto? value) { if (value is not null) FuelTypeId = value.Id; }
    [RelayCommand] public async Task LoadAsync() => await ExecuteAsync(async () => { var selectedId = SelectedPrice?.Id; var prices = commercialService.GetFuelPricesAsync(); var stations = stationService.GetActiveStationsAsync(); var fuels = stationService.GetFuelTypesAsync(); await Task.WhenAll(prices, stations, fuels); Replace(Stations, await stations); Replace(FuelTypes, await fuels); var stationNames = Stations.ToDictionary(x => x.Id, x => x.DisplayName); var fuelNames = FuelTypes.ToDictionary(x => x.Id, x => x.DisplayName); var loaded = await prices; foreach (var item in loaded) { item.StationDisplayName = stationNames.GetValueOrDefault(item.StationId, $"İstasyon #{item.StationId}"); item.FuelTypeDisplayName = fuelNames.GetValueOrDefault(item.FuelTypeId, $"Yakıt #{item.FuelTypeId}"); } Replace(Prices, loaded); SelectedPrice = selectedId is null ? Prices.FirstOrDefault() : Prices.FirstOrDefault(x => x.Id == selectedId) ?? Prices.FirstOrDefault(); OnPropertyChanged(nameof(IsEmpty)); });
    [RelayCommand] public void EditPrice() { if (!EnsureAdmin() || SelectedPrice is null) return; StationId = SelectedPrice.StationId; FuelTypeId = SelectedPrice.FuelTypeId; SelectedStation = Stations.FirstOrDefault(x => x.Id == StationId); SelectedFuelType = FuelTypes.FirstOrDefault(x => x.Id == FuelTypeId); UnitPrice = SelectedPrice.UnitPrice; EffectiveFrom = SelectedPrice.EffectiveFrom; IsEditing = true; }
    [RelayCommand] public async Task CreatePriceAsync()
    {
        if (!EnsureAdmin() || StationId <= 0 || FuelTypeId <= 0 || UnitPrice <= 0) { if (ErrorMessage is null) ErrorMessage = "İstasyon, yakıt türü ve pozitif birim fiyat zorunludur."; return; }
        await ExecuteAsync(async () => { var request = new FuelPriceSaveDto { StationId = StationId, FuelTypeId = FuelTypeId, UnitPrice = UnitPrice, EffectiveFrom = EffectiveFrom, IsActive = true }; var item = IsEditing && SelectedPrice is not null ? await commercialService.UpdateFuelPriceAsync(SelectedPrice.Id, request) : await commercialService.CreateFuelPriceAsync(request); var index = Prices.ToList().FindIndex(x => x.Id == item.Id); if (index >= 0) Prices[index] = item; else Prices.Insert(0, item); SelectedPrice = item; IsEditing = false; });
    }
    [RelayCommand] public async Task DeactivatePriceAsync() { if (!EnsureAdmin() || SelectedPrice is null) return; await ExecuteAsync(async () => { await commercialService.DeactivateFuelPriceAsync(SelectedPrice.Id); Replace(Prices, await commercialService.GetFuelPricesAsync()); SelectedPrice = Prices.FirstOrDefault(); }); }
    private bool EnsureAdmin() { if (IsAdmin) return true; ErrorMessage = "Bu işlem yalnızca ADMIN rolü için kullanılabilir."; return false; }
    private async Task ExecuteAsync(Func<Task> action) { if (IsLoading) return; IsLoading = true; ErrorMessage = null; try { await action(); } catch (Exception ex) { ErrorMessage = ex is ApiException api ? api.Message : ex.Message; } finally { IsLoading = false; } }
    private static void Replace<T>(ObservableCollection<T> target, IEnumerable<T> source) { target.Clear(); foreach (var item in source) target.Add(item); }
}
