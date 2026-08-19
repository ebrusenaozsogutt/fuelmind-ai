using System.Net;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Windows.Threading;
using FuelMind.Desktop.Configuration;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Dtos.Pumps;
using FuelMind.Desktop.Dtos.Simulations;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using FuelMind.Desktop.ViewModels;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class ManualAcceptanceRegressionTests
{
    [Fact]
    public void PumpDto_DeserializesPydanticDecimalStrings()
    {
        var pumps = JsonSerializer.Deserialize<IReadOnlyList<PumpDto>>("""
            [{"id":5,"station_id":2,"tank_id":3,"communication_port_id":1,"code":"PUMP_DIESEL_01","status":"IDLE",
              "nominal_flow_rate":"45.000","minimum_flow_rate":"10.000","maximum_motor_current":"18.000",
              "maximum_pressure":"8.000","total_working_hours":"0.00","is_active":true,"created_at":"2026-08-14T10:00:00Z"}]
            """)!;

        var pump = Assert.Single(pumps);
        Assert.Equal(45m, pump.NominalFlowRate);
        Assert.Equal(10m, pump.MinimumFlowRate);
        Assert.Equal(18m, pump.MaximumMotorCurrent);
        Assert.Equal(8m, pump.MaximumPressure);
    }

    [Fact]
    public void ManualStationSelection_UpdatesGlobalState_AndBuildsStationTwoUri()
    {
        var store = new LiveDataStore(Dispatcher.CurrentDispatcher);
        using var socket = CreateSocket(store);
        var viewModel = new LiveMonitoringViewModel(store, socket);

        viewModel.StationId = 2;

        Assert.Equal(2, store.SelectedStationId);
        var buildUri = typeof(LiveWebSocketService).GetMethod(
            "BuildUri", BindingFlags.Instance | BindingFlags.NonPublic)!;
        var uri = (Uri)buildUri.Invoke(socket, [2])!;
        Assert.Equal("/api/ws/stations/2/live", uri.AbsolutePath);
    }

    [Fact]
    public async Task DashboardSummary_UsesSelectedStation()
    {
        var store = new LiveDataStore(Dispatcher.CurrentDispatcher) { SelectedStationId = 2 };
        var handler = new RecordingHandler("""
            {"station_id":2,"daily_sales_liters":0,"active_alarms":0,"critical_alarms":0,"risky_equipment":0,
             "station_health_score":null,"station_risk_score":null,"station_risk_level":null,
             "high_or_critical_risk_count":0,"most_risky_equipment":null,"last_ai_assessment_at":null}
            """);
        var dashboard = new DashboardViewModel(
            store,
            CreateApiClient(handler),
            new DetailNavigationService());

        await dashboard.RefreshSummaryAsync();

        Assert.Equal("/api/stations/2/dashboard-summary", handler.LastRequestUri?.AbsolutePath);
    }

    [Fact]
    public void FieldTopology_TracksGlobalStation_AndSeparatesErrorFromEmptyState()
    {
        var store = new LiveDataStore(Dispatcher.CurrentDispatcher);
        using var socket = CreateSocket(store);
        var viewModel = new FieldTopologyViewModel(
            store,
            socket,
            new FakeStationService(),
            null!);

        store.SelectedStationId = 2;

        Assert.Equal(2, viewModel.SelectedStationId);
        Assert.True(viewModel.ShowEmptyState);
        viewModel.ErrorMessage = "Topology yüklenemedi.";
        Assert.False(viewModel.ShowEmptyState);
    }

    [Fact]
    public async Task StartingSimulationForStationTwo_UpdatesGlobalSelection()
    {
        var store = new LiveDataStore(Dispatcher.CurrentDispatcher);
        using var socket = CreateSocket(store, "ws://127.0.0.1:1/api/ws");
        var simulator = new SimulatorViewModel(
            CreateApiClient(new SimulationHandler()),
            NullLogger<SimulatorViewModel>.Instance,
            store,
            socket)
        {
            CurrentRun = new SimulationRunDto
            {
                Id = 7,
                StationId = 2,
                Mode = "REALTIME",
                Status = "CREATED",
                SimulationStartTime = DateTimeOffset.UtcNow,
            },
        };

        await simulator.StartCommand.ExecuteAsync(null);

        Assert.Equal(2, store.SelectedStationId);
        Assert.Equal(2, simulator.StationId);
    }

    [Fact]
    public async Task RefreshingSimulator_UsesBackendActiveRunnerAndRefreshesPersistedRun()
    {
        var store = new LiveDataStore(Dispatcher.CurrentDispatcher) { SelectedStationId = 2 };
        using var socket = CreateSocket(store);
        var simulator = new SimulatorViewModel(
            CreateApiClient(new SimulationHandler()),
            NullLogger<SimulatorViewModel>.Instance,
            store,
            socket)
        {
            CurrentRun = new SimulationRunDto
            {
                Id = 7,
                StationId = 2,
                Mode = "REALTIME",
                Status = "RUNNING",
                SimulationStartTime = DateTimeOffset.UtcNow,
            },
        };

        await simulator.RefreshActiveRunAsync();

        Assert.Equal("FAILED", simulator.Status);
        Assert.Null(simulator.ActiveRun);
    }

    private static LiveWebSocketService CreateSocket(
        LiveDataStore store,
        string webSocketBaseUrl = "ws://localhost:8000/api/ws") => new(
        new LiveMessageParser(new JsonSerializerOptions { PropertyNameCaseInsensitive = true }),
        Options.Create(new ApiSettings
        {
            BaseUrl = "http://localhost:8000/api/",
            WebSocketBaseUrl = webSocketBaseUrl,
        }),
        Options.Create(new ConnectionSettings { ReconnectSeconds = 1 }),
        NullLogger<LiveWebSocketService>.Instance,
        store);

    private static ApiClient CreateApiClient(HttpMessageHandler handler) => new(
        new HttpClient(handler) { BaseAddress = new Uri("http://localhost:8000/api/") },
        new JsonSerializerOptions { PropertyNameCaseInsensitive = true },
        new AuthState(),
        NullLogger<ApiClient>.Instance);

    private sealed class FakeStationService : IStationService
    {
        public Task<IReadOnlyList<StationDto>> GetActiveStationsAsync(CancellationToken cancellationToken = default) =>
            Task.FromResult<IReadOnlyList<StationDto>>([]);

        public Task<StationLiveStatusDto> GetLiveStatusAsync(int stationId, CancellationToken cancellationToken = default) =>
            Task.FromResult(new StationLiveStatusDto { StationId = stationId });

        public Task<IReadOnlyList<FuelMind.Desktop.Dtos.Stations.FuelTypeDto>> GetFuelTypesAsync(CancellationToken cancellationToken = default) =>
            Task.FromResult<IReadOnlyList<FuelMind.Desktop.Dtos.Stations.FuelTypeDto>>([]);
    }

    private sealed class RecordingHandler(string response) : HttpMessageHandler
    {
        public Uri? LastRequestUri { get; private set; }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            LastRequestUri = request.RequestUri;
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(response, Encoding.UTF8, "application/json"),
            });
        }
    }

    private sealed class SimulationHandler : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            var body = request.Method == HttpMethod.Post
                ? RunJson("RUNNING")
                : request.RequestUri!.AbsolutePath.EndsWith("/simulations/active")
                    ? "null"
                    : RunJson("FAILED");
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(body, Encoding.UTF8, "application/json"),
            });
        }

        private static string RunJson(string status) => $$"""
            {"id":7,"station_id":2,"mode":"REALTIME","status":"{{status}}","simulation_start_time":"2026-08-14T10:00:00Z","tick_interval_ms":1000,"simulation_step_seconds":5,"speed_multiplier":1,"random_seed":42,"persist_every_n_ticks":1,"sequence_number":0,"generated_sensor_count":0,"generated_sale_count":0,"generated_delivery_count":0,"created_at":"2026-08-14T10:00:00Z","updated_at":"2026-08-14T10:00:00Z"}
            """;
    }
}
