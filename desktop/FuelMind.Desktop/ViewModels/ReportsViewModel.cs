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
    private static readonly IReadOnlyDictionary<string, IReadOnlyList<ReportColumnDefinition>> ColumnSets =
        new Dictionary<string, IReadOnlyList<ReportColumnDefinition>>(StringComparer.OrdinalIgnoreCase)
        {
            ["end-of-day"] = [new("transaction_count", "İşlem", .7), new("total_liters", "Toplam Litre", 1), new("total_amount", "Toplam Tutar", 1), new("by_fuel_type", "Ürün Kırılımı", 1.6), new("by_pump", "Pompa Kırılımı", 1.4), new("by_customer", "Müşteri Kırılımı", 1.5), new("by_payment_type", "Ödeme Kırılımı", 1.3)],
            ["sales"] = [new("timestamp", "Tarih", 1.05), new("station", "İstasyon", 1), new("pump", "Pompa", .75), new("nozzle", "Tabanca", .8), new("attendant", "Pompacı", 1), new("shift", "Vardiya", .9), new("fuel_type", "Ürün", .8), new("liters", "Litre", .7), new("unit_price", "Birim Fiyat", .85), new("total_amount", "Tutar", .85), new("customer", "Müşteri", 1), new("plate", "Plaka", .8), new("card", "Kart", .8), new("sale_status", "Durum", .8)],
            ["attendants"] = [new("attendant_name", "Pompacı", 1.4), new("shift_name", "Vardiya", 1.2), new("transaction_count", "Tamamlanan İşlem", 1), new("total_liters", "Toplam Litre", 1), new("total_amount", "Toplam Tutar", 1)],
            ["deliveries"] = [new("timestamp", "Tarih", 1), new("station", "İstasyon", 1), new("tank", "Tank", .85), new("fuel_type", "Ürün", .8), new("level_before", "Önceki Seviye", 1), new("quantity_liters", "Dolum Litresi", 1), new("level_after", "Sonraki Seviye", 1), new("supplier", "Tedarikçi", 1), new("source", "Kaynak", .8), new("status", "Durum", .75)],
            ["tank-measurements"] = [new("timestamp", "Tarih", 1), new("station", "İstasyon", 1), new("tank", "Tank", .8), new("probe", "Prob", .8), new("fuel_height_mm", "Yakıt Yüksekliği", 1), new("fuel_volume_liters", "Yakıt Litresi", 1), new("water_height_mm", "Su Yüksekliği", 1), new("temperature_celsius", "Sıcaklık", .8), new("quality_score", "Kalite", .7), new("source", "Kaynak", .8), new("probe_status", "Prob Durumu", .9)],
            ["price-changes"] = [new("timestamp", "Tarih", 1), new("station", "İstasyon", 1), new("fuel_type", "Ürün", 1), new("old_price", "Eski Fiyat", 1), new("new_price", "Yeni Fiyat", 1), new("changed_by", "Değiştiren", 1)],
            ["faults"] = [new("detected_at", "Tespit", 1), new("station", "İstasyon", 1), new("target_type", "Cihaz Tipi", .85), new("target_id", "Cihaz ID", .7), new("fault_type", "Arıza Tipi", .9), new("fault_code", "Arıza Kodu", 1.1), new("status", "Durum", .8), new("resolved_at", "Çözüm Zamanı", 1), new("resolved_by", "Çözen", .9), new("resolution_note", "Çözüm Notu", 1.5)],
            ["customer-sales"] = [new("customer", "Müşteri", 1.4), new("plate", "Plaka", 1), new("card", "Kart", 1), new("transaction_count", "İşlem", .8), new("total_liters", "Toplam Litre", 1), new("total_amount", "Toplam Tutar", 1)],
        };

    public ObservableCollection<ReportRowDto> Rows { get; } = [];
    public ObservableCollection<ReportColumnDefinition> Columns { get; } = [];
    public ObservableCollection<StationDto> Stations { get; } = [];
    public IReadOnlyList<ReportTypeItem> ReportTypes { get; } = [new("end-of-day", "Gün Sonu"), new("sales", "Satış"), new("attendants", "Pompacı / Vardiya"), new("deliveries", "Tank Dolum"), new("tank-measurements", "Tank Ölçüm"), new("price-changes", "Ürün Fiyat Değişimi"), new("faults", "Arıza"), new("customer-sales", "Müşteri / Araç Satış")];

    [ObservableProperty] private ReportTypeItem? _selectedReportType;
    [ObservableProperty] private StationDto? _selectedStation;
    [ObservableProperty] private DateTime? _dateFrom;
    [ObservableProperty] private DateTime? _dateTo;
    [ObservableProperty] private string? _timeFrom;
    [ObservableProperty] private string? _timeTo;
    [ObservableProperty] private string? _pumpId;
    [ObservableProperty] private string? _nozzleId;
    [ObservableProperty] private string? _fuelTypeId;
    [ObservableProperty] private string? _customerId;
    [ObservableProperty] private string? _vehicleId;
    [ObservableProperty] private string? _plate;
    [ObservableProperty] private string? _attendantId;
    [ObservableProperty] private string? _shiftId;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;

    public bool IsEmpty => !IsLoading && Rows.Count == 0 && string.IsNullOrEmpty(ErrorMessage);
    public string EmptyStateMessage => SelectedReportType is null ? "Rapor türü seçin." : $"{SelectedReportType.Name} için seçili filtrelerde kayıt bulunamadı.";
    public bool ShowSalesFilters => SelectedReportType?.Key is "sales" or "end-of-day" or "attendants" or "customer-sales";
    public bool ShowEquipmentFilters => SelectedReportType?.Key is "sales" or "deliveries" or "tank-measurements";
    public bool ShowCommercialFilters => SelectedReportType?.Key is "sales" or "end-of-day" or "customer-sales";
    public bool ShowOperationsFilters => SelectedReportType?.Key is "sales" or "end-of-day" or "attendants" or "customer-sales";

    public async Task LoadAsync()
    {
        if (SelectedReportType is null) SelectedReportType = ReportTypes[0];
        await Execute(async () =>
        {
            Replace(Stations, await stationService.GetActiveStationsAsync());
            ConfigureColumns();
        });
    }

    [RelayCommand] private async Task RunAsync()
    {
        if (SelectedReportType is null) return;
        await Execute(async () => Replace(Rows, await reportService.GetAsync(SelectedReportType.Key, Query())));
    }

    [RelayCommand] private Task ExportPdfAsync() => ExportAsync("pdf");
    [RelayCommand] private Task ExportCsvAsync() => ExportAsync("csv");
    [RelayCommand] private void ClearFilters() => ResetFilters();

    partial void OnSelectedReportTypeChanged(ReportTypeItem? value)
    {
        ResetFilters();
        ConfigureColumns();
        Rows.Clear();
        OnPropertyChanged(nameof(IsEmpty));
        OnPropertyChanged(nameof(EmptyStateMessage));
        OnPropertyChanged(nameof(ShowSalesFilters));
        OnPropertyChanged(nameof(ShowEquipmentFilters));
        OnPropertyChanged(nameof(ShowCommercialFilters));
        OnPropertyChanged(nameof(ShowOperationsFilters));
    }

    private async Task ExportAsync(string format)
    {
        if (SelectedReportType is null) return;
        await Execute(async () =>
        {
            var bytes = await reportService.ExportAsync(SelectedReportType.Key, format, Query());
            var dialog = new SaveFileDialog
            {
                Filter = format == "pdf" ? "PDF (*.pdf)|*.pdf" : "CSV (*.csv)|*.csv",
                DefaultExt = $".{format}",
                AddExtension = true,
                FileName = $"fuelmind_{SelectedReportType.Key}_{DateTime.Today:yyyy-MM-dd}.{format}",
            };
            if (dialog.ShowDialog() == true) await System.IO.File.WriteAllBytesAsync(dialog.FileName, bytes);
        });
    }

    private string Query()
    {
        if (DateFrom is { } from && DateTo is { } to && to.Date < from.Date) throw new InvalidOperationException("Bitiş tarihi başlangıç tarihinden önce olamaz.");
        var values = new List<string>();
        AddDate("date_from", DateFrom); AddDate("date_to", DateTo);
        AddTime("time_from", TimeFrom); AddTime("time_to", TimeTo);
        if (SelectedStation is not null) Add("station_id", SelectedStation.Id.ToString());
        if (ShowEquipmentFilters) { AddPositive("pump_id", PumpId, "Pompa ID"); AddPositive("nozzle_id", NozzleId, "Tabanca ID"); AddPositive("fuel_type_id", FuelTypeId, "Yakıt türü ID"); }
        if (ShowCommercialFilters) { AddPositive("customer_id", CustomerId, "Müşteri ID"); AddPositive("vehicle_id", VehicleId, "Araç ID"); Add("plate", Plate); }
        if (ShowOperationsFilters) { AddPositive("attendant_id", AttendantId, "Pompacı ID"); AddPositive("shift_id", ShiftId, "Vardiya ID"); }
        return values.Count == 0 ? "" : "?" + string.Join("&", values);

        void AddDate(string key, DateTime? value) { if (value is { } date) Add(key, date.ToString("yyyy-MM-dd")); }
        void AddTime(string key, string? value)
        {
            if (string.IsNullOrWhiteSpace(value)) return;
            if (!TimeOnly.TryParse(value, out var time)) throw new InvalidOperationException($"{(key == "time_from" ? "Başlangıç" : "Bitiş")} saati HH:mm biçiminde olmalıdır.");
            Add(key, time.ToString("HH:mm"));
        }
        void AddPositive(string key, string? value, string label)
        {
            if (string.IsNullOrWhiteSpace(value)) return;
            if (!int.TryParse(value, out var id) || id <= 0) throw new InvalidOperationException($"{label} pozitif bir sayı olmalıdır.");
            Add(key, id.ToString());
        }
        void Add(string key, string? value) { if (!string.IsNullOrWhiteSpace(value)) values.Add($"{key}={Uri.EscapeDataString(value.Trim())}"); }
    }

    private void ResetFilters()
    {
        SelectedStation = null; DateFrom = DateTo = null; TimeFrom = TimeTo = null; PumpId = NozzleId = FuelTypeId = null;
        CustomerId = VehicleId = Plate = AttendantId = ShiftId = null;
    }

    private void ConfigureColumns()
    {
        Columns.Clear();
        if (SelectedReportType is { } type && ColumnSets.TryGetValue(type.Key, out var columns)) foreach (var column in columns) Columns.Add(column);
    }

    private async Task Execute(Func<Task> action)
    {
        if (IsLoading) return;
        IsLoading = true; ErrorMessage = null;
        try { await action(); }
        catch (Exception ex) { ErrorMessage = ToMessage(ex); }
        finally { IsLoading = false; OnPropertyChanged(nameof(IsEmpty)); }
    }

    private static string ToMessage(Exception exception)
    {
        var api = exception as ApiException;
        var message = api?.Message ?? exception.Message;
        return api?.ErrorCode == "VALIDATION_ERROR" || message.Contains("Request validation failed", StringComparison.OrdinalIgnoreCase)
            ? "Rapor filtreleri doğrulanamadı. Tarih, saat ve ID alanlarını kontrol edin."
            : message.Contains("cannot precede", StringComparison.OrdinalIgnoreCase)
                ? "Başlangıç ve bitiş değerlerini kontrol edin."
                : message;
    }

    private static void Replace<T>(ObservableCollection<T> target, IEnumerable<T> source) { target.Clear(); foreach (var item in source) target.Add(item); }
}

public sealed record ReportTypeItem(string Key, string Name);
