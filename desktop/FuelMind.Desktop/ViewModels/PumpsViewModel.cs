using System.Collections.ObjectModel;
using System.Collections.Specialized;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Collections;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using LiveChartsCore;
using LiveChartsCore.Kernel;
using LiveChartsCore.SkiaSharpView;
using LiveChartsCore.SkiaSharpView.Painting;
using LiveChartsCore.SkiaSharpView.WPF;
using SkiaSharp;

namespace FuelMind.Desktop.ViewModels;

/// <summary>
/// Presents the shared, UI-safe live pump collection without taking a snapshot.
/// </summary>
public sealed partial class PumpsViewModel : ObservableObject
{
    private readonly DetailNavigationService _detailNavigation;
    private readonly LiveDataStore _liveDataStore;
    private readonly LiveChartDataService _liveChartDataService;
    private readonly ApiClient _apiClient;
    private readonly HashSet<int> _historyLoadedPumpIds = [];
    private readonly LineSeries<LiveChartPoint> _selectedMetricSeries;
    private ReadOnlyObservableCollection<LiveChartPoint>? _selectedPumpHistory;
    private INotifyCollectionChanged? _selectedPumpHistoryNotifications;

    public PumpsViewModel(LiveDataStore liveDataStore, LiveChartDataService liveChartDataService, DetailNavigationService detailNavigation, ApiClient apiClient)
    {
        _liveDataStore = liveDataStore;
        _liveChartDataService = liveChartDataService;
        _detailNavigation = detailNavigation;
        _apiClient = apiClient;
        _liveDataStore.Pumps.CollectionChanged += OnPumpsCollectionChanged;

        _selectedMetricSeries = new LineSeries<LiveChartPoint>
        {
            Name = "Debi",
            Values = [],
            GeometrySize = 0,
            LineSmoothness = 0,
            Fill = null,
            Stroke = new SolidColorPaint(SKColors.DeepSkyBlue) { StrokeThickness = 3 },
            AnimationsSpeed = TimeSpan.Zero,
            Mapping = (point, _) => new Coordinate(point.ChartTimestamp, point.ChartValue),
        };
        Series = [_selectedMetricSeries];
        XAxes =
        [
            new Axis
            {
                Name = "Simülasyon zamanı",
                Labeler = value => DateTime.FromOADate(value).ToString("HH:mm:ss"),
                LabelsRotation = 15,
                MinStep = TimeSpan.FromSeconds(1).TotalDays,
                LabelsPaint = new SolidColorPaint(new SKColor(184, 199, 209)),
                NamePaint = new SolidColorPaint(new SKColor(244, 247, 250)),
            },
        ];
        YAxes =
        [
            new Axis
            {
                Name = "Debi",
                Labeler = value => value.ToString("N1"),
                MinLimit = 0,
                LabelsPaint = new SolidColorPaint(new SKColor(184, 199, 209)),
                NamePaint = new SolidColorPaint(new SKColor(244, 247, 250)),
            },
        ];
    }

    public ObservableCollection<PumpLiveDataDto> Pumps => _liveDataStore.Pumps;

    public int PumpCount => Pumps.Count;
    public ISeries[] Series { get; }
    public Axis[] XAxes { get; }
    public Axis[] YAxes { get; }
    public int SelectedChartPointCount => _selectedPumpHistory?.Count ?? 0;
    public IReadOnlyList<PumpChartMetricOption> MetricOptions { get; } =
    [
        new(PumpChartMetric.FlowRate, "Debi"),
        new(PumpChartMetric.Pressure, "Basınç"),
        new(PumpChartMetric.MotorCurrent, "Motor akımı"),
        new(PumpChartMetric.Temperature, "Pompa sıcaklığı"),
    ];

    [ObservableProperty]
    private int? _selectedPumpId;

    [ObservableProperty]
    private PumpChartMetric _selectedMetric = PumpChartMetric.FlowRate;

    public PumpLiveDataDto? SelectedPump => SelectedPumpId is int pumpId
        ? Pumps.FirstOrDefault(pump => pump.PumpId == pumpId)
        : null;

    public string SelectedPumpDisplay => SelectedPump is { } pump
        ? $"Pompa ID: {pump.PumpId} (Tank ID: {pump.TankId})"
        : "Pompa seçilmedi";

    public string SelectedMetricTitle => GetMetricTitle(SelectedMetric);
    public decimal? CurrentMetricValue => SelectedPump is null ? null : SelectedMetric switch
    {
        PumpChartMetric.FlowRate => SelectedPump.FlowRate,
        PumpChartMetric.Pressure => SelectedPump.Pressure,
        PumpChartMetric.MotorCurrent => SelectedPump.MotorCurrent,
        PumpChartMetric.Temperature => SelectedPump.Temperature,
        _ => null,
    };

    private void OnPumpsCollectionChanged(object? sender, NotifyCollectionChangedEventArgs eventArgs)
    {
        OnPropertyChanged(nameof(PumpCount));
        if (SelectedPumpId is null && Pumps.FirstOrDefault() is { } firstPump)
        {
            SelectedPumpId = firstPump.PumpId;
        }

        NotifySelectedPumpState();
    }

    partial void OnSelectedPumpIdChanged(int? value)
    {
        UpdateSelectedSeries();
        if (value is int pumpId) _ = LoadHistoryAsync(pumpId);
    }

    partial void OnSelectedMetricChanged(PumpChartMetric value) => UpdateSelectedSeries();

    private void UpdateSelectedSeries()
    {
        if (_selectedPumpHistoryNotifications is not null)
            _selectedPumpHistoryNotifications.CollectionChanged -= OnSelectedPumpHistoryChanged;

        _selectedMetricSeries.Name = SelectedMetricTitle;
        _selectedPumpHistory = SelectedPumpId is int pumpId
            ? _liveChartDataService.GetSeries(LiveChartDataService.GetPumpMetricKey(pumpId, GetMetricKey(SelectedMetric))) : null;
        _selectedMetricSeries.Values = _selectedPumpHistory is null ? [] : _selectedPumpHistory;
        _selectedPumpHistoryNotifications = _selectedPumpHistory as INotifyCollectionChanged;
        if (_selectedPumpHistoryNotifications is not null)
            _selectedPumpHistoryNotifications.CollectionChanged += OnSelectedPumpHistoryChanged;

        YAxes[0].Name = GetMetricAxisTitle(SelectedMetric);
        OnPropertyChanged(nameof(Series));
        OnPropertyChanged(nameof(SelectedChartPointCount));
        NotifySelectedPumpState();
    }

    private void OnSelectedPumpHistoryChanged(object? sender, NotifyCollectionChangedEventArgs eventArgs)
    {
        OnPropertyChanged(nameof(SelectedChartPointCount));
        OnPropertyChanged(nameof(Series));
    }

    private void NotifySelectedPumpState()
    {
        OnPropertyChanged(nameof(SelectedPump));
        OnPropertyChanged(nameof(SelectedPumpDisplay));
        OnPropertyChanged(nameof(SelectedMetricTitle));
        OnPropertyChanged(nameof(CurrentMetricValue));
    }

    private static string GetMetricKey(PumpChartMetric metric) => metric switch
    {
        PumpChartMetric.FlowRate => "flow_rate",
        PumpChartMetric.Pressure => "pressure",
        PumpChartMetric.MotorCurrent => "motor_current",
        PumpChartMetric.Temperature => "temperature",
        _ => throw new ArgumentOutOfRangeException(nameof(metric), metric, null),
    };

    private static string GetMetricTitle(PumpChartMetric metric) => metric switch
    {
        PumpChartMetric.FlowRate => "Debi",
        PumpChartMetric.Pressure => "Basınç",
        PumpChartMetric.MotorCurrent => "Motor akımı",
        PumpChartMetric.Temperature => "Pompa sıcaklığı",
        _ => throw new ArgumentOutOfRangeException(nameof(metric), metric, null),
    };

    private static string GetMetricAxisTitle(PumpChartMetric metric) => metric switch
    {
        PumpChartMetric.FlowRate => "Debi (L/dk)",
        PumpChartMetric.Pressure => "Basınç (bar)",
        PumpChartMetric.MotorCurrent => "Motor akımı (A)",
        PumpChartMetric.Temperature => "Pompa sıcaklığı (°C)",
        _ => throw new ArgumentOutOfRangeException(nameof(metric), metric, null),
    };

    private async Task LoadHistoryAsync(int pumpId)
    {
        if (!_historyLoadedPumpIds.Add(pumpId)) return;
        try
        {
            var readings = await _apiClient.GetAsync<IReadOnlyList<SensorHistoryDto>>($"pumps/{pumpId}/sensor-history?limit=600");
            foreach (var reading in readings)
            {
                AddHistory(pumpId, "flow_rate", reading.ReadingTimestamp, reading.FlowRate);
                AddHistory(pumpId, "pressure", reading.ReadingTimestamp, reading.Pressure);
                AddHistory(pumpId, "motor_current", reading.ReadingTimestamp, reading.MotorCurrent);
                AddHistory(pumpId, "temperature", reading.ReadingTimestamp, reading.PumpTemperature);
            }
            if (SelectedPumpId == pumpId) UpdateSelectedSeries();
        }
        catch (Exception)
        {
            // The live chart remains available even when retained history is unavailable.
            _historyLoadedPumpIds.Remove(pumpId);
        }
    }

    private void AddHistory(int pumpId, string metric, DateTimeOffset timestamp, decimal? value)
    {
        if (value is decimal measurement)
            _liveChartDataService.AddHistoricalPoint(LiveChartDataService.GetPumpMetricKey(pumpId, metric), timestamp, (double)measurement);
    }
    [RelayCommand] private void SelectPump(int pumpId) => SelectedPumpId = pumpId;
    [RelayCommand] private void OpenDetail(int pumpId) => _detailNavigation.ShowPump(pumpId);
}

public enum PumpChartMetric { FlowRate, Pressure, MotorCurrent, Temperature }

public sealed record PumpChartMetricOption(PumpChartMetric Metric, string DisplayName);
