using FuelMind.Desktop.Dtos.Faults;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.ViewModels;
using System.Net;
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
        Assert.True(viewModel.InvestigateCommand.CanExecute(null));
        Assert.False(viewModel.ResolveCommand.CanExecute(null));
        Assert.True(viewModel.IsResolutionNoteEditable);
        await viewModel.InvestigateCommand.ExecuteAsync(null);

        Assert.Equal("INVESTIGATING", viewModel.SelectedFault?.Status);
        Assert.Empty(viewModel.Faults);
        Assert.False(viewModel.InvestigateCommand.CanExecute(null));
        Assert.Contains("incelemeye alındı", viewModel.SuccessMessage);

        viewModel.NewResolutionNote = "Bağlantı ve kablo kontrol edildi.";
        Assert.True(viewModel.ResolveCommand.CanExecute(null));
        await viewModel.ResolveCommand.ExecuteAsync(null);

        Assert.Equal("RESOLVED", viewModel.SelectedFault?.Status);
        Assert.Equal("Bağlantı ve kablo kontrol edildi.", viewModel.SelectedFault?.ResolutionNote);
        Assert.Equal("Bağlantı ve kablo kontrol edildi.", service.LastResolutionNote);
        Assert.NotNull(viewModel.SelectedFault?.ResolvedAt);
        Assert.Equal(7, viewModel.SelectedFault?.ResolvedBy);
        Assert.Equal("Fault User", viewModel.SelectedFault?.ResolvedByName);
        Assert.False(viewModel.InvestigateCommand.CanExecute(null));
        Assert.False(viewModel.ResolveCommand.CanExecute(null));
        Assert.False(viewModel.IsResolutionNoteEditable);
        Assert.Equal("Bu arıza daha önce çözüldüğü için durumu değiştirilemez.", viewModel.ResolutionNoteHelpText);
        Assert.Contains("çözüldü", viewModel.SuccessMessage);
    }

    [Fact]
    public async Task SelectedFaultSeparatesEditableResolutionNoteFromDetailFields()
    {
        var service = new FakeFaultService();
        var viewModel = new FaultsViewModel(service, new FakeStationService());

        await viewModel.LoadAsync();

        Assert.Equal("Controlled acceptance check", viewModel.SelectedFault?.Cause);
        Assert.Equal("Pompa bağlantısı doğrulaması", viewModel.SelectedFault?.Description);
        Assert.Equal("", viewModel.NewResolutionNote);

        viewModel.NewResolutionNote = "Yeni çözüm notu";

        Assert.Equal("Yeni çözüm notu", viewModel.NewResolutionNote);
        Assert.Null(viewModel.SelectedFault?.ResolutionNote);
    }

    [Fact]
    public async Task ResolveFailureIsShownToTheUserAndKeepsTheFaultEditable()
    {
        var service = new FakeFaultService { ThrowOnResolve = true };
        var viewModel = new FaultsViewModel(service, new FakeStationService());

        await viewModel.LoadAsync();
        viewModel.NewResolutionNote = "Kablo kontrol edildi.";
        await viewModel.ResolveCommand.ExecuteAsync(null);

        Assert.Equal("OPEN", viewModel.SelectedFault?.Status);
        Assert.True(viewModel.IsResolutionNoteEditable);
        Assert.Equal("Sunucuya ulaşılamadı.", viewModel.ErrorMessage);
    }

    private sealed class FakeFaultService : IFaultService
    {
        private FaultDto _fault = OpenFault();
        public string? LastResolutionNote { get; private set; }
        public bool ThrowOnResolve { get; init; }

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
            if (ThrowOnResolve)
                throw new ApiException(HttpStatusCode.BadGateway, "UPSTREAM_UNAVAILABLE", "Sunucuya ulaşılamadı.");
            LastResolutionNote = note;
            _fault = Copy("RESOLVED", note);
            return Task.FromResult(_fault);
        }

        private FaultDto Copy(string status, string? note = null) => new()
        {
            Id = _fault.Id, StationId = _fault.StationId, TargetType = _fault.TargetType, TargetId = _fault.TargetId,
            FaultType = _fault.FaultType, FaultCode = _fault.FaultCode, Title = _fault.Title, Status = status,
            StartedAt = _fault.StartedAt, DetectedAt = _fault.DetectedAt,
            Description = _fault.Description, Cause = _fault.Cause,
            ResolutionNote = note, ResolvedAt = status == "RESOLVED" ? DateTimeOffset.UtcNow : null,
            ResolvedBy = status == "RESOLVED" ? 7 : null,
            ResolvedByName = status == "RESOLVED" ? "Fault User" : null,
        };

        private static FaultDto OpenFault() => new()
        {
            Id = 42, StationId = 1, TargetType = "PUMP", TargetId = 2, FaultType = "CONNECTION",
            FaultCode = "PUMP_NOT_CONNECTED", Title = "Pompa bağlantısı", Status = "OPEN",
            Description = "Pompa bağlantısı doğrulaması", Cause = "Controlled acceptance check",
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
