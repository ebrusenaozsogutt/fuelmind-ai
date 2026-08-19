using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Windows.Data;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Alarms;
using FuelMind.Desktop.Dtos.Faults;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class AlarmsViewModel : ObservableObject
{
    private readonly IAlarmService _service;
    private readonly SynchronizationContext? _context = SynchronizationContext.Current;
    private CancellationTokenSource? _detailCancellation;
    private bool _isApplyingDetail;

    public ObservableCollection<AlarmDto> Alarms { get; } = [];
    public event EventHandler? AlarmsChanged;
    public ICollectionView FilteredAlarms { get; }

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanAcknowledge))]
    [NotifyPropertyChangedFor(nameof(CanInvestigate))]
    [NotifyPropertyChangedFor(nameof(CanResolve))]
    [NotifyPropertyChangedFor(nameof(CanFalsePositive))]
    private AlarmDto? _selectedAlarm;

    [ObservableProperty] private string? _resolutionNote;
    [ObservableProperty] private string _statusFilter = "ACTIVE";
    [ObservableProperty] private string _severityFilter = "ALL";
    [ObservableProperty] private string _typeFilter = "ALL";
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private bool _isDetailLoading;
    [ObservableProperty] private bool _isFaultLoading;
    [ObservableProperty] private FaultDto? _relatedFault;
    [ObservableProperty] private string? _lastError;

    public IReadOnlyList<string> StatusFilters { get; } =
        ["ACTIVE", "ALL", "NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"];
    public IReadOnlyList<string> SeverityFilters { get; } =
        ["ALL", "LOW", "MEDIUM", "HIGH", "CRITICAL"];
    public IReadOnlyList<string> TypeFilters { get; } =
        ["ALL", "LOW_FLOW", "HIGH_MOTOR_CURRENT", "HIGH_PRESSURE", "HIGH_WATER_LEVEL",
         "LOW_DATA_QUALITY", "SENSOR_STUCK", "TANK_SALES_MISMATCH", "SENSOR_SPIKE", "AI_ANOMALY"];

    public string FaultRelationText => RelatedFault is null
        ? "İlişkili arıza kaydı yok"
        : $"İlişkili Arıza: #{RelatedFault.Id}\nKod: {RelatedFault.FaultCode}\nDurum: {RelatedFault.Status}";

    private readonly IFaultService? _faultService;

    public AlarmsViewModel(IAlarmService service, LiveWebSocketService socket, IFaultService? faultService = null)
    {
        _service = service;
        _faultService = faultService;
        FilteredAlarms = CollectionViewSource.GetDefaultView(Alarms);
        FilteredAlarms.Filter = MatchesFilter;
        socket.MessageReceived += (_, result) =>
        {
            if (result.Message is AlarmCreatedDto alarm)
            {
                Dispatch(() => AddLive(alarm));
            }
        };
    }

    public async Task LoadAsync()
    {
        LastError = null;
        IsLoading = true;
        try
        {
            var loaded = await _service.GetAllAsync();
            Dispatch(() =>
            {
                Alarms.Clear();
                foreach (var item in loaded)
                {
                    Alarms.Add(item);
                }

                FilteredAlarms.Refresh();
                AlarmsChanged?.Invoke(this, EventArgs.Empty);
            });
        }
        catch (Exception exception)
        {
            Dispatch(() => LastError = exception.Message);
        }
        finally
        {
            Dispatch(() => IsLoading = false);
        }
    }

    public void ApplyNavigationFilter(AlarmNavigationFilter filter)
    {
        StatusFilter = "ACTIVE";
        SeverityFilter = filter.Severity ?? "ALL";
        TypeFilter = "ALL";
    }

    [RelayCommand]
    private Task RefreshAsync() => LoadAsync();

    public bool CanAcknowledge => HasStatus("NEW");
    public bool CanInvestigate => HasStatus("NEW", "ACKNOWLEDGED");
    public bool CanResolve => HasStatus("NEW", "ACKNOWLEDGED", "INVESTIGATING");
    public bool CanFalsePositive => CanResolve;

    [RelayCommand] private Task AcknowledgeAsync() => UpdateAsync("acknowledge");
    [RelayCommand] private Task InvestigateAsync() => UpdateAsync("investigate");
    [RelayCommand] private Task ResolveAsync() => UpdateAsync("resolve");
    [RelayCommand] private Task FalsePositiveAsync() => UpdateAsync("false-positive");

    partial void OnSelectedAlarmChanged(AlarmDto? value)
    {
        ResolutionNote = value?.ExistingResolutionNote;
        if (_isApplyingDetail)
        {
            return;
        }

        _detailCancellation?.Cancel();
        _detailCancellation?.Dispose();
        _detailCancellation = null;
        if (value is null)
        {
            IsDetailLoading = false;
            RelatedFault = null;
            return;
        }

        RelatedFault = null;
        _ = LoadRelatedFaultAsync(value.Id);
        _detailCancellation = new CancellationTokenSource();
        _ = LoadSelectedAlarmDetailAsync(value.Id, _detailCancellation.Token);
    }

    private async Task LoadRelatedFaultAsync(int alarmId)
    {
        if (_faultService is null)
        {
            return;
        }

        IsFaultLoading = true;
        try
        {
            var faults = await _faultService.ListAsync($"?alarm_id={alarmId}");
            if (SelectedAlarm?.Id == alarmId)
            {
                RelatedFault = faults.FirstOrDefault();
            }
        }
        catch (Exception exception)
        {
            if (SelectedAlarm?.Id == alarmId)
            {
                LastError = exception is ApiException api ? api.Message : exception.Message;
            }
        }
        finally
        {
            if (SelectedAlarm?.Id == alarmId)
            {
                IsFaultLoading = false;
            }
        }
    }

    partial void OnRelatedFaultChanged(FaultDto? value) => OnPropertyChanged(nameof(FaultRelationText));

    internal async Task LoadSelectedAlarmDetailAsync(int alarmId, CancellationToken token = default)
    {
        IsDetailLoading = true;
        try
        {
            var detail = await _service.GetByIdAsync(alarmId, token);
            if (token.IsCancellationRequested)
            {
                return;
            }

            Dispatch(() =>
            {
                if (SelectedAlarm?.Id != alarmId)
                {
                    return;
                }

                ReplaceAlarm(detail);
                _isApplyingDetail = true;
                try
                {
                    SelectedAlarm = detail;
                }
                finally
                {
                    _isApplyingDetail = false;
                }
                ResolutionNote = detail.ExistingResolutionNote;
            });
        }
        catch (OperationCanceledException) when (token.IsCancellationRequested)
        {
        }
        catch (Exception exception)
        {
            Dispatch(() => LastError = exception.Message);
        }
        finally
        {
            if (!token.IsCancellationRequested)
            {
                Dispatch(() => IsDetailLoading = false);
            }
        }
    }

    private async Task UpdateAsync(string action)
    {
        if (SelectedAlarm is null)
        {
            return;
        }

        LastError = null;
        try
        {
            var updated = await _service.UpdateAsync(SelectedAlarm.Id, action, ResolutionNote);
            Dispatch(() =>
            {
                ReplaceAlarm(updated);
                _isApplyingDetail = true;
                try
                {
                    SelectedAlarm = updated;
                }
                finally
                {
                    _isApplyingDetail = false;
                }
                FilteredAlarms.Refresh();
                AlarmsChanged?.Invoke(this, EventArgs.Empty);
            });
        }
        catch (Exception exception)
        {
            Dispatch(() => LastError = exception.Message);
        }
    }

    private void AddLive(AlarmCreatedDto value)
    {
        if (Alarms.Any(x => x.Id == value.AlarmId))
        {
            return;
        }

        Alarms.Insert(0, new AlarmDto
        {
            Id = value.AlarmId,
            StationId = value.StationId,
            TankId = value.TankId,
            PumpId = value.PumpId,
            AlarmType = value.AlarmType,
            Severity = value.Severity,
            Title = value.Title,
            Description = value.Description,
            RecommendedAction = value.RecommendedAction,
            ProbableCauses = value.ProbableCauses,
            AnomalyScore = value.AnomalyScore,
            RiskLevel = value.RiskLevel,
            DecisionSource = value.DecisionSource,
            AnomalyType = value.AnomalyType,
            ModelVersion = value.ModelVersion,
            ModelOutlier = value.ModelOutlier,
            TriggeredRules = value.TriggeredRules,
            Findings = value.Findings,
            RecommendedChecks = value.RecommendedChecks,
            DataQualityNote = value.DataQualityNote,
            Status = value.Status,
            DetectedAt = value.DetectedAt,
        });
        FilteredAlarms.Refresh();
        AlarmsChanged?.Invoke(this, EventArgs.Empty);
    }

    private void ReplaceAlarm(AlarmDto alarm)
    {
        var current = Alarms.FirstOrDefault(item => item.Id == alarm.Id);
        if (current is not null)
        {
            Alarms[Alarms.IndexOf(current)] = alarm;
        }
    }

    partial void OnStatusFilterChanged(string value) => FilteredAlarms.Refresh();
    partial void OnSeverityFilterChanged(string value) => FilteredAlarms.Refresh();
    partial void OnTypeFilterChanged(string value) => FilteredAlarms.Refresh();

    private bool MatchesFilter(object value) => value is AlarmDto alarm
        && (StatusFilter == "ALL" ||
            (StatusFilter == "ACTIVE" && IsActiveStatus(alarm.Status)) ||
            string.Equals(alarm.Status, StatusFilter, StringComparison.OrdinalIgnoreCase))
        && (SeverityFilter == "ALL" || string.Equals(alarm.Severity, SeverityFilter, StringComparison.OrdinalIgnoreCase))
        && (TypeFilter == "ALL" || string.Equals(alarm.AlarmType, TypeFilter, StringComparison.OrdinalIgnoreCase));

    private static bool IsActiveStatus(string? status) => status is "NEW" or "ACKNOWLEDGED" or "INVESTIGATING";
    private bool HasStatus(params string[] statuses) => SelectedAlarm?.Status is { } status
        && statuses.Contains(status, StringComparer.OrdinalIgnoreCase);

    private void Dispatch(Action action)
    {
        if (_context is null || SynchronizationContext.Current == _context)
        {
            action();
        }
        else
        {
            _context.Post(_ => action(), null);
        }
    }
}
