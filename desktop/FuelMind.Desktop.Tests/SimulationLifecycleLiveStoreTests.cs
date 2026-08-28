using System.Windows.Threading;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.State;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class SimulationLifecycleLiveStoreTests
{
    [Fact]
    public void BeginSimulationRun_ClearsOldTelemetry_AndRejectsOldRunPackets()
    {
        var store = new LiveDataStore(Dispatcher.CurrentDispatcher);
        store.ApplySimulationTick(Tick(runId: 41, sequence: 10, level: 740));
        Assert.Single(store.Tanks);

        store.BeginSimulationRun(stationId: 7, runId: 42);

        Assert.Equal(42, store.ExpectedSimulationRunId);
        Assert.Equal(42, store.LastSimulationRunId);
        Assert.Null(store.LastSequence);
        Assert.Empty(store.Tanks);
        Assert.Empty(store.Pumps);

        store.ApplySimulationTick(Tick(runId: 41, sequence: 11, level: 730));

        Assert.Null(store.LastSequence);
        Assert.Empty(store.Tanks);
        Assert.Empty(store.Pumps);

        store.ApplySimulationTick(Tick(runId: 42, sequence: 1, level: 700));

        Assert.Equal(1, store.LastSequence);
        Assert.Equal(42, store.LastSimulationRunId);
        Assert.Equal(700m, Assert.Single(store.Tanks).MeasuredLevelLiters);
    }

    [Fact]
    public void ResumeOfExpectedRun_ContinuesStateWithoutClearingCollections()
    {
        var store = new LiveDataStore(Dispatcher.CurrentDispatcher);
        store.BeginSimulationRun(stationId: 7, runId: 51);
        store.ApplySimulationTick(Tick(runId: 51, sequence: 10, level: 650));

        store.ApplySimulationTick(Tick(runId: 51, sequence: 11, level: 640));

        Assert.Equal(51, store.ExpectedSimulationRunId);
        Assert.Equal(11, store.LastSequence);
        Assert.Equal(640m, Assert.Single(store.Tanks).MeasuredLevelLiters);
        Assert.Equal("ACTIVE", Assert.Single(store.Pumps).Status);
    }

    private static SimulationTickDto Tick(int runId, int sequence, decimal level) => new()
    {
        SimulationRunId = runId,
        StationId = 7,
        SimulationTime = new DateTimeOffset(2026, 8, 28, 12, 0, 0, TimeSpan.Zero),
        GeneratedAt = new DateTimeOffset(2026, 8, 28, 12, 0, 0, TimeSpan.Zero),
        Sequence = sequence,
        Tanks = [new TankLiveDataDto { TankId = 3, Code = "T-3", CapacityLiters = 1_000, MeasuredLevelLiters = level }],
        Pumps = [new PumpLiveDataDto { PumpId = 4, TankId = 3, Status = "ACTIVE" }],
    };
}
