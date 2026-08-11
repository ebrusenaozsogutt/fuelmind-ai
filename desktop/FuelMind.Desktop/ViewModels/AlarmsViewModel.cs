using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Windows.Data;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Alarms;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.ViewModels;
public sealed partial class AlarmsViewModel : ObservableObject
{
    private readonly AlarmService _service; private readonly SynchronizationContext? _context = SynchronizationContext.Current;
    public ObservableCollection<AlarmDto> Alarms { get; } = [];
    public event EventHandler? AlarmsChanged;
    public ICollectionView FilteredAlarms { get; }
    [ObservableProperty, NotifyPropertyChangedFor(nameof(CanAcknowledge)), NotifyPropertyChangedFor(nameof(CanInvestigate)), NotifyPropertyChangedFor(nameof(CanResolve)), NotifyPropertyChangedFor(nameof(CanFalsePositive))] private AlarmDto? _selectedAlarm;
    [ObservableProperty] private string? _resolutionNote;
    [ObservableProperty] private string _statusFilter = "ALL";
    [ObservableProperty] private string _severityFilter = "ALL";
    [ObservableProperty] private string _typeFilter = "ALL";
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private string? _lastError;

    public IReadOnlyList<string> StatusFilters { get; } = ["ALL", "NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"];
    public IReadOnlyList<string> SeverityFilters { get; } = ["ALL", "LOW", "MEDIUM", "HIGH", "CRITICAL"];
    public IReadOnlyList<string> TypeFilters { get; } = ["ALL", "LOW_FLOW", "HIGH_MOTOR_CURRENT", "HIGH_PRESSURE", "HIGH_WATER_LEVEL", "LOW_DATA_QUALITY", "SENSOR_STUCK", "TANK_SALES_MISMATCH", "SENSOR_SPIKE"];

    public AlarmsViewModel(AlarmService service, LiveWebSocketService socket)
    {
        _service = service;
        FilteredAlarms = CollectionViewSource.GetDefaultView(Alarms);
        FilteredAlarms.Filter = MatchesFilter;
        socket.MessageReceived += (_, result) => { if (result.Message is AlarmCreatedDto alarm) Dispatch(() => AddLive(alarm)); };
    }

    public async Task LoadAsync()
    {
        LastError = null;
        IsLoading = true;
        try
        {
            var loaded = await _service.GetAllAsync();
            Dispatch(() => { Alarms.Clear(); foreach (var item in loaded) Alarms.Add(item); FilteredAlarms.Refresh(); AlarmsChanged?.Invoke(this, EventArgs.Empty); });
        }
        catch (Exception exception) { Dispatch(() => LastError = exception.Message); }
        finally { Dispatch(() => IsLoading = false); }
    }
    [RelayCommand] private Task RefreshAsync() => LoadAsync();
    public bool CanAcknowledge => HasStatus("NEW");
    public bool CanInvestigate => HasStatus("NEW", "ACKNOWLEDGED");
    public bool CanResolve => HasStatus("NEW", "ACKNOWLEDGED", "INVESTIGATING");
    public bool CanFalsePositive => CanResolve;
    [RelayCommand] private Task AcknowledgeAsync() => UpdateAsync("acknowledge"); [RelayCommand] private Task InvestigateAsync() => UpdateAsync("investigate"); [RelayCommand] private Task ResolveAsync() => UpdateAsync("resolve"); [RelayCommand] private Task FalsePositiveAsync() => UpdateAsync("false-positive");
    private async Task UpdateAsync(string action)
    {
        if (SelectedAlarm is null) return;
        LastError = null;
        try
        {
            var updated = await _service.UpdateAsync(SelectedAlarm.Id, action, ResolutionNote);
            Dispatch(() => { var index = Alarms.IndexOf(SelectedAlarm); if (index >= 0) Alarms[index] = updated; SelectedAlarm = updated; FilteredAlarms.Refresh(); AlarmsChanged?.Invoke(this, EventArgs.Empty); });
        }
        catch (Exception exception) { Dispatch(() => LastError = exception.Message); }
    }
    private void AddLive(AlarmCreatedDto value)
    {
        if (Alarms.Any(x => x.Id == value.AlarmId)) return;
        Alarms.Insert(0, new AlarmDto { Id=value.AlarmId, StationId=value.StationId, TankId=value.TankId, PumpId=value.PumpId, AlarmType=value.AlarmType, Severity=value.Severity, Title=value.Title, Description=value.Description, RecommendedAction=value.RecommendedAction, ProbableCauses=value.ProbableCauses, Status=value.Status, DetectedAt=value.DetectedAt });
        FilteredAlarms.Refresh();
        AlarmsChanged?.Invoke(this, EventArgs.Empty);
    }
    partial void OnStatusFilterChanged(string value) => FilteredAlarms.Refresh();
    partial void OnSeverityFilterChanged(string value) => FilteredAlarms.Refresh();
    partial void OnTypeFilterChanged(string value) => FilteredAlarms.Refresh();
    private bool MatchesFilter(object value) => value is AlarmDto alarm &&
        (StatusFilter == "ALL" || string.Equals(alarm.Status, StatusFilter, StringComparison.OrdinalIgnoreCase)) &&
        (SeverityFilter == "ALL" || string.Equals(alarm.Severity, SeverityFilter, StringComparison.OrdinalIgnoreCase)) &&
        (TypeFilter == "ALL" || string.Equals(alarm.AlarmType, TypeFilter, StringComparison.OrdinalIgnoreCase));
    private bool HasStatus(params string[] statuses) => SelectedAlarm?.Status is { } status && statuses.Contains(status, StringComparer.OrdinalIgnoreCase);
    private void Dispatch(Action action) { if (_context is null || SynchronizationContext.Current == _context) action(); else _context.Post(_ => action(), null); }
}
