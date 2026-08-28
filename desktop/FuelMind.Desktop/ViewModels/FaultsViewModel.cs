using System.Collections.ObjectModel;
using System.Globalization;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Faults;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class FaultsViewModel(IFaultService service, IStationService stations) : ObservableObject
{
    public ObservableCollection<FaultDto> Faults { get; } = [];
    public ObservableCollection<StationDto> Stations { get; } = [];
    public IReadOnlyList<string> Statuses { get; } = ["Tümü", "Açık", "İnceleniyor", "Çözüldü"];
    public IReadOnlyList<string> FaultTypes { get; } = ["Tümü", "Haberleşme", "Bağlantı", "Başlatma", "Arayüz", "Sensör", "Ekipman", "Tabanca"];
    public IReadOnlyList<string> FaultCodes { get; } = ["Tümü", "Arayüz hatası", "Pompa bağlı değil", "USC başlatma hatası", "Port haberleşme hatası", "Probe haberleşme hatası", "Sensör hatası", "Tabanca hatası"];
    public IReadOnlyList<string> TargetTypes { get; } = ["Tümü", "Kontrolör", "Haberleşme Portu", "Pompa", "Probe", "Tabanca", "Tank", "Sensör"];

    [ObservableProperty, NotifyPropertyChangedFor(nameof(CanInvestigate)), NotifyPropertyChangedFor(nameof(CanResolve)), NotifyPropertyChangedFor(nameof(IsResolutionNoteEditable)), NotifyPropertyChangedFor(nameof(ResolutionNoteHelpText)), NotifyCanExecuteChangedFor(nameof(InvestigateCommand)), NotifyCanExecuteChangedFor(nameof(ResolveCommand))] private FaultDto? _selectedFault;
    [ObservableProperty] private string _status = "Tümü";
    [ObservableProperty] private StationDto? _filterStation;
    [ObservableProperty] private string _filterFaultType = "Tümü";
    [ObservableProperty] private string _filterFaultCode = "Tümü";
    [ObservableProperty] private string _filterTargetType = "Tümü";
    [ObservableProperty] private DateTime? _detectedFrom;
    [ObservableProperty] private DateTime? _detectedTo;
    [ObservableProperty, NotifyPropertyChangedFor(nameof(CanResolve)), NotifyCanExecuteChangedFor(nameof(ResolveCommand))] private string _newResolutionNote = "";
    [ObservableProperty, NotifyPropertyChangedFor(nameof(CanInvestigate)), NotifyPropertyChangedFor(nameof(CanResolve)), NotifyPropertyChangedFor(nameof(IsResolutionNoteEditable)), NotifyPropertyChangedFor(nameof(ResolutionNoteHelpText)), NotifyCanExecuteChangedFor(nameof(InvestigateCommand)), NotifyCanExecuteChangedFor(nameof(ResolveCommand))] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;
    [ObservableProperty] private string? _successMessage;

    public bool IsEmpty => !IsLoading && Faults.Count == 0 && ErrorMessage is null;
    public bool CanInvestigate => !IsLoading && HasStatus("OPEN");
    public bool CanResolve => !IsLoading && HasOpenLifecycleStatus() && !string.IsNullOrWhiteSpace(NewResolutionNote);
    public bool IsResolutionNoteEditable => !IsLoading && HasOpenLifecycleStatus();
    public string ResolutionNoteHelpText => SelectedFault is null
        ? "Çözüm notu eklemek için listeden bir arıza seçin."
        : IsResolutionNoteEditable
            ? "Arıza çözülürken yapılan işlemleri bu alana yazın."
            : "Bu arıza daha önce çözüldüğü için durumu değiştirilemez.";

    public async Task LoadAsync() => await Run(async () => { Replace(Stations, await stations.GetActiveStationsAsync()); await LoadFaultsCoreAsync(); });
    [RelayCommand] private Task RefreshAsync() => LoadAsync();
    [RelayCommand] private Task ApplyFiltersAsync() => Run(() => LoadFaultsCoreAsync());
    [RelayCommand] private async Task ClearFiltersAsync()
    {
        ResetFilters();
        await Run(() => LoadFaultsCoreAsync());
    }

    public async Task OpenFaultAsync(int faultId)
    {
        ResetFilters();
        await Run(async () =>
        {
            if (Stations.Count == 0) Replace(Stations, await stations.GetActiveStationsAsync());
            await LoadFaultsCoreAsync(faultId);
            if (SelectedFault?.Id != faultId) ErrorMessage = $"Arıza #{faultId} bulunamadı.";
        });
    }

    [RelayCommand(CanExecute = nameof(CanInvestigateFault))]
    private async Task InvestigateAsync()
    {
        if (SelectedFault is not { } fault || !CanInvestigate) return;
        await Run(async () =>
        {
            var updated = await service.InvestigateAsync(fault.Id);
            await LoadFaultsCoreAsync(updated.Id, updated);
            SuccessMessage = $"Arıza #{updated.Id} incelemeye alındı.";
        });
    }

    [RelayCommand(CanExecute = nameof(CanResolveFault))] private async Task ResolveAsync()
    {
        if (SelectedFault is not { } fault || !CanResolve) return;
        await Run(async () =>
        {
            var updated = await service.ResolveAsync(fault.Id, NewResolutionNote.Trim());
            await LoadFaultsCoreAsync(updated.Id, updated);
            SuccessMessage = $"Arıza #{updated.Id} çözüldü.";
        });
    }

    partial void OnSelectedFaultChanged(FaultDto? value)
    {
        NewResolutionNote = "";
        OnPropertyChanged(nameof(ResolutionNoteHelpText));
    }

    private bool CanInvestigateFault() => CanInvestigate;
    private bool CanResolveFault() => CanResolve;

    private async Task LoadFaultsCoreAsync(int? selectedId = null, FaultDto? selectedFallback = null)
    {
        selectedId ??= SelectedFault?.Id;
        Replace(Faults, await service.ListAsync(BuildFilterQuery()));
        SelectedFault = selectedId is int id
            ? Faults.FirstOrDefault(item => item.Id == id) ?? selectedFallback
            : Faults.FirstOrDefault();
    }
    private string BuildFilterQuery()
    {
        var parts = new List<string>();
        Add("station_id", FilterStation?.Id.ToString(CultureInfo.InvariantCulture)); Add("fault_type", FaultTypeValue(FilterFaultType)); Add("fault_code", FaultCodeValue(FilterFaultCode)); Add("status", StatusValue(Status)); Add("target_type", TargetTypeValue(FilterTargetType)); Add("detected_from", FormatDate(DetectedFrom, false)); Add("detected_to", FormatDate(DetectedTo, true));
        return parts.Count == 0 ? "" : "?" + string.Join("&", parts);
        void Add(string key, string? value) { if (!string.IsNullOrWhiteSpace(value)) parts.Add($"{key}={Uri.EscapeDataString(value)}"); }
    }
    private static string? FormatDate(DateTime? value, bool endOfDay) => value is DateTime date ? new DateTimeOffset(DateTime.SpecifyKind(endOfDay ? date.Date.AddDays(1).AddTicks(-1) : date.Date, DateTimeKind.Local)).ToUniversalTime().ToString("O") : null;
    private async Task Run(Func<Task> action) { if (IsLoading) return; IsLoading = true; ErrorMessage = null; SuccessMessage = null; try { await action(); } catch (Exception ex) { ErrorMessage = ErrorText(ex); } finally { IsLoading = false; OnPropertyChanged(nameof(IsEmpty)); } }
    private bool HasStatus(string expected) => string.Equals(SelectedFault?.Status, expected, StringComparison.OrdinalIgnoreCase);
    private bool HasOpenLifecycleStatus() => HasStatus("OPEN") || HasStatus("INVESTIGATING");
    private static string? StatusValue(string value) => value switch { "Açık" or "OPEN" => "OPEN", "İnceleniyor" or "INVESTIGATING" => "INVESTIGATING", "Çözüldü" or "RESOLVED" => "RESOLVED", _ => null };
    private static string? FaultTypeValue(string value) => value switch { "Haberleşme" or "COMMUNICATION" => "COMMUNICATION", "Bağlantı" or "CONNECTION" => "CONNECTION", "Başlatma" or "INITIALIZATION" => "INITIALIZATION", "Arayüz" or "INTERFACE" => "INTERFACE", "Sensör" or "SENSOR" => "SENSOR", "Ekipman" or "EQUIPMENT" => "EQUIPMENT", "Tabanca" or "NOZZLE" => "NOZZLE", _ => null };
    private static string? FaultCodeValue(string value) => value switch { "Arayüz hatası" or "INTERFACE_ERROR" => "INTERFACE_ERROR", "Pompa bağlı değil" or "PUMP_NOT_CONNECTED" => "PUMP_NOT_CONNECTED", "USC başlatma hatası" or "USC_INITIALIZATION_ERROR" => "USC_INITIALIZATION_ERROR", "Port haberleşme hatası" or "PORT_COMMUNICATION_ERROR" => "PORT_COMMUNICATION_ERROR", "Probe haberleşme hatası" or "PROBE_COMMUNICATION_ERROR" => "PROBE_COMMUNICATION_ERROR", "Sensör hatası" or "SENSOR_ERROR" => "SENSOR_ERROR", "Tabanca hatası" or "NOZZLE_ERROR" => "NOZZLE_ERROR", _ => null };
    private static string? TargetTypeValue(string value) => value switch { "Kontrolör" or "CONTROLLER" => "CONTROLLER", "Haberleşme Portu" or "PORT" => "PORT", "Pompa" or "PUMP" => "PUMP", "Probe" or "PROBE" => "PROBE", "Tabanca" or "NOZZLE" => "NOZZLE", "Tank" or "TANK" => "TANK", "Sensör" or "SENSOR" => "SENSOR", _ => null };
    private void ResetFilters() => (FilterStation, FilterFaultType, FilterFaultCode, FilterTargetType, Status, DetectedFrom, DetectedTo) = (null, "Tümü", "Tümü", "Tümü", "Tümü", null, null);
    private static string ErrorText(Exception ex)
    {
        var api = ex as ApiException;
        var message = api?.Message ?? ex.Message;
        return api?.ErrorCode == "VALIDATION_ERROR" || message.Contains("Request validation failed", StringComparison.OrdinalIgnoreCase)
            ? "İşlem doğrulanamadı. Arıza durumu ve çözüm notunu kontrol edin."
            : message.Contains("already resolved", StringComparison.OrdinalIgnoreCase)
                ? "Bu arıza zaten çözülmüş."
                : message.Contains("cannot be investigated", StringComparison.OrdinalIgnoreCase)
                    ? "Çözülmüş bir arıza yeniden incelemeye alınamaz."
                    : message.Contains("only open faults", StringComparison.OrdinalIgnoreCase)
                        ? "Yalnızca açık arızalar incelemeye alınabilir."
                    : message;
    }
    private static void Replace<T>(ObservableCollection<T> destination, IEnumerable<T> items) { destination.Clear(); foreach (var item in items) destination.Add(item); }
}
