using System.Collections.ObjectModel;
using System.Globalization;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Alarms;
using FuelMind.Desktop.Dtos.Faults;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class FaultsViewModel(IFaultService service, IStationService stations, IAlarmService alarms) : ObservableObject
{
    public ObservableCollection<FaultDto> Faults { get; } = [];
    public ObservableCollection<StationDto> Stations { get; } = [];
    public ObservableCollection<AlarmDto> RelatedAlarms { get; } = [];
    public ObservableCollection<FaultTargetOption> Targets { get; } = [];
    public IReadOnlyList<string> Statuses { get; } = ["ALL", "OPEN", "INVESTIGATING", "RESOLVED"];
    public IReadOnlyList<string> FaultTypes { get; } = ["COMMUNICATION", "CONNECTION", "INITIALIZATION", "INTERFACE", "SENSOR", "EQUIPMENT", "NOZZLE"];
    public IReadOnlyList<string> FaultCodes { get; } = ["INTERFACE_ERROR", "PUMP_NOT_CONNECTED", "USC_INITIALIZATION_ERROR", "PORT_COMMUNICATION_ERROR", "PROBE_COMMUNICATION_ERROR", "SENSOR_ERROR", "NOZZLE_ERROR"];
    public IReadOnlyList<string> TargetTypes { get; } = ["CONTROLLER", "PORT", "PUMP", "PROBE", "NOZZLE", "TANK", "SENSOR"];

    [ObservableProperty] private FaultDto? _selectedFault;
    [ObservableProperty] private string _status = "ALL";
    [ObservableProperty] private StationDto? _filterStation;
    [ObservableProperty] private string _filterFaultType = "ALL";
    [ObservableProperty] private string _filterFaultCode = "ALL";
    [ObservableProperty] private string _filterTargetType = "ALL";
    [ObservableProperty] private DateTime? _detectedFrom;
    [ObservableProperty] private DateTime? _detectedTo;
    [ObservableProperty] private string? _resolutionNote;
    [ObservableProperty] private StationDto? _createStation;
    [ObservableProperty] private AlarmDto? _relatedAlarm;
    [ObservableProperty] private string _targetType = "PUMP";
    [ObservableProperty] private FaultTargetOption? _selectedTarget;
    [ObservableProperty] private string _createFaultType = "EQUIPMENT";
    [ObservableProperty] private string _createFaultCode = "PUMP_NOT_CONNECTED";
    [ObservableProperty] private string _title = "";
    [ObservableProperty] private string? _description;
    [ObservableProperty] private string? _cause;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private bool _isTargetLoading;
    [ObservableProperty] private string? _errorMessage;
    [ObservableProperty] private string? _successMessage;
    [ObservableProperty] private string? _targetHint;

    public bool IsEmpty => !IsLoading && Faults.Count == 0 && ErrorMessage is null;
    public bool CanInvestigate => SelectedFault?.Status == "OPEN";
    public bool CanResolve => SelectedFault?.Status is "OPEN" or "INVESTIGATING";

    public async Task LoadAsync() => await Run(async () => { Replace(Stations, await stations.GetActiveStationsAsync()); await LoadFaultsCoreAsync(); });
    [RelayCommand] private Task RefreshAsync() => LoadAsync();
    [RelayCommand] private Task ApplyFiltersAsync() => Run(LoadFaultsCoreAsync);
    [RelayCommand] private async Task ClearFiltersAsync()
    {
        FilterStation = null; FilterFaultType = "ALL"; FilterFaultCode = "ALL"; FilterTargetType = "ALL"; Status = "ALL"; DetectedFrom = null; DetectedTo = null;
        await Run(LoadFaultsCoreAsync);
    }

    [RelayCommand] private async Task CreateAsync()
    {
        if (CreateStation is null || SelectedTarget is null || string.IsNullOrWhiteSpace(Title)) { ErrorMessage = "İstasyon, hedef ve başlık zorunludur."; return; }
        await Run(async () =>
        {
            var created = await service.CreateAsync(new FaultCreateDto { StationId = CreateStation.Id, AlarmId = RelatedAlarm?.Id, TargetType = TargetType, TargetId = SelectedTarget.Id, FaultType = CreateFaultType, FaultCode = CreateFaultCode, Title = Title.Trim(), Description = EmptyToNull(Description), Cause = EmptyToNull(Cause) });
            await LoadFaultsCoreAsync();
            SelectedFault = Faults.FirstOrDefault(item => item.Id == created.Id) ?? created;
            RelatedAlarm = null; SelectedTarget = null; Title = ""; Description = null; Cause = null;
            SuccessMessage = $"Arıza #{created.Id} oluşturuldu.";
        });
    }

    [RelayCommand] private async Task InvestigateAsync() { if (SelectedFault is null) return; await Run(async () => { await service.InvestigateAsync(SelectedFault.Id); await LoadFaultsCoreAsync(); }); }
    [RelayCommand] private async Task ResolveAsync()
    {
        if (SelectedFault is null || string.IsNullOrWhiteSpace(ResolutionNote)) { ErrorMessage = "Çözüm notu zorunludur."; return; }
        await Run(async () => { await service.ResolveAsync(SelectedFault.Id, ResolutionNote); ResolutionNote = null; await LoadFaultsCoreAsync(); });
    }

    partial void OnSelectedFaultChanged(FaultDto? value) { OnPropertyChanged(nameof(CanInvestigate)); OnPropertyChanged(nameof(CanResolve)); }
    partial void OnCreateStationChanged(StationDto? value)
    {
        RelatedAlarm = null; Targets.Clear(); SelectedTarget = null; TargetHint = null;
        if (value is not null) _ = LoadCreateDependenciesAsync(value.Id, TargetType);
    }
    partial void OnTargetTypeChanged(string value)
    {
        Targets.Clear(); SelectedTarget = null; TargetHint = null;
        if (CreateStation is not null) _ = LoadTargetsAsync(CreateStation.Id, value);
    }

    private async Task LoadCreateDependenciesAsync(int stationId, string targetType)
    {
        try { var stationAlarms = await alarms.GetAllAsync(includeFalsePositives: true); if (CreateStation?.Id != stationId) return; Replace(RelatedAlarms, stationAlarms.Where(item => item.StationId == stationId)); await LoadTargetsAsync(stationId, targetType); }
        catch (Exception ex) { ErrorMessage = ErrorText(ex); }
    }
    private async Task LoadTargetsAsync(int stationId, string targetType)
    {
        IsTargetLoading = true;
        try
        {
            var items = await service.GetTargetsAsync(stationId, targetType);
            if (CreateStation?.Id != stationId || TargetType != targetType) return;
            Replace(Targets, items);
            TargetHint = items.Count == 0 ? "Bu istasyon için seçilebilir hedef bulunamadı." : null;
        }
        catch (Exception ex) { ErrorMessage = ErrorText(ex); }
        finally { IsTargetLoading = false; }
    }
    private async Task LoadFaultsCoreAsync() { Replace(Faults, await service.ListAsync(BuildFilterQuery())); SelectedFault = Faults.FirstOrDefault(); }
    private string BuildFilterQuery()
    {
        var parts = new List<string>();
        Add("station_id", FilterStation?.Id.ToString(CultureInfo.InvariantCulture)); Add("fault_type", FilterFaultType == "ALL" ? null : FilterFaultType); Add("fault_code", FilterFaultCode == "ALL" ? null : FilterFaultCode); Add("status", Status == "ALL" ? null : Status); Add("target_type", FilterTargetType == "ALL" ? null : FilterTargetType); Add("detected_from", FormatDate(DetectedFrom, false)); Add("detected_to", FormatDate(DetectedTo, true));
        return parts.Count == 0 ? "" : "?" + string.Join("&", parts);
        void Add(string key, string? value) { if (!string.IsNullOrWhiteSpace(value)) parts.Add($"{key}={Uri.EscapeDataString(value)}"); }
    }
    private static string? FormatDate(DateTime? value, bool endOfDay) => value is DateTime date ? new DateTimeOffset(DateTime.SpecifyKind(endOfDay ? date.Date.AddDays(1).AddTicks(-1) : date.Date, DateTimeKind.Local)).ToUniversalTime().ToString("O") : null;
    private async Task Run(Func<Task> action) { if (IsLoading) return; IsLoading = true; ErrorMessage = null; SuccessMessage = null; try { await action(); } catch (Exception ex) { ErrorMessage = ErrorText(ex); } finally { IsLoading = false; OnPropertyChanged(nameof(IsEmpty)); } }
    private static string ErrorText(Exception ex) => ex is ApiException api ? api.Message : ex.Message;
    private static string? EmptyToNull(string? text) => string.IsNullOrWhiteSpace(text) ? null : text.Trim();
    private static void Replace<T>(ObservableCollection<T> destination, IEnumerable<T> items) { destination.Clear(); foreach (var item in items) destination.Add(item); }
}
