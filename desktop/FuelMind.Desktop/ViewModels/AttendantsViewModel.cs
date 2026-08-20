using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Operations;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class AttendantsViewModel(IOperationsService operations, IStationService stations) : ObservableObject
{
    public ObservableCollection<AttendantDto> Attendants { get; } = [];
    public ObservableCollection<ShiftDto> Shifts { get; } = [];
    public ObservableCollection<StationDto> Stations { get; } = [];
    public ObservableCollection<AssignmentRow> Assignments { get; } = [];
    [ObservableProperty] private AttendantDto? _selectedAttendant;
    [ObservableProperty] private ShiftDto? _selectedShift;
    [ObservableProperty] private StationDto? _selectedStation;
    [ObservableProperty] private AssignmentRow? _selectedAssignment;
    [ObservableProperty] private string _code = "";
    [ObservableProperty] private string _fullName = "";
    [ObservableProperty] private string _employeeNumber = "";
    [ObservableProperty] private string? _phone;
    [ObservableProperty] private TimeOnly _startTime = new(8, 0);
    [ObservableProperty] private TimeOnly _endTime = new(16, 0);
    [ObservableProperty] private string _shiftCode = "";
    [ObservableProperty] private string _shiftName = "";
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;
    [ObservableProperty] private string? _successMessage;
    public bool IsEmpty => !IsLoading && Attendants.Count == 0 && ErrorMessage is null;

    public async Task LoadAsync() => await Run(async () =>
    {
        Replace(Attendants, await operations.AttendantsAsync());
        Replace(Shifts, await operations.ShiftsAsync());
        Replace(Stations, await stations.GetActiveStationsAsync());
        await LoadAssignmentsCoreAsync();
    });
    [RelayCommand] private Task RefreshAsync() => LoadAsync();
    [RelayCommand] private async Task SaveAttendantAsync()
    {
        if (SelectedStation is null) { ErrorMessage = "İstasyon seçin."; return; }
        if (!Require(Code, "Pompacı kodu") || !Require(FullName, "Ad soyad") || !Require(EmployeeNumber, "Personel numarası")) return;
        await Run(async () => { await operations.SaveAttendantAsync(SelectedAttendant?.Id, new() { StationId = SelectedStation.Id, Code = Code, FullName = FullName, EmployeeNumber = EmployeeNumber, Phone = Phone, IsActive = true }); SuccessMessage = "Pompacı kaydedildi."; await LoadCoreAsync(); });
    }
    [RelayCommand] private async Task DeactivateAttendantAsync() { if (SelectedAttendant is null) return; await Run(async () => { await operations.DeactivateAttendantAsync(SelectedAttendant.Id); SuccessMessage = "Pompacı pasife alındı."; await LoadCoreAsync(); }); }
    [RelayCommand] private async Task SaveShiftAsync()
    {
        if (SelectedStation is null) { ErrorMessage = "İstasyon seçin."; return; }
        if (!Require(ShiftCode, "Vardiya kodu") || !Require(ShiftName, "Vardiya adı")) return;
        if (StartTime == EndTime) { ErrorMessage = "Vardiya başlangıç ve bitiş saati aynı olamaz."; return; }
        await Run(async () => { await operations.SaveShiftAsync(SelectedShift?.Id, new() { StationId = SelectedStation.Id, Code = ShiftCode, Name = ShiftName, StartTime = StartTime, EndTime = EndTime, IsActive = true }); SuccessMessage = "Vardiya kaydedildi."; await LoadCoreAsync(); });
    }
    [RelayCommand] private async Task DeactivateShiftAsync() { if (SelectedShift is null) return; await Run(async () => { await operations.DeactivateShiftAsync(SelectedShift.Id); SuccessMessage = "Vardiya pasife alındı."; await LoadCoreAsync(); }); }
    [RelayCommand] private async Task AssignAsync()
    {
        if (SelectedAttendant is null || SelectedShift is null) { ErrorMessage = "Pompacı ve vardiya seçin."; return; }
        await Run(async () => { await operations.AssignAsync(new() { AttendantId = SelectedAttendant.Id, ShiftId = SelectedShift.Id }); await LoadAssignmentsCoreAsync(); SuccessMessage = "Vardiya ataması oluşturuldu."; });
    }
    [RelayCommand] private async Task ToggleAssignmentActiveAsync()
    {
        if (SelectedAssignment is null) return;
        await Run(async () =>
        {
            await operations.SetAssignmentActiveAsync(SelectedAssignment.Id, !SelectedAssignment.IsActive);
            await LoadAssignmentsCoreAsync();
            SuccessMessage = SelectedAssignment.IsActive ? "Atama pasife alındı." : "Atama tekrar aktifleştirildi.";
        });
    }
    partial void OnSelectedAttendantChanged(AttendantDto? value) { if (value is null) return; Code = value.Code; FullName = value.FullName; EmployeeNumber = value.EmployeeNumber; Phone = value.Phone; SelectedStation = Stations.FirstOrDefault(s => s.Id == value.StationId); }
    partial void OnSelectedShiftChanged(ShiftDto? value) { if (value is null) return; ShiftCode = value.Code; ShiftName = value.Name; StartTime = value.StartTime; EndTime = value.EndTime; SelectedStation = Stations.FirstOrDefault(s => s.Id == value.StationId); }
    private async Task LoadCoreAsync() { Replace(Attendants, await operations.AttendantsAsync()); Replace(Shifts, await operations.ShiftsAsync()); await LoadAssignmentsCoreAsync(); }
    private async Task LoadAssignmentsCoreAsync()
    {
        var rows = (await operations.AssignmentsAsync()).Select(item => new AssignmentRow(item.Id, item.IsActive, Attendants.FirstOrDefault(x => x.Id == item.AttendantId)?.FullName ?? $"#{item.AttendantId}", Shifts.FirstOrDefault(x => x.Id == item.ShiftId)?.Name ?? $"#{item.ShiftId}", Stations.FirstOrDefault(x => x.Id == item.StationId)?.DisplayName ?? $"İstasyon #{item.StationId}"));
        Replace(Assignments, rows); SelectedAssignment = Assignments.FirstOrDefault();
    }
    private async Task Run(Func<Task> action) { if (IsLoading) return; IsLoading = true; ErrorMessage = null; SuccessMessage = null; try { await action(); } catch (Exception ex) { ErrorMessage = ToMessage(ex); } finally { IsLoading = false; OnPropertyChanged(nameof(IsEmpty)); } }
    private bool Require(string value, string label) { if (!string.IsNullOrWhiteSpace(value)) return true; ErrorMessage = $"{label} zorunludur."; return false; }
    private static string ToMessage(Exception ex)
    {
        var api = ex as ApiException;
        var message = api?.Message ?? ex.Message;
        return api?.ErrorCode == "VALIDATION_ERROR" || message.Contains("Request validation failed", StringComparison.OrdinalIgnoreCase)
            ? "Form doğrulanamadı. Zorunlu alanları ve vardiya saatlerini kontrol edin."
            : message.Contains("already exists", StringComparison.OrdinalIgnoreCase)
                ? "Bu kod veya personel numarası zaten kullanılıyor."
                : message;
    }
    private static void Replace<T>(ObservableCollection<T> destination, IEnumerable<T> source) { destination.Clear(); foreach (var item in source) destination.Add(item); }
}

public sealed record AssignmentRow(int Id, bool IsActive, string Attendant, string Shift, string Station)
{
    public string ActiveDisplay => IsActive ? "Aktif" : "Pasif";
}
