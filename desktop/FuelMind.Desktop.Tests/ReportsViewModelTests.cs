using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Dtos.Reports;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using FuelMind.Desktop.ViewModels;
using Microsoft.Extensions.Logging.Abstractions;
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
        Assert.Equal(["sale_id", "timestamp", "station", "pump", "nozzle", "attendant"], viewModel.Columns.Take(6).Select(item => item.Key));
        Assert.Contains(viewModel.Columns, item => item.Key == "start_totalizer" && item.IsNumeric);
        Assert.Contains(viewModel.Columns, item => item.Key == "payment_type");
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

    [Fact]
    public async Task RunDisablesDuplicateRequestsAndResetsLoadingAfterCompletion()
    {
        var service = new DelayedReportService();
        var viewModel = new ReportsViewModel(service, new FakeStationService())
        {
            SelectedReportType = new ReportTypeItem("sales", "Satış"),
        };

        var firstRun = viewModel.RunCommand.ExecuteAsync(null);
        await service.RequestStarted.Task;

        Assert.True(viewModel.IsLoading);
        Assert.False(viewModel.RunCommand.CanExecute(null));
        await viewModel.RunCommand.ExecuteAsync(null);
        Assert.Equal(1, service.CallCount);

        service.CompleteRequest();
        await firstRun;

        Assert.False(viewModel.IsLoading);
        Assert.True(viewModel.RunCommand.CanExecute(null));
        Assert.Single(viewModel.Rows);
    }

    [Fact]
    public async Task RunResetsLoadingAndShowsErrorWhenReportRequestFails()
    {
        var viewModel = new ReportsViewModel(new FailingReportService(), new FakeStationService())
        {
            SelectedReportType = new ReportTypeItem("sales", "Satış"),
        };

        await viewModel.RunCommand.ExecuteAsync(null);

        Assert.False(viewModel.IsLoading);
        Assert.False(string.IsNullOrWhiteSpace(viewModel.ErrorMessage));
    }

    [Fact]
    public async Task PdfExportAcceptsValidatedPdfAndCsvExportKeepsCsvContract()
    {
        var pdfService = new ReportService(CreateApiClient(new DownloadHandler("application/pdf", "%PDF-1.7\nbody")));
        var pdf = await pdfService.ExportAsync("sales", "pdf", "?date_from=2026-08-20");
        Assert.StartsWith("%PDF-", Encoding.ASCII.GetString(pdf));

        var csvService = new ReportService(CreateApiClient(new DownloadHandler("text/csv", "timestamp,total\n2026-08-20,10")));
        var csv = await csvService.ExportAsync("sales", "csv", "?station_id=3");
        Assert.StartsWith("timestamp,total", Encoding.UTF8.GetString(csv));
    }

    [Fact]
    public async Task PdfExportRejectsInvalidPdfResponse()
    {
        var service = new ReportService(CreateApiClient(new DownloadHandler("application/json", "{\"error\":\"invalid\"}")));

        var exception = await Assert.ThrowsAsync<ApiException>(() => service.ExportAsync("sales", "pdf", ""));

        Assert.Equal("INVALID_DOWNLOAD_RESPONSE", exception.ErrorCode);
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

    private sealed class DelayedReportService : IReportService
    {
        private readonly TaskCompletionSource<IReadOnlyList<ReportRowDto>> _completion = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public TaskCompletionSource<bool> RequestStarted { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public int CallCount { get; private set; }

        public Task<byte[]> ExportAsync(string reportType, string format, string query, CancellationToken cancellationToken = default) => Task.FromResult(Array.Empty<byte>());

        public Task<IReadOnlyList<ReportRowDto>> GetAsync(string reportType, string query, CancellationToken cancellationToken = default)
        {
            CallCount++;
            RequestStarted.TrySetResult(true);
            return _completion.Task;
        }

        public void CompleteRequest()
        {
            using var document = JsonDocument.Parse("""[{"timestamp":"2026-08-20T09:00:00Z"}]""");
            _completion.TrySetResult([ReportRowDto.From(document.RootElement[0])]);
        }
    }

    private sealed class FailingReportService : IReportService
    {
        public Task<byte[]> ExportAsync(string reportType, string format, string query, CancellationToken cancellationToken = default) => Task.FromResult(Array.Empty<byte>());
        public Task<IReadOnlyList<ReportRowDto>> GetAsync(string reportType, string query, CancellationToken cancellationToken = default) =>
            Task.FromException<IReadOnlyList<ReportRowDto>>(new InvalidOperationException("API ulaşılabilir değil."));
    }

    private static ApiClient CreateApiClient(HttpMessageHandler handler) => new(
        new HttpClient(handler) { BaseAddress = new Uri("http://localhost/api/") },
        new JsonSerializerOptions { PropertyNameCaseInsensitive = true },
        new AuthState(),
        NullLogger<ApiClient>.Instance);

    private sealed class DownloadHandler(string mediaType, string body) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var content = new ByteArrayContent(Encoding.UTF8.GetBytes(body));
            content.Headers.ContentType = MediaTypeHeaderValue.Parse(mediaType);
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = content });
        }
    }

    private sealed class FakeStationService : IStationService
    {
        public Task<IReadOnlyList<StationDto>> GetActiveStationsAsync(CancellationToken cancellationToken = default) => Task.FromResult<IReadOnlyList<StationDto>>([]);
        public Task<StationLiveStatusDto> GetLiveStatusAsync(int stationId, CancellationToken cancellationToken = default) => Task.FromException<StationLiveStatusDto>(new NotSupportedException());
        public Task<IReadOnlyList<FuelTypeDto>> GetFuelTypesAsync(CancellationToken cancellationToken = default) => Task.FromResult<IReadOnlyList<FuelTypeDto>>([]);
    }
}
