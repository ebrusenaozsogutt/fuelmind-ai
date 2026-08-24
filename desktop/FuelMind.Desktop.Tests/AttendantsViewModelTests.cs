using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Dtos.Operations;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.ViewModels;
using System.Net;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class AttendantsViewModelTests
{
    [Fact]
    public async Task AttendantAndShiftSelectionsPersistAcrossTabChanges()
    {
        var (viewModel, service) = await CreateViewModelAsync();
        var attendant = service.Attendants.Single();
        var shift = service.Shifts.Single();

        viewModel.SelectedAttendant = attendant;
        viewModel.SelectedTabIndex = 1;
        viewModel.SelectedShift = shift;
        viewModel.SelectedTabIndex = 2;

        Assert.Same(attendant, viewModel.SelectedAttendant);
        Assert.Same(shift, viewModel.SelectedShift);
        Assert.Equal("Ayşe Demir / ATT-01", viewModel.SelectedAttendantSummary);
        Assert.Equal("Sabah / 08:00 – 16:00", viewModel.SelectedShiftSummary);
    }

    [Fact]
    public async Task AssignmentCommandIsDisabledUntilCompatibleSelectionsAreMade()
    {
        var (viewModel, service) = await CreateViewModelAsync(includeOtherStationShift: true);

        Assert.False(viewModel.AssignCommand.CanExecute(null));

        viewModel.SelectedAttendant = service.Attendants.Single();
        Assert.False(viewModel.AssignCommand.CanExecute(null));

        viewModel.SelectedShift = service.Shifts.Single(item => item.StationId == 2);
        Assert.False(viewModel.AssignCommand.CanExecute(null));
        Assert.Equal("Seçilen pompacı ve vardiya aynı istasyona ait olmalıdır.", viewModel.AssignmentReadinessMessage);

        viewModel.SelectedShift = service.Shifts.Single(item => item.StationId == 1);
        Assert.True(viewModel.AssignCommand.CanExecute(null));
        Assert.Equal("Atama oluşturmaya hazır.", viewModel.AssignmentReadinessMessage);
    }

    [Fact]
    public async Task ValidAssignmentCallsApiRefreshesListAndClearsPreviousError()
    {
        var (viewModel, service) = await CreateViewModelAsync();
        viewModel.SelectedAttendant = service.Attendants.Single();
        viewModel.SelectedShift = service.Shifts.Single();
        viewModel.ErrorMessage = "Önceki hata";

        await viewModel.AssignCommand.ExecuteAsync(null);

        Assert.Equal(1, service.AssignCallCount);
        Assert.Equal(1, service.LastAssignment?.AttendantId);
        Assert.Equal(10, service.LastAssignment?.ShiftId);
        Assert.Single(viewModel.Assignments);
        Assert.Equal("08:00 – 16:00", viewModel.Assignments.Single().Schedule);
        Assert.Null(viewModel.ErrorMessage);
        Assert.Equal("Ayşe Demir, Sabah vardiyasına atandı.", viewModel.SuccessMessage);
        Assert.Equal(2, viewModel.SelectedTabIndex);
    }

    [Fact]
    public async Task DuplicateAssignmentIsRejectedWithoutCallingApi()
    {
        var (viewModel, service) = await CreateViewModelAsync(withExistingAssignment: true);
        viewModel.SelectedAttendant = service.Attendants.Single();
        viewModel.SelectedShift = service.Shifts.Single();

        await viewModel.AssignCommand.ExecuteAsync(null);

        Assert.Equal(0, service.AssignCallCount);
        Assert.Equal("Bu pompacı zaten seçilen vardiyaya atanmış.", viewModel.ErrorMessage);
    }

    [Fact]
    public async Task NewModeUsesPostClearsStaleSelectionAndRefreshesTheList()
    {
        var (viewModel, service) = await CreateViewModelAsync();
        viewModel.SelectedAttendant = service.Attendants.Single();

        viewModel.NewAttendantCommand.Execute(null);
        viewModel.Code = "ATT-02";
        viewModel.FullName = "Mehmet Kaya";
        viewModel.EmployeeNumber = "1002";
        viewModel.Phone = "5551234567";
        viewModel.AttendantIsActive = true;
        viewModel.SelectedStation = viewModel.Stations.First();

        await viewModel.SaveAttendantCommand.ExecuteAsync(null);

        Assert.Null(service.LastAttendantSaveId);
        Assert.Equal(2, service.Attendants.Count);
        Assert.Contains(viewModel.Attendants, item => item.Code == "ATT-02");
        Assert.Null(viewModel.SelectedAttendant);
        Assert.False(viewModel.IsEditMode);
        Assert.Equal("Yeni pompacı kaydedildi.", viewModel.SuccessMessage);
        Assert.Null(viewModel.ErrorMessage);
    }

    [Fact]
    public async Task EmptyGridItemCannotCauseAnUpdateAgainstZeroId()
    {
        var (viewModel, service) = await CreateViewModelAsync();
        viewModel.SelectedAttendant = new AttendantDto();
        viewModel.Code = "ATT-02";
        viewModel.FullName = "Mehmet Kaya";
        viewModel.EmployeeNumber = "1002";
        viewModel.SelectedStation = viewModel.Stations.First();

        await viewModel.SaveAttendantCommand.ExecuteAsync(null);

        Assert.Null(service.LastAttendantSaveId);
        Assert.Null(viewModel.ErrorMessage);
    }

    [Fact]
    public async Task EditModeUsesPutAndKeepsExistingAttendantEditable()
    {
        var (viewModel, service) = await CreateViewModelAsync();
        viewModel.SelectedAttendant = service.Attendants.Single();
        viewModel.FullName = "Ayşe Yılmaz";
        viewModel.Phone = "5550000000";

        await viewModel.SaveAttendantCommand.ExecuteAsync(null);

        Assert.Equal(1, service.LastAttendantSaveId);
        Assert.Equal("Ayşe Yılmaz", service.Attendants.Single().FullName);
        Assert.Equal("5550000000", service.Attendants.Single().Phone);
        Assert.True(viewModel.IsEditMode);
        Assert.Equal("Pompacı güncellendi.", viewModel.SuccessMessage);
    }

    [Fact]
    public async Task DuplicateAttendantBusinessErrorIsShownInTurkish()
    {
        var (viewModel, service) = await CreateViewModelAsync();
        service.DuplicateNextAttendantSave = true;
        viewModel.NewAttendantCommand.Execute(null);
        viewModel.Code = "ATT-01";
        viewModel.FullName = "Yeni Kayıt";
        viewModel.EmployeeNumber = "9999";
        viewModel.SelectedStation = viewModel.Stations.First();

        await viewModel.SaveAttendantCommand.ExecuteAsync(null);

        Assert.Equal("Bu pompacı kodu veya personel numarası zaten kullanılıyor.", viewModel.ErrorMessage);
    }

    private static async Task<(AttendantsViewModel ViewModel, FakeOperationsService Service)> CreateViewModelAsync(
        bool includeOtherStationShift = false,
        bool withExistingAssignment = false)
    {
        var service = new FakeOperationsService(includeOtherStationShift, withExistingAssignment);
        var viewModel = new AttendantsViewModel(service, new FakeStationService());
        await viewModel.LoadAsync();
        return (viewModel, service);
    }

    private sealed class FakeOperationsService : IOperationsService
    {
        private readonly List<AssignmentDto> _assignments;

        public FakeOperationsService(bool includeOtherStationShift, bool withExistingAssignment)
        {
            Attendants = [new AttendantDto { Id = 1, StationId = 1, Code = "ATT-01", FullName = "Ayşe Demir", EmployeeNumber = "1001", IsActive = true }];
            var shifts = new List<ShiftDto>
            {
                new() { Id = 10, StationId = 1, Code = "SABAH", Name = "Sabah", StartTime = new TimeOnly(8, 0), EndTime = new TimeOnly(16, 0), IsActive = true },
            };
            if (includeOtherStationShift)
                shifts.Add(new ShiftDto { Id = 20, StationId = 2, Code = "AKSAM", Name = "Akşam", StartTime = new TimeOnly(16, 0), EndTime = new TimeOnly(23, 0), IsActive = true });
            Shifts = shifts;
            _assignments = withExistingAssignment ? [new AssignmentDto { Id = 5, AttendantId = 1, ShiftId = 10, StationId = 1, IsActive = true }] : [];
        }

        public List<AttendantDto> Attendants { get; }
        public IReadOnlyList<ShiftDto> Shifts { get; }
        public int AssignCallCount { get; private set; }
        public AssignmentSaveDto? LastAssignment { get; private set; }
        public int? LastAttendantSaveId { get; private set; }
        public bool DuplicateNextAttendantSave { get; set; }

        public Task<IReadOnlyList<AttendantDto>> AttendantsAsync(CancellationToken ct = default) => Task.FromResult<IReadOnlyList<AttendantDto>>(Attendants.ToList());
        public Task<IReadOnlyList<ShiftDto>> ShiftsAsync(CancellationToken ct = default) => Task.FromResult(Shifts);
        public Task<IReadOnlyList<AssignmentDto>> AssignmentsAsync(CancellationToken ct = default) => Task.FromResult<IReadOnlyList<AssignmentDto>>(_assignments.ToList());
        public Task<AttendantDto> SaveAttendantAsync(int? id, AttendantSaveDto dto, CancellationToken ct = default)
        {
            LastAttendantSaveId = id;
            if (DuplicateNextAttendantSave)
                throw new ApiException(HttpStatusCode.Conflict, "CONFLICT", "Attendant code or employee number already exists.");

            var attendant = new AttendantDto
            {
                Id = id ?? Attendants.Max(item => item.Id) + 1,
                StationId = dto.StationId,
                Code = dto.Code,
                FullName = dto.FullName,
                EmployeeNumber = dto.EmployeeNumber,
                Phone = dto.Phone,
                IsActive = dto.IsActive,
            };
            if (id is int editingId)
                Attendants[Attendants.FindIndex(item => item.Id == editingId)] = attendant;
            else
                Attendants.Add(attendant);
            return Task.FromResult(attendant);
        }
        public Task<ShiftDto> SaveShiftAsync(int? id, ShiftSaveDto dto, CancellationToken ct = default) => Task.FromResult(Shifts[0]);
        public Task DeactivateAttendantAsync(int id, CancellationToken ct = default) => Task.CompletedTask;
        public Task DeactivateShiftAsync(int id, CancellationToken ct = default) => Task.CompletedTask;
        public Task<AssignmentDto> SetAssignmentActiveAsync(int id, bool active, CancellationToken ct = default) =>
            Task.FromResult(_assignments.Single(item => item.Id == id));

        public Task AssignAsync(AssignmentSaveDto dto, CancellationToken ct = default)
        {
            AssignCallCount++;
            LastAssignment = dto;
            _assignments.Add(new AssignmentDto { Id = 100, AttendantId = dto.AttendantId, ShiftId = dto.ShiftId, StationId = 1, IsActive = dto.IsActive });
            return Task.CompletedTask;
        }
    }

    private sealed class FakeStationService : IStationService
    {
        private static readonly IReadOnlyList<StationDto> StationList =
        [
            new StationDto { Id = 1, Code = "IST-01", Name = "Merkez", City = "İstanbul", District = "Kadıköy", Address = "Merkez", IsActive = true },
            new StationDto { Id = 2, Code = "IST-02", Name = "Kuzey", City = "İstanbul", District = "Üsküdar", Address = "Kuzey", IsActive = true },
        ];

        public Task<IReadOnlyList<StationDto>> GetActiveStationsAsync(CancellationToken cancellationToken = default) => Task.FromResult(StationList);
        public Task<StationLiveStatusDto> GetLiveStatusAsync(int stationId, CancellationToken cancellationToken = default) => Task.FromException<StationLiveStatusDto>(new NotSupportedException());
        public Task<IReadOnlyList<FuelTypeDto>> GetFuelTypesAsync(CancellationToken cancellationToken = default) => Task.FromResult<IReadOnlyList<FuelTypeDto>>([]);
    }
}
