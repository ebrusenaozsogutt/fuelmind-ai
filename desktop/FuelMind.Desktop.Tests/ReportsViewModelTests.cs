using System.Text.Json;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Dtos.Reports;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.ViewModels;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class ReportsViewModelTests
{
    [Fact]
    public async Task SalesReportUsesOperationsFiltersAndShowsItsOwnColumns()
    {
        var service = new FakeReportService();
        var viewModel = new ReportsViewModel(service, new FakeStationService());
        await viewModel.LoadAsync();
        viewModel.SelectedReportType = viewModel.ReportTypes.Single(item => item.Key == "sales");
        viewModel.DateFrom = new DateTime(2026, 8, 1); viewModel.DateTo = new DateTime(2026, 8, 2);
        viewModel.TimeFrom = "08:00"; viewModel.TimeTo = "18:00";
        viewModel.PumpId = "3"; viewModel.NozzleId = "8"; viewModel.FuelTypeId = "4";
        viewModel.CustomerId = "9"; viewModel.VehicleId = "10"; viewModel.Plate = "34 ABC 01";
        viewModel.AttendantId = "6"; viewModel.ShiftId = "7";

        await viewModel.RunCommand.ExecuteAsync(null);

        Assert.Contains("attendant_id=6", service.LastQuery);
        Assert.Contains("shift_id=7", service.LastQuery);
        Assert.Contains("plate=34%20ABC%2001", service.LastQuery);
        Assert.Contains("time_from=08%3A00", service.LastQuery);
        Assert.Equal(["timestamp", "station", "pump", "nozzle", "attendant", "shift"], viewModel.Columns.Take(6).Select(item => item.Key));
        Assert.Equal("Pompacı Adı", viewModel.Rows.Single()["attendant"]);
        Assert.Equal("Akşam", viewModel.Rows.Single()["shift"]);
    }

    [Fact]
    public void ChangingReportTypeClearsInapplicableSalesFiltersAndChangesColumns()
    {
        var viewModel = new ReportsViewModel(new FakeReportService(), new FakeStationService());
        viewModel.SelectedReportType = viewModel.ReportTypes.Single(item => item.Key == "sales");
        viewModel.AttendantId = "6"; viewModel.Plate = "34 ABC 01";

        viewModel.SelectedReportType = viewModel.ReportTypes.Single(item => item.Key == "faults");

        Assert.Null(viewModel.AttendantId);
        Assert.Null(viewModel.Plate);
        Assert.Contains(viewModel.Columns, item => item.Key == "fault_code");
        Assert.DoesNotContain(viewModel.Columns, item => item.Key == "attendant");
    }

    private sealed class FakeReportService : IReportService
    {
        public string LastQuery { get; private set; } = "";
        public Task<byte[]> ExportAsync(string reportType, string format, string query, CancellationToken cancellationToken = default) => Task.FromResult(Array.Empty<byte>());
        public Task<IReadOnlyList<ReportRowDto>> GetAsync(string reportType, string query, CancellationToken cancellationToken = default)
        {
            LastQuery = query;
            using var document = JsonDocument.Parse("""[{"timestamp":"2026-08-01T09:00:00Z","station":"Merkez","pump":"P-1","nozzle":"N-1","attendant":"Pompacı Adı","shift":"Akşam"}]""");
            return Task.FromResult<IReadOnlyList<ReportRowDto>>([ReportRowDto.From(document.RootElement[0])]);
        }
    }

    private sealed class FakeStationService : IStationService
    {
        public Task<IReadOnlyList<StationDto>> GetActiveStationsAsync(CancellationToken cancellationToken = default) => Task.FromResult<IReadOnlyList<StationDto>>([]);
        public Task<StationLiveStatusDto> GetLiveStatusAsync(int stationId, CancellationToken cancellationToken = default) => Task.FromException<StationLiveStatusDto>(new NotSupportedException());
        public Task<IReadOnlyList<FuelTypeDto>> GetFuelTypesAsync(CancellationToken cancellationToken = default) => Task.FromResult<IReadOnlyList<FuelTypeDto>>([]);
    }
}
