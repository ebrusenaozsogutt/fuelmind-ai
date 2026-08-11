using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.State;

public sealed partial class LiveDataStore : ObservableObject
{
    private readonly LiveChartDataService? _liveChartDataService;
    private readonly SynchronizationContext? _context = SynchronizationContext.Current;
    public LiveDataStore(LiveWebSocketService service)
    {
        service.ConnectionStateChanged += (_, state) => Dispatch(() => ConnectionState = state);
        service.MessageReceived += (_, result) => Dispatch(() => Apply(result));
    }
    public LiveDataStore(System.Windows.Threading.Dispatcher dispatcher, LiveChartDataService? liveChartDataService = null)
    {
        _context = new System.Windows.Threading.DispatcherSynchronizationContext(dispatcher);
        _liveChartDataService = liveChartDataService;
    }
    [ObservableProperty] private LiveConnectionState _connectionState = LiveConnectionState.Disconnected;
    [ObservableProperty] private int _selectedStationId = 1;
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
    public void Clear() => Dispatch(() => { LastMessageAt = null; LastSimulationTick = null; LastSequence = null; LastSimulationRunId = null; HasSequenceGap = false; ExpectedSequence = null; ReceivedSequence = null; ConnectedStationId = null; Tanks.Clear(); Pumps.Clear(); _liveChartDataService?.Clear(); });
    public void UpdateConnectionState(LiveConnectionState state) => Dispatch(() => ConnectionState = state);
    public void ApplyConnectionReady(ConnectionReadyDto ready) => Dispatch(() => { ConnectedStationId = ready.StationId; LastMessageAt = DateTimeOffset.UtcNow; });
    public void ApplySimulationTick(SimulationTickDto tick) => Dispatch(() => Apply(new LiveMessageParseResult("simulation_tick", tick, null, false)));
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
                Tanks.Clear(); foreach (var tank in tick.Tanks) Tanks.Add(tank);
                Pumps.Clear(); foreach (var pump in tick.Pumps) Pumps.Add(pump);
                break;
        }
    }
    private void Dispatch(Action action) { if (_context is null || SynchronizationContext.Current == _context) action(); else _context.Post(_ => action(), null); }
}
