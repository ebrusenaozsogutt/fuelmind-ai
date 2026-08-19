using System.Text.Json;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.State;
using System.Windows.Threading;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class FieldTopologyContractTests
{
    [Fact]
    public void LiveStatus_DeserializesTopologyAndEmptyCollectionsSafely()
    {
        var status = JsonSerializer.Deserialize<StationLiveStatusDto>("""
            { "station_id": 7,
              "controllers": [{ "id": 10, "station_id": 7, "code": "USC-01", "name": "USC", "controller_type": "USC", "status": "ONLINE", "is_active": true }],
              "ports": [{ "id": 11, "controller_id": 10, "port_number": 1, "name": "PORT 1", "port_type": "PUMP", "status": "ONLINE", "is_active": true }],
              "probes": [{ "id": 12, "tank_id": 4, "communication_port_id": 11, "code": "PROBE-1", "name": "Probe", "status": "ONLINE", "is_active": true, "fuel_volume_liters": 18241.5, "quality_flags": [] }],
              "nozzles": [{ "id": 13, "pump_id": 5, "fuel_type_id": 1, "code": "NOZZLE-1", "nozzle_number": 1, "status": "AVAILABLE", "totalizer_liters": 100000.5, "is_active": true, "fuel_type_code": "DIESEL" }] }
            """)!;

        var empty = JsonSerializer.Deserialize<StationLiveStatusDto>("{ \"station_id\": 8 }")!;

        Assert.Equal(10, Assert.Single(status.Controllers).Id);
        Assert.Equal(11, Assert.Single(status.Ports).Id);
        Assert.Equal(18241.5m, Assert.Single(status.Probes).FuelVolumeLiters);
        Assert.Equal(100000.5m, Assert.Single(status.Nozzles).TotalizerLiters);
        Assert.Empty(empty.Controllers);
        Assert.Empty(empty.Ports);
        Assert.Empty(empty.Probes);
        Assert.Empty(empty.Nozzles);
    }

    [Fact]
    public void SimulationTick_UpdatesTopologyById()
    {
        var tick = JsonSerializer.Deserialize<SimulationTickDto>("""
            { "event_type": "simulation_tick", "simulation_run_id": 1, "station_id": 7, "simulation_time": "2026-08-14T10:00:00Z", "generated_at": "2026-08-14T10:00:00Z", "sequence": 1,
              "pumps": [{ "pump_id": 5, "tank_id": 4, "communication_port_id": 11, "status": "ACTIVE" }],
              "controllers": [{ "id": 10, "station_id": 7, "code": "USC-01", "name": "USC", "controller_type": "USC", "status": "ONLINE", "is_active": true }],
              "ports": [{ "id": 11, "controller_id": 10, "port_number": 1, "name": "PORT 1", "port_type": "PUMP", "status": "ONLINE", "is_active": true }],
              "probes": [{ "id": 12, "tank_id": 4, "communication_port_id": 11, "code": "PROBE-1", "name": "Probe", "status": "ONLINE", "is_active": true, "fuel_volume_liters": 18000.0, "temperature_celsius": 19.5, "quality_flags": [] }],
              "nozzles": [{ "id": 13, "pump_id": 5, "fuel_type_id": 1, "code": "NOZZLE-1", "nozzle_number": 1, "status": "DISPENSING", "totalizer_liters": 100000.0, "is_active": true }],
              "tanks": [], "sales": [], "events": [], "active_scenarios": [], "ai_results": [] }
            """)!;
        var updatedTick = JsonSerializer.Deserialize<SimulationTickDto>("""
            { "event_type": "simulation_tick", "simulation_run_id": 1, "station_id": 7, "simulation_time": "2026-08-14T10:00:01Z", "generated_at": "2026-08-14T10:00:01Z", "sequence": 2,
              "controllers": [{ "id": 10, "station_id": 7, "code": "USC-01", "name": "USC", "controller_type": "USC", "status": "ONLINE", "is_active": true }],
              "ports": [{ "id": 11, "controller_id": 10, "port_number": 1, "name": "PORT 1", "port_type": "PUMP", "status": "ONLINE", "is_active": true }],
              "probes": [{ "id": 12, "tank_id": 4, "communication_port_id": 11, "code": "PROBE-1", "name": "Probe", "status": "ONLINE", "is_active": true, "fuel_volume_liters": 17990.0, "temperature_celsius": 19.7, "quality_flags": ["OK"] }],
              "nozzles": [{ "id": 13, "pump_id": 5, "fuel_type_id": 1, "code": "NOZZLE-1", "nozzle_number": 1, "status": "AVAILABLE", "totalizer_liters": 100042.9, "is_active": true }],
              "tanks": [], "pumps": [{ "pump_id": 5, "tank_id": 4, "communication_port_id": 11, "status": "IDLE" }], "sales": [], "events": [], "active_scenarios": [], "ai_results": [] }
            """)!;
        var dispatcher = Dispatcher.CurrentDispatcher;
        var previousContext = SynchronizationContext.Current;
        SynchronizationContext.SetSynchronizationContext(new DispatcherSynchronizationContext(dispatcher));
        try
        {
            var store = new LiveDataStore(dispatcher);
            store.ApplySimulationTick(tick);
            Assert.Single(store.Nozzles);
            Assert.Single(store.Probes);

            store.ApplySimulationTick(updatedTick);

            Assert.Single(store.Nozzles);
            Assert.Equal("AVAILABLE", store.Nozzles[0].Status);
            Assert.Equal(100042.9m, store.Nozzles[0].TotalizerLiters);
            Assert.Single(store.Probes);
            Assert.Equal(17990.0m, store.Probes[0].FuelVolumeLiters);
            Assert.Equal(19.7m, store.Probes[0].TemperatureCelsius);
            Assert.Equal(11, Assert.Single(store.Pumps).CommunicationPortId);
        }
        finally
        {
            SynchronizationContext.SetSynchronizationContext(previousContext);
        }
    }
}
