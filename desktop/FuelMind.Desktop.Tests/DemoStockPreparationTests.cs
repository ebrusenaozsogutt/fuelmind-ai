using System.Net;
using System.Text;
using System.Text.Json;
using System.Windows.Threading;
using FuelMind.Desktop.Configuration;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using FuelMind.Desktop.ViewModels;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class DemoStockPreparationTests
{
    [Theory]
    [InlineData("null")]
    [InlineData("")]
    public async Task OptionalActiveRunResponseAcceptsJsonNullAndEmptyBody(string body)
    {
        var api = CreateApi(new StaticHandler(body));

        var activeRun = await api.GetOrDefaultAsync<object>("simulations/active?station_id=1");

        Assert.Null(activeRun);
    }

    [Fact]
    public async Task DemoStockPreparationContinuesAfterNoActiveRunAndAcceptsDeliveryDto()
    {
        var store = new LiveDataStore(Dispatcher.CurrentDispatcher) { SelectedStationId = 1 };
        using var socket = new LiveWebSocketService(
            new LiveMessageParser(new JsonSerializerOptions { PropertyNameCaseInsensitive = true }),
            Options.Create(new ApiSettings { BaseUrl = "http://localhost/api/", WebSocketBaseUrl = "ws://127.0.0.1:1/api/ws" }),
            Options.Create(new ConnectionSettings { ReconnectSeconds = 1 }),
            NullLogger<LiveWebSocketService>.Instance,
            store);
        var handler = new DemoStockHandler();
        var viewModel = new SimulatorViewModel(CreateApi(handler), NullLogger<SimulatorViewModel>.Instance, store, socket);

        await viewModel.PrepareDemoStockCommand.ExecuteAsync(null);

        Assert.Null(viewModel.LastError);
        Assert.Equal("1 tank hazırlandı, 0 tank hedef seviyedeydi.", viewModel.StockPreparationResult);
        Assert.True(handler.DeliveryPosted);
        Assert.False(viewModel.IsBusy);
        Assert.True(viewModel.CreateSimulationCommand.CanExecute(null));
    }

    private static ApiClient CreateApi(HttpMessageHandler handler) => new(
        new HttpClient(handler) { BaseAddress = new Uri("http://localhost/api/") },
        new JsonSerializerOptions { PropertyNameCaseInsensitive = true }, new AuthState(), NullLogger<ApiClient>.Instance);

    private sealed class StaticHandler(string body) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
            Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(body, Encoding.UTF8, "application/json") });
    }

    private sealed class DemoStockHandler : HttpMessageHandler
    {
        public bool DeliveryPosted { get; private set; }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var path = request.RequestUri!.AbsolutePath;
            var body = path.EndsWith("/simulations/active")
                ? "null"
                : path.EndsWith("/tanks")
                    ? """[{"id":11,"station_id":1,"fuel_type_id":1,"code":"T-1","capacity_liters":1000,"current_level_liters":400,"minimum_safe_level":200,"critical_level":100,"water_level":0,"temperature":20,"sensor_status":"ACTIVE","is_active":true,"created_at":"2026-08-19T09:00:00Z"}]"""
                    : """{"id":99,"tank_id":11,"delivery_timestamp":"2026-08-19T09:00:00Z","quantity_liters":250,"level_before":400,"level_after":650,"supplier_name":"Demo stock preparation","created_at":"2026-08-19T09:00:00Z"}""";
            if (request.Method == HttpMethod.Post && path.EndsWith("/deliveries")) DeliveryPosted = true;
            return Task.FromResult(new HttpResponseMessage(request.Method == HttpMethod.Post ? HttpStatusCode.Created : HttpStatusCode.OK)
            {
                Content = new StringContent(body, Encoding.UTF8, "application/json"),
            });
        }
    }
}
