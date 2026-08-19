using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Reports;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;
using Microsoft.Win32;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class ReportsViewModel(IReportService reportService, IStationService stationService) : ObservableObject
{
    public ObservableCollection<ReportRowDto> Rows { get; } = [];
    public ObservableCollection<StationDto> Stations { get; } = [];
    public IReadOnlyList<ReportTypeItem> ReportTypes { get; } = [new("end-of-day", "Gün Sonu"), new("sales", "Satış"), new("attendants", "Pompacı / Vardiya"), new("deliveries", "Tank Dolum"), new("tank-measurements", "Tank Ölçüm"), new("price-changes", "Ürün Fiyat Değişimi"), new("faults", "Arıza"), new("customer-sales", "Müşteri / Araç Satış")];
    [ObservableProperty] private ReportTypeItem? _selectedReportType;
    [ObservableProperty] private StationDto? _selectedStation;
    [ObservableProperty] private DateTime? _dateFrom = DateTime.Today;
    [ObservableProperty] private DateTime? _dateTo = DateTime.Today;
    [ObservableProperty] private string? _plate;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;
    public bool IsEmpty => !IsLoading && Rows.Count == 0 && string.IsNullOrEmpty(ErrorMessage);
    public async Task LoadAsync() { if (SelectedReportType is null) SelectedReportType = ReportTypes[0]; try { Stations.Clear(); foreach (var station in await stationService.GetActiveStationsAsync()) Stations.Add(station); } catch (Exception ex) { ErrorMessage = ex.Message; } }
    [RelayCommand] private async Task RunAsync() { if (SelectedReportType is null) return; await Execute(async () => Replace(await reportService.GetAsync(SelectedReportType.Key, Query()))); }
    [RelayCommand] private async Task ExportPdfAsync() => await ExportAsync("pdf");
    [RelayCommand] private async Task ExportCsvAsync() => await ExportAsync("csv");
    [RelayCommand] private void ClearFilters() { SelectedStation = null; DateFrom = DateTime.Today; DateTo = DateTime.Today; Plate = null; }
    private async Task ExportAsync(string format) { if (SelectedReportType is null) return; await Execute(async () => { var bytes = await reportService.ExportAsync(SelectedReportType.Key, format, Query()); var dialog = new SaveFileDialog { Filter = format == "pdf" ? "PDF (*.pdf)|*.pdf" : "CSV (*.csv)|*.csv", FileName = $"fuelmind_{SelectedReportType.Key}_{DateTime.Today:yyyy-MM-dd}.{format}" }; if (dialog.ShowDialog() == true) await System.IO.File.WriteAllBytesAsync(dialog.FileName, bytes); }); }
    private string Query() { var values = new List<string>(); if (DateFrom is { } from) values.Add($"date_from={from:yyyy-MM-dd}"); if (DateTo is { } to) values.Add($"date_to={to:yyyy-MM-dd}"); if (SelectedStation is not null) values.Add($"station_id={SelectedStation.Id}"); if (!string.IsNullOrWhiteSpace(Plate)) values.Add($"plate={Uri.EscapeDataString(Plate)}"); return values.Count == 0 ? "" : "?" + string.Join("&", values); }
    private async Task Execute(Func<Task> action) { if (IsLoading) return; IsLoading = true; ErrorMessage = null; try { await action(); } catch (Exception ex) { ErrorMessage = ex is ApiException api ? api.Message : ex.Message; } finally { IsLoading = false; OnPropertyChanged(nameof(IsEmpty)); } }
    private void Replace(IEnumerable<ReportRowDto> source) { Rows.Clear(); foreach (var row in source) Rows.Add(row); }
}
public sealed record ReportTypeItem(string Key, string Name);
