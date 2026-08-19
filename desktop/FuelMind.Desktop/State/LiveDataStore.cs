using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.State;

public sealed partial class LiveDataStore : ObservableObject
{
    private readonly LiveChartDataService? _liveChartDataService;
    private readonly SynchronizationContext? _context = SynchronizationContext.Current;
    private readonly System.Windows.Threading.Dispatcher? _dispatcher;
    public LiveDataStore(LiveWebSocketService service)
    {
        service.ConnectionStateChanged += (_, state) => Dispatch(() => ConnectionState = state);
        service.MessageReceived += (_, result) => Dispatch(() => Apply(result));
    }
    public LiveDataStore(System.Windows.Threading.Dispatcher dispatcher, LiveChartDataService? liveChartDataService = null)
    {
        _dispatcher = dispatcher;
        _context = new System.Windows.Threading.DispatcherSynchronizationContext(dispatcher);
        _liveChartDataService = liveChartDataService;
    }
    [ObservableProperty] private LiveConnectionState _connectionState = LiveConnectionState.Disconnected;
    [ObservableProperty] private int _selectedStationId;
    [ObservableProperty] private int? _connectedStationId;
    [ObservableProperty] private DateTimeOffset? _lastMessageAt;
    [ObservableProperty] private SimulationTickDto? _lastSimulationTick;
    [ObservableProperty] private int? _lastSequence;
    [ObservableProperty] private int? _lastSimulationRunId;
    [ObservableProperty] private bool _hasSequenceGap;
    [ObservableProperty] private int? _expectedSequence;
    [ObservableProperty] private int? _receivedSequence;
    public ObservableCollection<TankLiveDataDto> Tanks { get; } = [];
    public ObservableCollection<PumpLiveDataDto> Pumps { get; } = [];
    public ObservableCollection<ControllerLiveDto> Controllers { get; } = [];
    public ObservableCollection<CommunicationPortLiveDto> Ports { get; } = [];
    public ObservableCollection<ProbeLiveDto> Probes { get; } = [];
    public ObservableCollection<NozzleLiveDto> Nozzles { get; } = [];
    public ObservableCollection<LiveAnomalyResultDto> AiResults { get; } = [];
    public event EventHandler? TopologyChanged;
    public void Clear() => Dispatch(() => { LastMessageAt = null; LastSimulationTick = null; LastSequence = null; LastSimulationRunId = null; HasSequenceGap = false; ExpectedSequence = null; ReceivedSequence = null; ConnectedStationId = null; Tanks.Clear(); Pumps.Clear(); Controllers.Clear(); Ports.Clear(); Probes.Clear(); Nozzles.Clear(); AiResults.Clear(); _liveChartDataService?.Clear(); TopologyChanged?.Invoke(this, EventArgs.Empty); });
    public void UpdateConnectionState(LiveConnectionState state) => Dispatch(() => ConnectionState = state);
    public void ApplyConnectionReady(ConnectionReadyDto ready) => Dispatch(() => { ConnectedStationId = ready.StationId; LastMessageAt = DateTimeOffset.UtcNow; });
    public void ApplySimulationTick(SimulationTickDto tick) => Dispatch(() => Apply(new LiveMessageParseResult("simulation_tick", tick, null, false)));
    public void ApplyAnomalyEvaluation(AnomalyEvaluationDto evaluation) => Dispatch(() => Apply(new LiveMessageParseResult("anomaly_evaluation", evaluation, null, false)));
    public void ApplyLiveStatus(StationLiveStatusDto status) => Dispatch(() =>
    {
        SelectedStationId = status.StationId;
        ConnectedStationId ??= status.StationId;
        LastMessageAt = DateTimeOffset.UtcNow;
        MergeTopology(status.Controllers, status.Ports, status.Probes, status.Nozzles);
    });
    private void Apply(LiveMessageParseResult result)
    {
        LastMessageAt = DateTimeOffset.UtcNow;
        switch (result.Message)
        {
            case ConnectionReadyDto ready: ConnectedStationId = ready.StationId; break;
            case SimulationTickDto tick:
                if (LastSimulationRunId != tick.SimulationRunId) { LastSimulationRunId = tick.SimulationRunId; LastSequence = null; HasSequenceGap = false; ExpectedSequence = null; ReceivedSequence = null; _liveChartDataService?.ResetForSimulationRun(tick.SimulationRunId); }
                if (LastSequence is int previous)
                {
                    if (tick.Sequence == previous) return;
                    if (tick.Sequence < previous) return;
                    if (tick.Sequence > previous + 1) { HasSequenceGap = true; ExpectedSequence = previous + 1; ReceivedSequence = tick.Sequence; }
                    else { HasSequenceGap = false; ExpectedSequence = null; ReceivedSequence = null; }
                }
                ConnectedStationId = tick.StationId; LastSimulationTick = tick; LastSequence = tick.Sequence;
                foreach (var tank in tick.Tanks)
                {
                    _liveChartDataService?.AddPoint(
                        LiveChartDataService.GetMeasuredTankLevelMetricKey(tank.TankId),
                        tick,
                        (double)tank.MeasuredLevelLiters);
                }
                foreach (var pump in tick.Pumps)
                {
                    _liveChartDataService?.AddPoint(LiveChartDataService.GetPumpMetricKey(pump.PumpId, "flow_rate"), tick, (double)pump.FlowRate);
                    _liveChartDataService?.AddPoint(LiveChartDataService.GetPumpMetricKey(pump.PumpId, "pressure"), tick, (double)pump.Pressure);
                    _liveChartDataService?.AddPoint(LiveChartDataService.GetPumpMetricKey(pump.PumpId, "motor_current"), tick, (double)pump.MotorCurrent);
                    if (pump.Temperature is decimal temperature)
                        _liveChartDataService?.AddPoint(LiveChartDataService.GetPumpMetricKey(pump.PumpId, "temperature"), tick, (double)temperature);
                }
                AiResults.Clear(); foreach (var resultItem in tick.AiResults) AiResults.Add(resultItem);
                Tanks.Clear(); foreach (var tank in tick.Tanks) { tank.AiAnalysis = tick.AiResults.FirstOrDefault(x => string.Equals(x.EntityType, "TANK", StringComparison.OrdinalIgnoreCase) && x.EntityId == tank.TankId); Tanks.Add(tank); }
                Pumps.Clear(); foreach (var pump in tick.Pumps) { pump.AiAnalysis = tick.AiResults.FirstOrDefault(x => string.Equals(x.EntityType, "PUMP", StringComparison.OrdinalIgnoreCase) && x.EntityId == pump.PumpId); Pumps.Add(pump); }
                MergeTopology(tick.Controllers, tick.Ports, tick.Probes, tick.Nozzles);
                break;
            case AnomalyEvaluationDto evaluation:
                AiResults.Clear(); foreach (var resultItem in evaluation.Results) AiResults.Add(resultItem);
                foreach (var resultItem in evaluation.Results)
                {
                    if (string.Equals(resultItem.EntityType, "PUMP", StringComparison.OrdinalIgnoreCase))
                    {
                        var index = Pumps.ToList().FindIndex(x => x.PumpId == resultItem.EntityId);
                        if (index >= 0) { Pumps[index].AiAnalysis = resultItem; Pumps[index] = Pumps[index]; }
                    }
                    else if (string.Equals(resultItem.EntityType, "TANK", StringComparison.OrdinalIgnoreCase))
                    {
                        var index = Tanks.ToList().FindIndex(x => x.TankId == resultItem.EntityId);
                        if (index >= 0) { Tanks[index].AiAnalysis = resultItem; Tanks[index] = Tanks[index]; }
                    }
                }
                break;
        }
    }
    private void MergeTopology(
        IReadOnlyList<ControllerLiveDto> controllers,
        IReadOnlyList<CommunicationPortLiveDto> ports,
        IReadOnlyList<ProbeLiveDto> probes,
        IReadOnlyList<NozzleLiveDto> nozzles)
    {
        MergeById(Controllers, controllers, item => item.Id);
        MergeById(Ports, ports, item => item.Id);
        MergeById(Probes, probes, item => item.Id);
        MergeById(Nozzles, nozzles, item => item.Id);
        TopologyChanged?.Invoke(this, EventArgs.Empty);
    }
    private static void MergeById<T>(
        ObservableCollection<T> target,
        IReadOnlyList<T> incoming,
        Func<T, int> getId)
    {
        var incomingIds = incoming.Select(getId).ToHashSet();
        for (var index = target.Count - 1; index >= 0; index--)
            if (!incomingIds.Contains(getId(target[index]))) target.RemoveAt(index);
        foreach (var item in incoming)
        {
            var index = -1;
            for (var candidateIndex = 0; candidateIndex < target.Count; candidateIndex++)
            {
                if (getId(target[candidateIndex]) == getId(item))
                {
                    index = candidateIndex;
                    break;
                }
            }

            if (index >= 0) target[index] = item;
            else target.Add(item);
        }
    }
    private void Dispatch(Action action)
    {
        var context = _context;
        if (context is null ||
            SynchronizationContext.Current == context ||
            _dispatcher?.CheckAccess() == true)
        {
            action();
            return;
        }

        context.Post(_ => action(), null);
    }
}
