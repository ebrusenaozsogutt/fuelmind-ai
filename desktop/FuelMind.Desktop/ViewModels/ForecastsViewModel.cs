using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Forecasts;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using LiveChartsCore;
using LiveChartsCore.SkiaSharpView;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class ForecastsViewModel : ObservableObject
{
    private readonly IForecastService _forecasts; private readonly IStationService _stations; private readonly AuthState _auth;
    public ForecastsViewModel(IForecastService forecasts, IStationService stations, AuthState auth) { _forecasts = forecasts; _stations = stations; _auth = auth; Series = [new LineSeries<decimal> { Name = "Tahmin", Values = ChartValues, Fill = null, GeometrySize = 6 }, new LineSeries<decimal> { Name = "Alt Sınır", Values = LowerChartValues, Fill = null, GeometrySize = 0 }, new LineSeries<decimal> { Name = "Üst Sınır", Values = UpperChartValues, Fill = null, GeometrySize = 0 }]; XAxes = [new Axis { Labels = Labels }]; YAxes = [new Axis { Name = "Litre", Labeler = x => $"{x:N0} L" }]; RuntimeDiagnostics.Trace("ForecastsViewModel constructor"); }
    public ObservableCollection<StationDto> Stations { get; } = []; public ObservableCollection<FuelTypeDto> FuelTypes { get; } = []; public ObservableCollection<ForecastDto> Forecasts { get; } = []; public ObservableCollection<decimal> ChartValues { get; } = []; public ObservableCollection<decimal> LowerChartValues { get; } = []; public ObservableCollection<decimal> UpperChartValues { get; } = []; public ObservableCollection<string> Labels { get; } = [];
    public ISeries[] Series { get; } public Axis[] XAxes { get; } public Axis[] YAxes { get; }
    [ObservableProperty] private StationDto? _selectedStation; [ObservableProperty] private FuelTypeDto? _selectedFuelType; [ObservableProperty] private ForecastPerformanceDto? _performance; [ObservableProperty] private bool _isLoading; [ObservableProperty] private string? _errorMessage;
    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage); public bool IsEmpty => !IsLoading && Forecasts.Count == 0 && !HasError; public bool HasForecasts => Forecasts.Count > 0; public bool CanGenerate => string.Equals(_auth.CurrentUser?.Role, "ADMIN", StringComparison.OrdinalIgnoreCase); public string ModelDisplay => Performance?.Winner == "baseline" || Performance?.ModelType == "seven_day_moving_average" ? "7 Günlük Hareketli Ortalama" : Performance?.ModelType == "demand_xgboost" ? "XGBoost Talep Tahmin Modeli" : "Model bilgisi yok"; public string ModelSelectionDescription => Performance?.Winner == "xgboost" ? "XGBoost, baseline modele göre daha düşük MAE ürettiği için aktif model olarak kullanılmaktadır." : "Bu model, geçmiş performans karşılaştırmasında en düşük MAE değerini verdiği için aktif olarak kullanılmaktadır."; public decimal AverageConfidence => Forecasts.Count == 0 ? 0 : Forecasts.Average(x => x.ConfidenceScore);
    public async Task LoadAsync(CancellationToken ct = default)
    {
        if (IsLoading) { RuntimeDiagnostics.Trace("ForecastsViewModel LoadAsync skipped: already loading"); return; }
        IsLoading = true; ErrorMessage = null;
        RuntimeDiagnostics.Trace("ForecastsViewModel LoadAsync START");
        try
        {
            if (Stations.Count == 0)
            {
                foreach (var s in await _stations.GetActiveStationsAsync(ct)) Stations.Add(s);
                foreach (var f in await _stations.GetFuelTypesAsync(ct)) FuelTypes.Add(f);
                SelectedStation ??= Stations.FirstOrDefault();
            }
            if (SelectedStation is not null) await LoadDataAsync(ct);
            else RuntimeDiagnostics.Trace("ForecastsViewModel LoadAsync: no active station available");
        }
        catch (Exception ex) { RuntimeDiagnostics.Exception("ForecastsViewModel LoadAsync", ex); ErrorMessage = "Tahmin verileri alınamadı."; }
        finally { IsLoading = false; NotifyState(); TraceState("LoadAsync END"); }
    }
    [RelayCommand] private Task RefreshAsync(CancellationToken ct) => LoadAsync(ct);
    [RelayCommand] private async Task GenerateAsync(CancellationToken ct) { if (!CanGenerate || SelectedStation is null) return; IsLoading = true; ErrorMessage = null; try { await _forecasts.GenerateForecastAsync(SelectedStation.Id, SelectedFuelType?.Id, ct); await LoadDataAsync(ct); ErrorMessage = "Tahmin başarıyla güncellendi."; } catch (Exception) { ErrorMessage = "Tahmin üretilemedi."; } finally { IsLoading = false; NotifyState(); } }
    partial void OnSelectedStationChanged(StationDto? value) { _ = LoadAsync(); } partial void OnSelectedFuelTypeChanged(FuelTypeDto? value) { _ = LoadAsync(); }
    private async Task LoadDataAsync(CancellationToken ct)
    {
        RuntimeDiagnostics.Trace($"ForecastsViewModel GET forecasts/latest station={SelectedStation!.Id} fuel={SelectedFuelType?.Id.ToString() ?? "<all>"}");
        var rows = await _forecasts.GetLatestForecastsAsync(SelectedStation!.Id, SelectedFuelType?.Id, ct);
        if (SelectedFuelType is null && rows.Count > 0)
        {
            var matchingFuel = FuelTypes.FirstOrDefault(fuel => rows.Any(row => row.FuelTypeId == fuel.Id));
            if (matchingFuel is not null)
            {
                SelectedFuelType = matchingFuel;
                rows = rows.Where(row => row.FuelTypeId == matchingFuel.Id).ToArray();
                RuntimeDiagnostics.Trace($"ForecastsViewModel selected forecast-backed fuel={matchingFuel.Id}");
            }
        }
        Performance = await _forecasts.GetPerformanceAsync(ct);
        Forecasts.Clear(); ChartValues.Clear(); LowerChartValues.Clear(); UpperChartValues.Clear(); Labels.Clear();
        foreach (var row in rows.OrderBy(x => x.ForecastDate).Take(7))
        {
            Forecasts.Add(row); ChartValues.Add(row.PredictedDemand); LowerChartValues.Add(row.LowerBound); UpperChartValues.Add(row.UpperBound);
            Labels.Add(row.ForecastDate.ToDateTime(TimeOnly.MinValue).ToString("dd MMM"));
        }
        NotifyState();
    }
    internal void TraceState(string source) => RuntimeDiagnostics.Trace($"ForecastsViewModel {source}; IsLoading={IsLoading}; Error={ErrorMessage ?? "<none>"}; Stations={Stations.Count}; SelectedStation={SelectedStation?.Id.ToString() ?? "<null>"}; FuelTypes={FuelTypes.Count}; SelectedFuel={SelectedFuelType?.Id.ToString() ?? "<null>"}; Forecasts={Forecasts.Count}; PerformanceLoaded={Performance is not null}; AverageConfidence={AverageConfidence}; IsEmpty={IsEmpty}; Series={Series.Length}; XAxes={XAxes.Length}; YAxes={YAxes.Length}");
    private void NotifyState() { OnPropertyChanged(nameof(HasError)); OnPropertyChanged(nameof(IsEmpty)); OnPropertyChanged(nameof(HasForecasts)); OnPropertyChanged(nameof(AverageConfidence)); OnPropertyChanged(nameof(ModelDisplay)); OnPropertyChanged(nameof(ModelSelectionDescription)); }
}
