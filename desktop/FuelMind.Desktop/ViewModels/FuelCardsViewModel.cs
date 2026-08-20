using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Commercial;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class FuelCardsViewModel(ICommercialService commercialService, IStationService stationService, AuthState authState) : ObservableObject
{
    private int _configurationLoadVersion;
    public ObservableCollection<FuelCardReadDto> Cards { get; } = [];
    public ObservableCollection<FuelCardLimitReadDto> Limits { get; } = [];
    public ObservableCollection<FuelCardAllowedStationDto> AllowedStations { get; } = [];
    public ObservableCollection<FuelCardAllowedFuelTypeDto> AllowedFuelTypes { get; } = [];
    public ObservableCollection<FuelCardUsageWindowDto> UsageWindows { get; } = [];
    public ObservableCollection<CustomerReadDto> Customers { get; } = [];
    public ObservableCollection<FleetReadDto> Fleets { get; } = [];
    public ObservableCollection<FleetGroupReadDto> FleetGroups { get; } = [];
    public ObservableCollection<VehicleReadDto> Vehicles { get; } = [];
    public ObservableCollection<WeekdayOption> Weekdays { get; } =
    [new(0, "Pazartesi"), new(1, "Salı"), new(2, "Çarşamba"), new(3, "Perşembe"), new(4, "Cuma"), new(5, "Cumartesi"), new(6, "Pazar")];
    public IReadOnlyList<string> CardStatuses { get; } = ["ACTIVE", "PASSIVE", "BLOCKED", "EXPIRED"];
    public IReadOnlyList<string> PaymentTypes { get; } = ["PREPAID", "CREDIT"];
    public IReadOnlyList<string> LimitTypes { get; } = ["PER_TRANSACTION", "DAILY", "WEEKLY", "MONTHLY", "CUSTOM"];

    [ObservableProperty] private FuelCardReadDto? _selectedCard;
    [ObservableProperty] private FuelCardLimitReadDto? _selectedLimit;
    [ObservableProperty] private FuelCardUsageWindowDto? _selectedUsageWindow;
    [ObservableProperty] private CustomerReadDto? _selectedCustomer;
    [ObservableProperty] private FleetReadDto? _selectedFleet;
    [ObservableProperty] private FleetGroupReadDto? _selectedFleetGroup;
    [ObservableProperty] private VehicleReadDto? _selectedVehicle;
    [ObservableProperty] private string _searchText = string.Empty;
    [ObservableProperty] private bool _isCardFormOpen;
    [ObservableProperty] private bool _isEditingCard;
    [ObservableProperty] private string _cardDisplayName = string.Empty;
    [ObservableProperty] private string _cardCode = string.Empty;
    [ObservableProperty] private string _cardUnitId = string.Empty;
    [ObservableProperty] private string _cardStatus = "ACTIVE";
    [ObservableProperty] private DateTime _cardValidFrom = DateTime.Today;
    [ObservableProperty] private DateTime? _cardValidUntil;
    [ObservableProperty] private string _cardPaymentType = "PREPAID";
    [ObservableProperty] private decimal _cardPrepaidBalance;
    [ObservableProperty] private decimal _cardCreditLimit;
    [ObservableProperty] private bool _cardIsActive = true;
    [ObservableProperty] private bool _isLimitFormOpen;
    [ObservableProperty] private bool _isEditingLimit;
    [ObservableProperty] private string _newLimitType = "DAILY";
    [ObservableProperty] private decimal _newLimitLiters;
    [ObservableProperty] private DateTime? _limitValidFrom;
    [ObservableProperty] private DateTime? _limitValidUntil;
    [ObservableProperty] private bool _limitIsActive = true;
    [ObservableProperty] private bool _isUsageWindowFormOpen;
    [ObservableProperty] private bool _isEditingUsageWindow;
    [ObservableProperty] private WeekdayOption? _selectedWeekday;
    [ObservableProperty] private string _usageWindowStart = "08:00";
    [ObservableProperty] private string _usageWindowEnd = "18:00";
    [ObservableProperty] private bool _usageWindowIsActive = true;
    [ObservableProperty] private int _stationId;
    [ObservableProperty] private int _fuelTypeId;
    [ObservableProperty] private decimal _previewLiters;
    [ObservableProperty] private DateTime _previewAt = DateTime.Now;
    [ObservableProperty] private string? _authorizationMessage;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;
    public bool IsAdmin => string.Equals(authState.CurrentUser?.Role, "ADMIN", StringComparison.OrdinalIgnoreCase);
    public bool IsPrepaid => string.Equals(CardPaymentType, "PREPAID", StringComparison.OrdinalIgnoreCase);
    public bool IsCredit => string.Equals(CardPaymentType, "CREDIT", StringComparison.OrdinalIgnoreCase);
    public decimal CardCreditUsed => SelectedCard?.CreditUsed ?? 0;
    public decimal CardAvailableCredit => CardCreditLimit - CardCreditUsed;
    public bool HasUsageWindows => UsageWindows.Count > 0;
    public bool HasNoUsageWindows => !HasUsageWindows;
    public bool HasLimits => Limits.Count > 0;
    public bool IsEmpty => !IsLoading && Cards.Count == 0 && string.IsNullOrEmpty(ErrorMessage);

    partial void OnSelectedCardChanged(FuelCardReadDto? value) { _ = LoadConfigurationAsync(value); OnPropertyChanged(nameof(CardCreditUsed)); }
    partial void OnSelectedCustomerChanged(CustomerReadDto? value) => _ = LoadFleetsAsync(value);
    partial void OnSelectedFleetChanged(FleetReadDto? value) => _ = LoadGroupsAsync(value);
    partial void OnSelectedFleetGroupChanged(FleetGroupReadDto? value) => _ = LoadVehiclesAsync(value);
    partial void OnSelectedVehicleChanged(VehicleReadDto? value) => OnPropertyChanged(nameof(ActiveCardVehicleWarning));
    partial void OnCardPaymentTypeChanged(string value) { OnPropertyChanged(nameof(IsPrepaid)); OnPropertyChanged(nameof(IsCredit)); }
    partial void OnCardCreditLimitChanged(decimal value) => OnPropertyChanged(nameof(CardAvailableCredit));
    partial void OnNewLimitTypeChanged(string value) => OnPropertyChanged(nameof(IsCustomLimit));
    public bool IsCustomLimit => string.Equals(NewLimitType, "CUSTOM", StringComparison.OrdinalIgnoreCase);
    public bool ActiveCardVehicleWarning => !IsEditingCard && SelectedVehicle?.HasActiveFuelCard == true && string.Equals(CardStatus, "ACTIVE", StringComparison.OrdinalIgnoreCase);
    partial void OnCardStatusChanged(string value) => OnPropertyChanged(nameof(ActiveCardVehicleWarning));

    [RelayCommand] public async Task LoadAsync() => await ExecuteAsync(async () =>
    {
        var selectedCardId = SelectedCard?.Id;
        var cardsTask = commercialService.GetFuelCardsAsync(SearchText);
        var vehiclesTask = commercialService.GetVehiclesAsync();
        var groupsTask = commercialService.GetFleetGroupsAsync();
        var fleetsTask = commercialService.GetFleetsAsync();
        var customersTask = commercialService.GetCustomersAsync();
        await Task.WhenAll(cardsTask, vehiclesTask, groupsTask, fleetsTask, customersTask);
        var vehicles = (await vehiclesTask).ToDictionary(item => item.Id);
        var groups = (await groupsTask).ToDictionary(item => item.Id);
        var fleets = (await fleetsTask).ToDictionary(item => item.Id);
        var customers = (await customersTask).ToDictionary(item => item.Id, item => $"{item.Code} · {item.Name}");
        var loadedCards = await cardsTask;
        foreach (var card in loadedCards)
        {
            if (vehicles.TryGetValue(card.VehicleId, out var vehicle))
            {
                card.VehicleLabel = vehicle.Plate;
                if (groups.TryGetValue(vehicle.FleetGroupId, out var group))
                {
                    card.FleetGroupLabel = group.Name;
                    if (fleets.TryGetValue(group.FleetId, out var fleet))
                    {
                        card.FleetLabel = fleet.Name;
                        card.CustomerLabel = customers.GetValueOrDefault(fleet.CustomerId, "—");
                    }
                }
            }
        }
        Replace(Cards, loadedCards);
        // Replace the selected row with the refreshed instance so its child
        // configuration (especially limits) is reloaded after every card refresh.
        SelectedCard = selectedCardId is int id
            ? Cards.FirstOrDefault(card => card.Id == id) ?? Cards.FirstOrDefault()
            : Cards.FirstOrDefault();
        OnPropertyChanged(nameof(IsEmpty));
    });
    [RelayCommand] public async Task OpenCreateCardAsync()
    {
        if (!EnsureAdmin()) return;
        IsEditingCard = false; CardDisplayName = CardCode = CardUnitId = string.Empty; CardStatus = "ACTIVE"; CardPaymentType = "PREPAID";
        CardValidFrom = DateTime.Today; CardValidUntil = null; CardPrepaidBalance = CardCreditLimit = 0; CardIsActive = true;
        SelectedCustomer = null; SelectedFleet = null; SelectedFleetGroup = null; SelectedVehicle = null; Fleets.Clear(); FleetGroups.Clear(); Vehicles.Clear();
        await ExecuteAsync(async () => { Replace(Customers, await commercialService.GetCustomersAsync()); IsCardFormOpen = true; });
    }
    [RelayCommand] public void OpenEditCard()
    {
        if (!EnsureAdmin() || SelectedCard is null) return;
        IsEditingCard = true; CardDisplayName = SelectedCard.DisplayName; CardCode = SelectedCard.CardCode; CardUnitId = SelectedCard.UnitId;
        CardStatus = SelectedCard.Status; CardPaymentType = SelectedCard.PaymentType; CardValidFrom = SelectedCard.ValidFrom.ToDateTime(TimeOnly.MinValue);
        CardValidUntil = SelectedCard.ValidUntil?.ToDateTime(TimeOnly.MinValue); CardPrepaidBalance = SelectedCard.PrepaidBalance; CardCreditLimit = SelectedCard.CreditLimit; CardIsActive = SelectedCard.IsActive;
        IsCardFormOpen = true;
    }
    [RelayCommand] public void CancelCardForm() => IsCardFormOpen = false;
    [RelayCommand] public async Task SaveCardAsync()
    {
        if (!EnsureAdmin() || !ValidateCard()) return;
        await ExecuteAsync(async () =>
        {
            var request = new FuelCardSaveDto { VehicleId = IsEditingCard ? (SelectedVehicle?.Id ?? SelectedCard!.VehicleId) : SelectedVehicle!.Id, CardCode = CardCode, DisplayName = CardDisplayName, UnitId = CardUnitId, Status = CardStatus, ValidFrom = DateOnly.FromDateTime(CardValidFrom), ValidUntil = CardValidUntil is null ? null : DateOnly.FromDateTime(CardValidUntil.Value), PaymentType = CardPaymentType, PrepaidBalance = IsPrepaid ? CardPrepaidBalance : 0, CreditLimit = IsCredit ? CardCreditLimit : 0, IsActive = CardIsActive };
            if (IsEditingCard && SelectedCard is not null) { var updated = await commercialService.UpdateFuelCardAsync(SelectedCard.Id, request); ReplaceOrAdd(Cards, updated); SelectedCard = updated; }
            else { var created = await commercialService.CreateFuelCardAsync(request); Cards.Add(created); SelectedCard = created; }
            IsCardFormOpen = false;
        });
    }
    [RelayCommand] public async Task DeactivateCardAsync()
    {
        if (!EnsureAdmin() || SelectedCard is null) return;
        var selectedId = SelectedCard.Id;
        await ExecuteAsync(async () => { await commercialService.DeactivateFuelCardAsync(selectedId); Replace(Cards, await commercialService.GetFuelCardsAsync(SearchText)); SelectedCard = Cards.FirstOrDefault(x => x.Id == selectedId) ?? Cards.FirstOrDefault(); });
    }

    [RelayCommand] public void OpenCreateLimit() { if (!EnsureAdmin() || SelectedCard is null) return; IsEditingLimit = false; NewLimitType = "DAILY"; NewLimitLiters = 0; LimitValidFrom = LimitValidUntil = null; LimitIsActive = true; IsLimitFormOpen = true; }
    [RelayCommand] public void OpenEditLimit(FuelCardLimitReadDto? limit)
    {
        if (!EnsureAdmin() || limit is null) return; SelectedLimit = limit; IsEditingLimit = true; NewLimitType = limit.LimitType; NewLimitLiters = limit.QuantityLimitLiters; LimitValidFrom = limit.ValidFrom?.ToDateTime(TimeOnly.MinValue); LimitValidUntil = limit.ValidUntil?.ToDateTime(TimeOnly.MinValue); LimitIsActive = limit.IsActive; IsLimitFormOpen = true;
    }
    [RelayCommand] public void CancelLimitForm() => IsLimitFormOpen = false;
    [RelayCommand] public async Task SaveLimitAsync()
    {
        if (!EnsureAdmin() || SelectedCard is null || NewLimitLiters <= 0) { ErrorMessage = "Pozitif litre limiti girin."; return; }
        if (IsCustomLimit && (LimitValidFrom is null || LimitValidUntil is null)) { ErrorMessage = "Kullanıcı tanımlı limitte başlangıç ve bitiş zorunludur."; return; }
        await ExecuteAsync(async () => { var request = new FuelCardLimitSaveDto { FuelCardId = SelectedCard.Id, LimitType = NewLimitType, QuantityLimitLiters = NewLimitLiters, ValidFrom = LimitValidFrom is null ? null : DateOnly.FromDateTime(LimitValidFrom.Value), ValidUntil = LimitValidUntil is null ? null : DateOnly.FromDateTime(LimitValidUntil.Value), IsActive = LimitIsActive }; if (IsEditingLimit && SelectedLimit is not null) await commercialService.UpdateCardLimitAsync(SelectedLimit.Id, request); else await commercialService.CreateCardLimitAsync(request); IsLimitFormOpen = false; await LoadConfigurationAsync(SelectedCard); });
    }
    [RelayCommand] public async Task DeactivateLimitAsync(FuelCardLimitReadDto? limit) { if (!EnsureAdmin() || limit is null) return; await ExecuteAsync(async () => { await commercialService.DeactivateCardLimitAsync(limit.Id); await LoadConfigurationAsync(SelectedCard); }); }

    [RelayCommand] public void OpenCreateUsageWindow() { if (!EnsureAdmin() || SelectedCard is null) return; IsEditingUsageWindow = false; SelectedWeekday = Weekdays[0]; UsageWindowStart = "08:00"; UsageWindowEnd = "18:00"; UsageWindowIsActive = true; IsUsageWindowFormOpen = true; }
    [RelayCommand] public void OpenEditUsageWindow(FuelCardUsageWindowDto? window) { if (!EnsureAdmin() || window is null) return; SelectedUsageWindow = window; IsEditingUsageWindow = true; SelectedWeekday = Weekdays.First(x => x.Value == window.DayOfWeek); UsageWindowStart = window.StartTime.ToString("HH:mm"); UsageWindowEnd = window.EndTime.ToString("HH:mm"); UsageWindowIsActive = window.IsActive; IsUsageWindowFormOpen = true; }
    [RelayCommand] public void CancelUsageWindowForm() => IsUsageWindowFormOpen = false;
    [RelayCommand] public async Task SaveUsageWindowAsync()
    {
        if (!EnsureAdmin() || SelectedCard is null || SelectedWeekday is null || !TimeOnly.TryParse(UsageWindowStart, out var start) || !TimeOnly.TryParse(UsageWindowEnd, out var end) || start >= end) { ErrorMessage = "Geçerli bir gün ve başlangıç/bitiş saati girin."; return; }
        await ExecuteAsync(async () => { var request = new FuelCardUsageWindowSaveDto { FuelCardId = SelectedCard.Id, DayOfWeek = SelectedWeekday.Value, StartTime = start, EndTime = end, IsActive = UsageWindowIsActive }; if (IsEditingUsageWindow && SelectedUsageWindow is not null) await commercialService.UpdateUsageWindowAsync(SelectedUsageWindow.Id, request); else await commercialService.CreateUsageWindowAsync(request); IsUsageWindowFormOpen = false; await LoadConfigurationAsync(SelectedCard); });
    }
    [RelayCommand] public async Task DeactivateUsageWindowAsync(FuelCardUsageWindowDto? window) { if (!EnsureAdmin() || window is null) return; await ExecuteAsync(async () => { await commercialService.DeactivateUsageWindowAsync(window.Id); await LoadConfigurationAsync(SelectedCard); }); }

    [RelayCommand] public async Task AddStationAsync() { if (!EnsureAdmin() || SelectedCard is null || StationId <= 0) { ErrorMessage = "Kart ve istasyon kimliği seçilmelidir."; return; } await ExecuteAsync(async () => { await commercialService.AddAllowedStationAsync(SelectedCard.Id, StationId); await LoadConfigurationAsync(SelectedCard); }); }
    [RelayCommand] public async Task RemoveStationAsync(FuelCardAllowedStationDto? station) { if (!EnsureAdmin() || station is null) return; await ExecuteAsync(async () => { await commercialService.RemoveAllowedStationAsync(station.Id); await LoadConfigurationAsync(SelectedCard); }); }
    [RelayCommand] public async Task AddFuelTypeAsync() { if (!EnsureAdmin() || SelectedCard is null || FuelTypeId <= 0) { ErrorMessage = "Kart ve yakıt türü kimliği seçilmelidir."; return; } await ExecuteAsync(async () => { await commercialService.AddAllowedFuelTypeAsync(SelectedCard.Id, FuelTypeId); await LoadConfigurationAsync(SelectedCard); }); }
    [RelayCommand] public async Task RemoveFuelTypeAsync(FuelCardAllowedFuelTypeDto? fuelType) { if (!EnsureAdmin() || fuelType is null) return; await ExecuteAsync(async () => { await commercialService.RemoveAllowedFuelTypeAsync(fuelType.Id); await LoadConfigurationAsync(SelectedCard); }); }
    [RelayCommand] public async Task PreviewAuthorizationAsync() { if (SelectedCard is null || StationId <= 0 || FuelTypeId <= 0 || PreviewLiters <= 0) { ErrorMessage = "Önizleme için kart, istasyon, yakıt türü ve litre girin."; return; } await ExecuteAsync(async () => { var result = await commercialService.PreviewAuthorizationAsync(new FuelCardAuthorizationRequestDto { UnitId = SelectedCard.UnitId, VehicleId = SelectedCard.VehicleId, StationId = StationId, FuelTypeId = FuelTypeId, RequestedQuantityLiters = PreviewLiters, RequestedAt = new DateTimeOffset(PreviewAt) }); AuthorizationMessage = result.Authorized ? $"YETKİLİ — {result.Message}" : $"REDDEDİLDİ — {result.Message}"; }); }

    private async Task LoadFleetsAsync(CustomerReadDto? customer) { Fleets.Clear(); FleetGroups.Clear(); Vehicles.Clear(); SelectedFleet = null; SelectedFleetGroup = null; SelectedVehicle = null; if (customer is null) return; try { Replace(Fleets, await commercialService.GetFleetsAsync(customer.Id)); } catch (Exception ex) { ErrorMessage = ToMessage(ex); } }
    private async Task LoadGroupsAsync(FleetReadDto? fleet) { FleetGroups.Clear(); Vehicles.Clear(); SelectedFleetGroup = null; SelectedVehicle = null; if (fleet is null) return; try { Replace(FleetGroups, await commercialService.GetFleetGroupsAsync(fleet.Id)); } catch (Exception ex) { ErrorMessage = ToMessage(ex); } }
    private async Task LoadVehiclesAsync(FleetGroupReadDto? group) { Vehicles.Clear(); SelectedVehicle = null; if (group is null) return; try { var vehicles = await commercialService.GetVehiclesAsync(group.Id); var activeCardVehicleIds = Cards.Where(card => card.IsActive && string.Equals(card.Status, "ACTIVE", StringComparison.OrdinalIgnoreCase)).Select(card => card.VehicleId).ToHashSet(); foreach (var vehicle in vehicles) vehicle.HasActiveFuelCard = activeCardVehicleIds.Contains(vehicle.Id); Replace(Vehicles, vehicles); } catch (Exception ex) { ErrorMessage = ToMessage(ex); } }
    private async Task LoadConfigurationAsync(FuelCardReadDto? card)
    {
        var version = Interlocked.Increment(ref _configurationLoadVersion);
        Limits.Clear(); AllowedStations.Clear(); AllowedFuelTypes.Clear(); UsageWindows.Clear(); AuthorizationMessage = null;
        OnPropertyChanged(nameof(HasUsageWindows)); OnPropertyChanged(nameof(HasNoUsageWindows)); OnPropertyChanged(nameof(HasLimits));
        if (card is null) return;
        try
        {
            var limitsTask = commercialService.GetCardLimitsAsync(card.Id);
            var stationsTask = commercialService.GetAllowedStationsAsync(card.Id);
            var fuelTypesTask = commercialService.GetAllowedFuelTypesAsync(card.Id);
            var windowsTask = commercialService.GetUsageWindowsAsync(card.Id);
            var stationCatalogTask = stationService.GetActiveStationsAsync();
            var fuelCatalogTask = stationService.GetFuelTypesAsync();
            await Task.WhenAll(limitsTask, stationsTask, fuelTypesTask, windowsTask, stationCatalogTask, fuelCatalogTask);
            if (version != Volatile.Read(ref _configurationLoadVersion)) return;

            var stationNames = (await stationCatalogTask).ToDictionary(item => item.Id, item => item.DisplayName);
            var fuelNames = (await fuelCatalogTask).ToDictionary(item => item.Id, item => item.DisplayName);
            var allowedStations = await stationsTask;
            foreach (var item in allowedStations) item.StationDisplayName = stationNames.GetValueOrDefault(item.StationId, $"İstasyon #{item.StationId}");
            var allowedFuelTypes = await fuelTypesTask;
            foreach (var item in allowedFuelTypes) item.FuelTypeDisplayName = fuelNames.GetValueOrDefault(item.FuelTypeId, $"Yakıt #{item.FuelTypeId}");
            Replace(Limits, await limitsTask);
            Replace(AllowedStations, allowedStations);
            Replace(AllowedFuelTypes, allowedFuelTypes);
            Replace(UsageWindows, await windowsTask);
            OnPropertyChanged(nameof(HasUsageWindows)); OnPropertyChanged(nameof(HasNoUsageWindows));
            OnPropertyChanged(nameof(HasLimits));
        }
        catch (Exception ex)
        {
            if (version == Volatile.Read(ref _configurationLoadVersion)) ErrorMessage = ToMessage(ex);
        }
    }
    private bool ValidateCard() { if (string.IsNullOrWhiteSpace(CardDisplayName) || string.IsNullOrWhiteSpace(CardCode) || string.IsNullOrWhiteSpace(CardUnitId) || (!IsEditingCard && SelectedVehicle is null)) { ErrorMessage = "Araç, kart adı, kart kodu ve ID Unit zorunludur."; return false; } if (ActiveCardVehicleWarning) { ErrorMessage = "Bu aracın zaten aktif bir yakıt kartı bulunuyor. Mevcut kartı pasifleştirin veya farklı araç seçin."; return false; } if (CardValidUntil is not null && CardValidUntil.Value.Date < CardValidFrom.Date) { ErrorMessage = "Geçerlilik bitişi başlangıçtan önce olamaz."; return false; } return true; }
    private bool EnsureAdmin() { if (IsAdmin) return true; ErrorMessage = "Bu işlem yalnızca ADMIN rolü için kullanılabilir."; return false; }
    private async Task ExecuteAsync(Func<Task> action) { if (IsLoading) return; IsLoading = true; ErrorMessage = null; try { await action(); } catch (Exception ex) { ErrorMessage = ToMessage(ex); } finally { IsLoading = false; } }
    private static string ToMessage(Exception ex)
    {
        var api = ex as ApiException;
        var message = api?.Message ?? ex.Message;
        return api?.ErrorCode == "VALIDATION_ERROR" || message.Contains("Request validation failed", StringComparison.OrdinalIgnoreCase)
            ? "Girilen kart bilgileri doğrulanamadı. Zorunlu alanları kontrol edin."
            : message;
    }
    private static void Replace<T>(ObservableCollection<T> target, IEnumerable<T> source) { target.Clear(); foreach (var item in source) target.Add(item); }
    private static void ReplaceOrAdd(ObservableCollection<FuelCardReadDto> target, FuelCardReadDto item) { var index = target.ToList().FindIndex(x => x.Id == item.Id); if (index >= 0) target[index] = item; else target.Add(item); }
}

public sealed record WeekdayOption(int Value, string Name);
