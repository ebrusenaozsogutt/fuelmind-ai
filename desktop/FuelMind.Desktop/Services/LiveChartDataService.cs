using System.Collections.ObjectModel;
using System.Windows.Threading;
using FuelMind.Desktop.Collections;
using FuelMind.Desktop.Configuration;
using FuelMind.Desktop.Dtos.Live;
using Microsoft.Extensions.Options;

namespace FuelMind.Desktop.Services;

/// <summary>
/// Owns bounded, UI-safe point sources for future LiveCharts2 series. It is
/// intentionally metric-agnostic: callers choose a metric key and pass a value
/// taken from a real simulation tick.
/// </summary>
public sealed class LiveChartDataService
{
    private readonly object _sync = new();
    private readonly Dispatcher _dispatcher;
    private readonly int _maxPoints;
    private readonly Dictionary<string, ChartSeriesState> _series = new(StringComparer.Ordinal);
    private int? _simulationRunId;

    public LiveChartDataService(Dispatcher dispatcher, IOptions<LiveChartsSettings> settings)
    {
        _dispatcher = dispatcher;
        _maxPoints = settings.Value.MaxPoints;
    }

    public int MaxPoints => _maxPoints;

    /// <summary>Builds a stable, per-tank measured-level metric key without hard-coded IDs.</summary>
    public static string GetMeasuredTankLevelMetricKey(int tankId) => $"tank:{tankId}:measured_level_liters";

    /// <summary>Builds a stable, per-pump metric key without hard-coded IDs.</summary>
    public static string GetPumpMetricKey(int pumpId, string metricName)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(metricName);
        return $"pump:{pumpId}:{metricName}";
    }

    /// <summary>Gets the bounded collection that can be assigned to a LiveCharts2 series.</summary>
    public ReadOnlyObservableCollection<LiveChartPoint> GetSeries(string metricKey)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(metricKey);
        lock (_sync)
        {
            return GetOrCreateSeries(metricKey).Points;
        }
    }

    /// <summary>Adds one real tick value to the named metric's bounded history.</summary>
    public void AddPoint(string metricKey, SimulationTickDto tick, double value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(metricKey);
        ArgumentNullException.ThrowIfNull(tick);

        ChartSeriesState series;
        IReadOnlyList<LiveChartPoint> snapshot;
        long revision;
        lock (_sync)
        {
            ResetForSimulationRunCore(tick.SimulationRunId);
            series = GetOrCreateSeries(metricKey);
            series.Buffer.Add(new LiveChartPoint(tick.SimulationTime, value));
            snapshot = series.Buffer.Snapshot();
            revision = ++series.Revision;
        }

        PublishSnapshot(series, snapshot, revision);
    }

    /// <summary>Adds persisted context before the next live tick arrives.</summary>
    public void AddHistoricalPoint(string metricKey, DateTimeOffset timestamp, double value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(metricKey);
        ChartSeriesState series;
        IReadOnlyList<LiveChartPoint> snapshot;
        long revision;
        lock (_sync)
        {
            series = GetOrCreateSeries(metricKey);
            series.Buffer.Add(new LiveChartPoint(timestamp, value));
            snapshot = series.Buffer.Snapshot();
            revision = ++series.Revision;
        }
        PublishSnapshot(series, snapshot, revision);
    }

    /// <summary>Clears all metric buffers when the simulation run changes.</summary>
    public void ResetForSimulationRun(int simulationRunId)
    {
        lock (_sync)
        {
            ResetForSimulationRunCore(simulationRunId);
        }
    }

    /// <summary>Clears all bounded histories, including their UI-facing sources.</summary>
    public void Clear()
    {
        List<(ChartSeriesState Series, long Revision)> updates;
        lock (_sync)
        {
            _simulationRunId = null;
            updates = [];
            foreach (var series in _series.Values)
            {
                series.Buffer.Clear();
                updates.Add((series, ++series.Revision));
            }
        }

        foreach (var (series, revision) in updates)
        {
            PublishSnapshot(series, [], revision);
        }
    }

    private void ResetForSimulationRunCore(int simulationRunId)
    {
        if (_simulationRunId == simulationRunId) return;

        _simulationRunId = simulationRunId;
        foreach (var series in _series.Values)
        {
            series.Buffer.Clear();
            var revision = ++series.Revision;
            PublishSnapshot(series, [], revision);
        }
    }

    private ChartSeriesState GetOrCreateSeries(string metricKey)
    {
        if (_series.TryGetValue(metricKey, out var series)) return series;

        series = new ChartSeriesState(_maxPoints);
        _series.Add(metricKey, series);
        return series;
    }

    private void PublishSnapshot(ChartSeriesState series, IReadOnlyList<LiveChartPoint> snapshot, long revision)
    {
        lock (_sync)
        {
            series.PendingSnapshot = snapshot;
            series.PendingRevision = revision;
            if (series.IsPublicationQueued) return;
            series.IsPublicationQueued = true;
        }

        _dispatcher.BeginInvoke(() => ApplyLatestSnapshot(series));
    }

    private void ApplyLatestSnapshot(ChartSeriesState series)
    {
        IReadOnlyList<LiveChartPoint> snapshot;
        long revision;
        lock (_sync)
        {
            snapshot = series.PendingSnapshot ?? [];
            revision = series.PendingRevision;
            series.PendingSnapshot = null;
            series.IsPublicationQueued = false;
        }

        if (revision < series.AppliedRevision) return;
        series.AppliedRevision = revision;
        series.MutablePoints.Clear();
        foreach (var point in snapshot) series.MutablePoints.Add(point);
    }

    private sealed class ChartSeriesState
    {
        public ChartSeriesState(int maxPoints)
        {
            Buffer = new RingBuffer<LiveChartPoint>(maxPoints);
            Points = new ReadOnlyObservableCollection<LiveChartPoint>(MutablePoints);
        }

        public RingBuffer<LiveChartPoint> Buffer { get; }
        public ObservableCollection<LiveChartPoint> MutablePoints { get; } = [];
        public ReadOnlyObservableCollection<LiveChartPoint> Points { get; }
        public long Revision { get; set; }
        public long AppliedRevision { get; set; }
        public IReadOnlyList<LiveChartPoint>? PendingSnapshot { get; set; }
        public long PendingRevision { get; set; }
        public bool IsPublicationQueued { get; set; }
    }
}
