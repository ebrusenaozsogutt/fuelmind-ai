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
    public IReadOnlyList<string> Statuses { get; } = ["ALL", "OPEN", "INVESTIGATING", "RESOLVED"];
    public IReadOnlyList<string> FaultTypes { get; } = ["ALL", "COMMUNICATION", "CONNECTION", "INITIALIZATION", "INTERFACE", "SENSOR", "EQUIPMENT", "NOZZLE"];
    public IReadOnlyList<string> FaultCodes { get; } = ["ALL", "INTERFACE_ERROR", "PUMP_NOT_CONNECTED", "USC_INITIALIZATION_ERROR", "PORT_COMMUNICATION_ERROR", "PROBE_COMMUNICATION_ERROR", "SENSOR_ERROR", "NOZZLE_ERROR"];
    public IReadOnlyList<string> TargetTypes { get; } = ["ALL", "CONTROLLER", "PORT", "PUMP", "PROBE", "NOZZLE", "TANK", "SENSOR"];

    [ObservableProperty] private FaultDto? _selectedFault;
    [ObservableProperty] private string _status = "ALL";
    [ObservableProperty] private StationDto? _filterStation;
    [ObservableProperty] private string _filterFaultType = "ALL";
    [ObservableProperty] private string _filterFaultCode = "ALL";
    [ObservableProperty] private string _filterTargetType = "ALL";
    [ObservableProperty] private DateTime? _detectedFrom;
    [ObservableProperty] private DateTime? _detectedTo;
    [ObservableProperty] private string? _resolutionNote;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;
    [ObservableProperty] private string? _successMessage;

    public bool IsEmpty => !IsLoading && Faults.Count == 0 && ErrorMessage is null;
    public bool CanInvestigate => SelectedFault?.Status == "OPEN";
    public bool CanResolve => SelectedFault?.Status is "OPEN" or "INVESTIGATING";

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

    [RelayCommand]
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

    [RelayCommand] private async Task ResolveAsync()
    {
        if (SelectedFault is not { } fault || !CanResolve) return;
        if (string.IsNullOrWhiteSpace(ResolutionNote)) { ErrorMessage = "Arızayı çözmek için çözüm notu zorunludur."; return; }
        await Run(async () =>
        {
            var updated = await service.ResolveAsync(fault.Id, ResolutionNote.Trim());
            ResolutionNote = updated.ResolutionNote;
            await LoadFaultsCoreAsync(updated.Id, updated);
            SuccessMessage = $"Arıza #{updated.Id} çözüldü.";
        });
    }

    partial void OnSelectedFaultChanged(FaultDto? value)
    {
        ResolutionNote = value?.ResolutionNote;
        OnPropertyChanged(nameof(CanInvestigate));
        OnPropertyChanged(nameof(CanResolve));
    }

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
        Add("station_id", FilterStation?.Id.ToString(CultureInfo.InvariantCulture)); Add("fault_type", FilterFaultType == "ALL" ? null : FilterFaultType); Add("fault_code", FilterFaultCode == "ALL" ? null : FilterFaultCode); Add("status", Status == "ALL" ? null : Status); Add("target_type", FilterTargetType == "ALL" ? null : FilterTargetType); Add("detected_from", FormatDate(DetectedFrom, false)); Add("detected_to", FormatDate(DetectedTo, true));
        return parts.Count == 0 ? "" : "?" + string.Join("&", parts);
        void Add(string key, string? value) { if (!string.IsNullOrWhiteSpace(value)) parts.Add($"{key}={Uri.EscapeDataString(value)}"); }
    }
    private static string? FormatDate(DateTime? value, bool endOfDay) => value is DateTime date ? new DateTimeOffset(DateTime.SpecifyKind(endOfDay ? date.Date.AddDays(1).AddTicks(-1) : date.Date, DateTimeKind.Local)).ToUniversalTime().ToString("O") : null;
    private async Task Run(Func<Task> action) { if (IsLoading) return; IsLoading = true; ErrorMessage = null; SuccessMessage = null; try { await action(); } catch (Exception ex) { ErrorMessage = ErrorText(ex); } finally { IsLoading = false; OnPropertyChanged(nameof(IsEmpty)); } }
    private void ResetFilters() => (FilterStation, FilterFaultType, FilterFaultCode, FilterTargetType, Status, DetectedFrom, DetectedTo) = (null, "ALL", "ALL", "ALL", "ALL", null, null);
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
                    : message;
    }
    private static void Replace<T>(ObservableCollection<T> destination, IEnumerable<T> items) { destination.Clear(); foreach (var item in items) destination.Add(item); }
}
