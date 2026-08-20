using FuelMind.Desktop.Dtos.Faults;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.ViewModels;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class FaultsViewModelTests
{
    [Fact]
    public async Task InvestigateAndResolveKeepTheUpdatedFaultInDetailAfterFilteredRefresh()
    {
        var service = new FakeFaultService();
        var viewModel = new FaultsViewModel(service, new FakeStationService()) { Status = "OPEN" };

        await viewModel.LoadAsync();
        await viewModel.InvestigateCommand.ExecuteAsync(null);

        Assert.Equal("INVESTIGATING", viewModel.SelectedFault?.Status);
        Assert.Empty(viewModel.Faults);
        Assert.Contains("incelemeye alındı", viewModel.SuccessMessage);

        viewModel.ResolutionNote = "Bağlantı ve kablo kontrol edildi.";
        await viewModel.ResolveCommand.ExecuteAsync(null);

        Assert.Equal("RESOLVED", viewModel.SelectedFault?.Status);
        Assert.Equal("Bağlantı ve kablo kontrol edildi.", viewModel.SelectedFault?.ResolutionNote);
        Assert.NotNull(viewModel.SelectedFault?.ResolvedAt);
        Assert.Equal(7, viewModel.SelectedFault?.ResolvedBy);
        Assert.Contains("çözüldü", viewModel.SuccessMessage);
    }

    private sealed class FakeFaultService : IFaultService
    {
        private FaultDto _fault = OpenFault();

        public Task<IReadOnlyList<FaultDto>> ListAsync(string query, CancellationToken ct = default) =>
            Task.FromResult<IReadOnlyList<FaultDto>>(query.Contains("status=OPEN", StringComparison.Ordinal) && _fault.Status != "OPEN" ? [] : [_fault]);

        public Task<FaultDto> CreateAsync(FaultCreateDto request, CancellationToken ct = default) => Task.FromResult(_fault);
        public Task<IReadOnlyList<FaultTargetOption>> GetTargetsAsync(int stationId, string targetType, CancellationToken ct = default) => Task.FromResult<IReadOnlyList<FaultTargetOption>>([]);

        public Task<FaultDto> InvestigateAsync(int id, CancellationToken ct = default)
        {
            _fault = Copy("INVESTIGATING");
            return Task.FromResult(_fault);
        }

        public Task<FaultDto> ResolveAsync(int id, string note, CancellationToken ct = default)
        {
            _fault = Copy("RESOLVED", note);
            return Task.FromResult(_fault);
        }

        private FaultDto Copy(string status, string? note = null) => new()
        {
            Id = _fault.Id, StationId = _fault.StationId, TargetType = _fault.TargetType, TargetId = _fault.TargetId,
            FaultType = _fault.FaultType, FaultCode = _fault.FaultCode, Title = _fault.Title, Status = status,
            StartedAt = _fault.StartedAt, DetectedAt = _fault.DetectedAt,
            ResolutionNote = note, ResolvedAt = status == "RESOLVED" ? DateTimeOffset.UtcNow : null,
            ResolvedBy = status == "RESOLVED" ? 7 : null,
        };

        private static FaultDto OpenFault() => new()
        {
            Id = 42, StationId = 1, TargetType = "PUMP", TargetId = 2, FaultType = "CONNECTION",
            FaultCode = "PUMP_NOT_CONNECTED", Title = "Pompa bağlantısı", Status = "OPEN",
            StartedAt = DateTimeOffset.UtcNow.AddMinutes(-5), DetectedAt = DateTimeOffset.UtcNow,
        };
    }

    private sealed class FakeStationService : IStationService
    {
        public Task<IReadOnlyList<StationDto>> GetActiveStationsAsync(CancellationToken cancellationToken = default) => Task.FromResult<IReadOnlyList<StationDto>>([]);
        public Task<StationLiveStatusDto> GetLiveStatusAsync(int stationId, CancellationToken cancellationToken = default) => Task.FromException<StationLiveStatusDto>(new NotSupportedException());
        public Task<IReadOnlyList<FuelTypeDto>> GetFuelTypesAsync(CancellationToken cancellationToken = default) => Task.FromResult<IReadOnlyList<FuelTypeDto>>([]);
    }
}
