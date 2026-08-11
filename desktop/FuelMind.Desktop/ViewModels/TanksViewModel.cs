using System.Collections.Specialized;
using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Collections;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using LiveChartsCore;
using LiveChartsCore.Kernel;
using LiveChartsCore.SkiaSharpView;
using LiveChartsCore.SkiaSharpView.WPF;

namespace FuelMind.Desktop.ViewModels;

/// <summary>
/// Presents the shared, UI-safe live tank collection without taking a snapshot.
/// </summary>
public sealed partial class TanksViewModel : ObservableObject
{
    private readonly LiveDataStore _liveDataStore;
    private readonly LiveChartDataService _liveChartDataService;
    private readonly LineSeries<LiveChartPoint> _measuredLevelSeries;
    private ReadOnlyObservableCollection<LiveChartPoint>? _selectedTankHistory;
    private INotifyCollectionChanged? _selectedTankHistoryNotifications;

    private readonly DetailNavigationService _detailNavigation;
    public TanksViewModel(LiveDataStore liveDataStore, LiveChartDataService liveChartDataService, DetailNavigationService detailNavigation)
    {
        _liveDataStore = liveDataStore;
        _liveChartDataService = liveChartDataService;
        _detailNavigation = detailNavigation;
        _liveDataStore.Tanks.CollectionChanged += OnTanksCollectionChanged;

        _measuredLevelSeries = new LineSeries<LiveChartPoint>
        {
            Name = "Measured level",
            Values = [],
            GeometrySize = 8,
            LineSmoothness = 0,
            Fill = null,
            AnimationsSpeed = TimeSpan.Zero,
            Mapping = (point, _) => new Coordinate(point.ChartTimestamp, point.ChartValue),
        };
        Series = [_measuredLevelSeries];
        XAxes =
        [
            new Axis
            {
                Name = "Simulation time",
                Labeler = value => DateTime.FromOADate(value).ToString("HH:mm:ss"),
                LabelsRotation = 15,
                MinStep = TimeSpan.FromSeconds(1).TotalDays,
            },
        ];
        YAxes =
        [
            new Axis
            {
                Name = "Liters",
                Labeler = value => $"{value:N0} L",
            },
        ];

        if (Tanks.FirstOrDefault() is { } firstTank)
        {
            SelectedTankId = firstTank.TankId;
        }
    }

    public ObservableCollection<TankLiveDataDto> Tanks => _liveDataStore.Tanks;

    public int TankCount => Tanks.Count;
    public ISeries[] Series { get; }
    public Axis[] XAxes { get; }
    public Axis[] YAxes { get; }
    public int SelectedChartPointCount => _selectedTankHistory?.Count ?? 0;

    [ObservableProperty]
    private int? _selectedTankId;

    public TankLiveDataDto? SelectedTank => SelectedTankId is int tankId
        ? Tanks.FirstOrDefault(tank => tank.TankId == tankId)
        : null;

    public string SelectedTankDisplay => SelectedTank is { } tank
        ? $"{tank.Code ?? "Tank"} (ID: {tank.TankId})"
        : "--";

    public decimal? CurrentMeasuredLevel => SelectedTank?.MeasuredLevelLiters;
    public decimal? CurrentCapacity => SelectedTank?.CapacityLiters;
    public double? CurrentFillPercentage => SelectedTank is { CapacityLiters: > 0 } tank
        ? Math.Clamp((double)(tank.MeasuredLevelLiters / tank.CapacityLiters * 100m), 0d, 100d)
        : null;

    private void OnTanksCollectionChanged(object? sender, NotifyCollectionChangedEventArgs eventArgs)
    {
        OnPropertyChanged(nameof(TankCount));
        if (SelectedTankId is null && Tanks.FirstOrDefault() is { } firstTank)
        {
            SelectedTankId = firstTank.TankId;
        }

        NotifySelectedTankState();
    }

    partial void OnSelectedTankIdChanged(int? value)
    {
        if (_selectedTankHistoryNotifications is not null)
        {
            _selectedTankHistoryNotifications.CollectionChanged -= OnSelectedTankHistoryChanged;
        }

        _selectedTankHistory = value is int tankId
            ? _liveChartDataService.GetSeries(LiveChartDataService.GetMeasuredTankLevelMetricKey(tankId))
            : null;
        _measuredLevelSeries.Values = _selectedTankHistory is null ? [] : _selectedTankHistory;
        _selectedTankHistoryNotifications = _selectedTankHistory as INotifyCollectionChanged;
        if (_selectedTankHistoryNotifications is not null)
        {
            _selectedTankHistoryNotifications.CollectionChanged += OnSelectedTankHistoryChanged;
        }

        OnPropertyChanged(nameof(Series));
        OnPropertyChanged(nameof(SelectedChartPointCount));
        NotifySelectedTankState();
    }

    private void OnSelectedTankHistoryChanged(object? sender, NotifyCollectionChangedEventArgs eventArgs)
    {
        OnPropertyChanged(nameof(SelectedChartPointCount));
        OnPropertyChanged(nameof(Series));
    }

    private void NotifySelectedTankState()
    {
        OnPropertyChanged(nameof(SelectedTank));
        OnPropertyChanged(nameof(SelectedTankDisplay));
        OnPropertyChanged(nameof(CurrentMeasuredLevel));
        OnPropertyChanged(nameof(CurrentCapacity));
        OnPropertyChanged(nameof(CurrentFillPercentage));
    }
    [RelayCommand] private void OpenDetail(int tankId) => _detailNavigation.ShowTank(tankId);
}
