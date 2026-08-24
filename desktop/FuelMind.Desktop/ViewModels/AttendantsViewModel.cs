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
    [ObservableProperty, NotifyPropertyChangedFor(nameof(SelectedAttendantSummary)), NotifyPropertyChangedFor(nameof(AssignmentReadinessMessage)), NotifyCanExecuteChangedFor(nameof(AssignCommand))] private AttendantDto? _selectedAttendant;
    [ObservableProperty, NotifyPropertyChangedFor(nameof(SelectedShiftSummary)), NotifyPropertyChangedFor(nameof(AssignmentReadinessMessage)), NotifyCanExecuteChangedFor(nameof(AssignCommand))] private ShiftDto? _selectedShift;
    [ObservableProperty] private StationDto? _selectedStation;
    [ObservableProperty] private AssignmentRow? _selectedAssignment;
    [ObservableProperty] private string _code = "";
    [ObservableProperty] private string _fullName = "";
    [ObservableProperty] private string _employeeNumber = "";
    [ObservableProperty] private string? _phone;
    [ObservableProperty] private bool _attendantIsActive = true;
    [ObservableProperty, NotifyPropertyChangedFor(nameof(IsEditMode)), NotifyPropertyChangedFor(nameof(AttendantSaveActionText))] private int? _editingAttendantId;
    [ObservableProperty] private TimeOnly _startTime = new(8, 0);
    [ObservableProperty] private TimeOnly _endTime = new(16, 0);
    [ObservableProperty] private string _shiftCode = "";
    [ObservableProperty] private string _shiftName = "";
    [ObservableProperty, NotifyCanExecuteChangedFor(nameof(AssignCommand))] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;
    [ObservableProperty] private string? _successMessage;
    [ObservableProperty] private int _selectedTabIndex;
    public bool IsEmpty => !IsLoading && Attendants.Count == 0 && ErrorMessage is null;
    public bool IsEditMode => EditingAttendantId is > 0;
    public string AttendantSaveActionText => IsEditMode ? "Değişiklikleri Kaydet" : "Pompacıyı Kaydet";
    public string SelectedAttendantSummary => SelectedAttendant is null
        ? "Henüz pompacı seçilmedi"
        : $"{SelectedAttendant.FullName} / {SelectedAttendant.Code}";
    public string SelectedShiftSummary => SelectedShift is null
        ? "Henüz vardiya seçilmedi"
        : $"{SelectedShift.Name} / {SelectedShift.Schedule}";
    public string AssignmentReadinessMessage => SelectedAttendant is null || SelectedShift is null
        ? "1. Pompacı seçin  •  2. Vardiya seçin  •  3. Atamayı oluşturun"
        : SelectedAttendant.StationId != SelectedShift.StationId
            ? "Seçilen pompacı ve vardiya aynı istasyona ait olmalıdır."
            : "Atama oluşturmaya hazır.";

    public async Task LoadAsync() => await Run(async () =>
    {
        var attendantId = SelectedAttendant?.Id;
        var shiftId = SelectedShift?.Id;
        Replace(Attendants, await operations.AttendantsAsync());
        Replace(Shifts, await operations.ShiftsAsync());
        Replace(Stations, await stations.GetActiveStationsAsync());
        SelectedAttendant = attendantId is int selectedAttendantId ? Attendants.FirstOrDefault(item => item.Id == selectedAttendantId) : null;
        SelectedShift = shiftId is int selectedShiftId ? Shifts.FirstOrDefault(item => item.Id == selectedShiftId) : null;
        await LoadAssignmentsCoreAsync();
    });
    [RelayCommand] private Task RefreshAsync() => LoadAsync();
    [RelayCommand] private void NewAttendant()
    {
        SelectedAttendant = null;
        EditingAttendantId = null;
        Code = "";
        FullName = "";
        EmployeeNumber = "";
        Phone = null;
        SelectedStation = null;
        AttendantIsActive = true;
        ErrorMessage = null;
        SuccessMessage = null;
    }
    [RelayCommand] private async Task SaveAttendantAsync()
    {
        if (SelectedStation is null) { ErrorMessage = "İstasyon seçin."; return; }
        if (!Require(Code, "Pompacı kodu") || !Require(FullName, "Ad soyad") || !Require(EmployeeNumber, "Personel numarası")) return;
        // Keep the transport decision independent from any stale/default selection id.
        var editingId = IsEditMode ? EditingAttendantId : null;
        await Run(async () =>
        {
            await operations.SaveAttendantAsync(editingId, new()
            {
                StationId = SelectedStation.Id,
                Code = Code,
                FullName = FullName,
                EmployeeNumber = EmployeeNumber,
                Phone = Phone,
                IsActive = AttendantIsActive,
            });

            await LoadCoreAsync();
            if (editingId is null)
                NewAttendant();
            SuccessMessage = editingId is null ? "Yeni pompacı kaydedildi." : "Pompacı güncellendi.";
        });
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
    private bool CanAssign() => !IsLoading && SelectedAttendant is not null && SelectedShift is not null && SelectedAttendant.StationId == SelectedShift.StationId;

    [RelayCommand(CanExecute = nameof(CanAssign))] private async Task AssignAsync()
    {
        if (SelectedAttendant is null || SelectedShift is null) { ErrorMessage = "Pompacı ve vardiya seçin."; return; }
        if (SelectedAttendant.StationId != SelectedShift.StationId) { ErrorMessage = "Seçilen pompacı ve vardiya aynı istasyona ait olmalıdır."; return; }
        if (Assignments.Any(item => item.IsActive && item.AttendantId == SelectedAttendant.Id && item.ShiftId == SelectedShift.Id))
        {
            ErrorMessage = "Bu pompacı zaten seçilen vardiyaya atanmış.";
            return;
        }

        var attendant = SelectedAttendant;
        var shift = SelectedShift;
        await Run(async () =>
        {
            await operations.AssignAsync(new() { AttendantId = attendant.Id, ShiftId = shift.Id });
            await LoadAssignmentsCoreAsync();
            SuccessMessage = $"{attendant.FullName}, {shift.Name} vardiyasına atandı.";
            SelectedTabIndex = 2;
        });
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
    partial void OnSelectedAttendantChanged(AttendantDto? value)
    {
        if (value is null)
        {
            EditingAttendantId = null;
            return;
        }

        // A DataGrid new-item placeholder can have the default Id (0). It must never
        // turn a create operation into an update against attendants/0.
        if (value.Id <= 0)
        {
            NewAttendant();
            return;
        }

        EditingAttendantId = value.Id;
        Code = value.Code;
        FullName = value.FullName;
        EmployeeNumber = value.EmployeeNumber;
        Phone = value.Phone;
        AttendantIsActive = value.IsActive;
        SelectedStation = Stations.FirstOrDefault(s => s.Id == value.StationId);
    }
    partial void OnSelectedShiftChanged(ShiftDto? value) { if (value is null) return; ShiftCode = value.Code; ShiftName = value.Name; StartTime = value.StartTime; EndTime = value.EndTime; SelectedStation = Stations.FirstOrDefault(s => s.Id == value.StationId); }
    private async Task LoadCoreAsync()
    {
        var attendantId = SelectedAttendant?.Id;
        var shiftId = SelectedShift?.Id;
        Replace(Attendants, await operations.AttendantsAsync());
        Replace(Shifts, await operations.ShiftsAsync());
        SelectedAttendant = attendantId is int selectedAttendantId ? Attendants.FirstOrDefault(item => item.Id == selectedAttendantId) : null;
        SelectedShift = shiftId is int selectedShiftId ? Shifts.FirstOrDefault(item => item.Id == selectedShiftId) : null;
        await LoadAssignmentsCoreAsync();
    }
    private async Task LoadAssignmentsCoreAsync()
    {
        var rows = (await operations.AssignmentsAsync()).Select(item =>
        {
            var shift = Shifts.FirstOrDefault(x => x.Id == item.ShiftId);
            return new AssignmentRow(
                item.Id,
                item.AttendantId,
                item.ShiftId,
                item.IsActive,
                Attendants.FirstOrDefault(x => x.Id == item.AttendantId)?.FullName ?? $"#{item.AttendantId}",
                shift?.Name ?? $"#{item.ShiftId}",
                shift?.Schedule ?? "-",
                Stations.FirstOrDefault(x => x.Id == item.StationId)?.DisplayName ?? $"İstasyon #{item.StationId}");
        });
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
            : message.Contains("same station", StringComparison.OrdinalIgnoreCase) || message.Contains("belong to the same station", StringComparison.OrdinalIgnoreCase)
                ? "Seçilen pompacı ve vardiya aynı istasyona ait olmalıdır."
                : message.Contains("already assigned", StringComparison.OrdinalIgnoreCase) || message.Contains("duplicate", StringComparison.OrdinalIgnoreCase)
                    ? "Bu pompacı zaten seçilen vardiyaya atanmış."
            : message.Contains("already exists", StringComparison.OrdinalIgnoreCase)
                ? "Bu pompacı kodu veya personel numarası zaten kullanılıyor."
                : message;
    }
    private static void Replace<T>(ObservableCollection<T> destination, IEnumerable<T> source) { destination.Clear(); foreach (var item in source) destination.Add(item); }
}

public sealed record AssignmentRow(int Id, int AttendantId, int ShiftId, bool IsActive, string Attendant, string Shift, string Schedule, string Station)
{
    public string ActiveDisplay => IsActive ? "Aktif" : "Pasif";
}
