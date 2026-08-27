using System.Net;
using System.Text;
using System.Text.Json;
using FuelMind.Desktop.Dtos.Auth;
using FuelMind.Desktop.Dtos.Forecasts;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Dtos.Orders;
using FuelMind.Desktop.Dtos.Tanks;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using FuelMind.Desktop.ViewModels;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.DependencyInjection;
using System.Reflection;
using System.IO;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class ForecastOrderAcceptanceTests
{
    [Fact]
    public async Task Forecast_service_parses_latest_performance_and_generate_request()
    {
        var handler = new RouterHandler(); var service = new ForecastService(Api(handler));
        var latest = await service.GetLatestForecastsAsync(2, 4);
        var performance = await service.GetPerformanceAsync();
        await service.GenerateForecastAsync(2, 4);
        Assert.Single(latest); Assert.Equal(88.25m, latest[0].ConfidenceScore);
        Assert.Equal("baseline", performance!.Winner);
        Assert.Contains("forecasts/generate?station_id=2&fuel_type_id=4", handler.Paths);
    }

    [Fact]
    public async Task Order_service_parses_order_and_no_order_and_propagates_errors()
    {
        var service = new OrderRecommendationService(Api(new RouterHandler()));
        var order = await service.GetTankRecommendationAsync(1);
        var noOrder = await service.GenerateTankRecommendationAsync(2);
        Assert.True(order.RecommendedQuantity > 0); Assert.Equal(0, noOrder.RecommendedQuantity);
        await Assert.ThrowsAsync<ApiException>(() => service.GetTankRecommendationAsync(404));
    }

    [Fact]
    public async Task Forecast_view_model_loads_seven_rows_metrics_baseline_and_empty_state()
    {
        var vm = new ForecastsViewModel(new FakeForecasts(), new FakeStations(), Admin());
        await vm.LoadAsync();
        Assert.Equal(7, vm.Forecasts.Count); Assert.False(vm.IsLoading); Assert.Equal("7 Günlük Hareketli Ortalama", vm.ModelDisplay); Assert.Equal(80m, vm.AverageConfidence);
        var empty = new ForecastsViewModel(new FakeForecasts(empty: true), new FakeStations(), Admin());
        await empty.LoadAsync(); Assert.True(empty.IsEmpty);
    }

    [Fact]
    public async Task Forecast_view_model_selects_the_first_series_returned_by_the_backend()
    {
        var vm = new ForecastsViewModel(new FakeForecasts(fuelTypeId: 4), new FakeStations(3, 4, 5), Admin());

        await vm.LoadAsync();

        Assert.Equal(4, vm.SelectedFuelType!.Id);
        Assert.Equal(7, vm.Forecasts.Count);
        Assert.Equal(7, vm.ChartValues.Count);
        Assert.Equal(7, vm.Labels.Count);
        Assert.True(vm.AverageConfidence > 0);
        Assert.False(vm.IsEmpty);
    }

    [Fact]
    public async Task Forecast_view_model_surfaces_user_safe_error()
    {
        var vm = new ForecastsViewModel(new FakeForecasts(fail: true), new FakeStations(), Admin());
        await vm.LoadAsync(); Assert.Equal("Tahmin verileri alınamadı.", vm.ErrorMessage); Assert.False(vm.IsLoading);
    }

    [Fact]
    public async Task Orders_view_model_loads_order_states_priority_confidence_and_tank_change()
    {
        var orders = new FakeOrders();
        var vm = new OrdersViewModel(orders, new FakeStations(), Api(new TankHandler()), Admin());
        await vm.LoadAsync();
        Assert.True(vm.HasOrder); Assert.False(vm.NoOrderRequired); Assert.Equal("Kritik", vm.PriorityDisplay); Assert.Equal(88m, vm.Recommendation!.ConfidenceScore); Assert.Equal(6190.946m, vm.DisplayedCurrentStock); Assert.Equal(6250m, vm.DisplayedMinimumSafeStock); Assert.False(vm.IsLoading);
        vm.SelectedTank = vm.Tanks.Single(t => t.Id == 2);
        await Task.Delay(20);
        Assert.True(vm.NoOrderRequired); Assert.False(vm.HasOrder); Assert.Equal("Düşük", vm.PriorityDisplay);
        Assert.Equal([1, 2], orders.RequestedTankIds);
    }

    [Theory]
    [InlineData("LOW", "Düşük")]
    [InlineData("MEDIUM", "Orta")]
    [InlineData("HIGH", "Yüksek")]
    [InlineData("CRITICAL", "Kritik")]
    public async Task Orders_view_model_maps_each_priority(string priority, string expected)
    {
        var vm = new OrdersViewModel(new FakeOrders(priority), new FakeStations(), Api(new TankHandler()), Admin());
        await vm.LoadAsync(); Assert.Equal(expected, vm.PriorityDisplay);
    }

    [Fact]
    public async Task Orders_view_model_surfaces_error_and_clears_loading()
    {
        var vm = new OrdersViewModel(new FakeOrders(fail: true), new FakeStations(), Api(new TankHandler()), Admin());
        await vm.LoadAsync(); Assert.Equal("Sipariş önerisi alınamadı.", vm.ErrorMessage); Assert.False(vm.IsLoading);
    }

    [Fact]
    public void Navigation_registers_real_forecast_and_order_view_models_and_templates()
    {
        var services = new ServiceCollection();
        typeof(FuelMind.Desktop.App).GetMethod("ConfigureServices", BindingFlags.Static | BindingFlags.NonPublic)!.Invoke(null, [services]);
        using var provider = services.BuildServiceProvider();
        Assert.NotNull(provider.GetService<ForecastsViewModel>());
        Assert.NotNull(provider.GetService<OrdersViewModel>());
        var desktopProjectRoot = Path.Combine(FindRepositoryRoot(), "desktop", "FuelMind.Desktop");
        var markup = File.ReadAllText(Path.Combine(desktopProjectRoot, "Views", "MainWindow.xaml"));
        Assert.Contains("ForecastsViewModel", markup); Assert.Contains("OrdersViewModel", markup);
        var shell = File.ReadAllText(Path.Combine(desktopProjectRoot, "ViewModels", "AuthenticatedShellViewModel.cs"));
        Assert.DoesNotContain("ShowPlaceholder(\"Tahminler\")", shell); Assert.DoesNotContain("ShowPlaceholder(\"Sipariş Önerileri\")", shell);
    }

    private static string FindRepositoryRoot()
    {
        for (var directory = new DirectoryInfo(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            if (File.Exists(Path.Combine(directory.FullName, "desktop", "FuelMind.sln")))
            {
                return directory.FullName;
            }
        }

        throw new DirectoryNotFoundException("Repository root containing desktop/FuelMind.sln was not found.");
    }

    private static ApiClient Api(HttpMessageHandler handler) => new(new HttpClient(handler) { BaseAddress = new Uri("http://localhost/api/") }, new JsonSerializerOptions { PropertyNameCaseInsensitive = true }, new AuthState(), NullLogger<ApiClient>.Instance);
    private static AuthState Admin() { var auth = new AuthState(); auth.SetCurrentUser(new CurrentUserResponseDto { Id = 1, Username = "admin", FullName = "Admin", Role = "ADMIN", IsActive = true }); return auth; }

    private sealed class FakeStations : IStationService
    {
        private readonly int[] _fuelTypeIds;
        public FakeStations(params int[] fuelTypeIds) => _fuelTypeIds = fuelTypeIds.Length == 0 ? [1] : fuelTypeIds;
        public Task<IReadOnlyList<StationDto>> GetActiveStationsAsync(CancellationToken ct = default) => Task.FromResult<IReadOnlyList<StationDto>>([new() { Id=1, Code="S", Name="Station", City="K", District="K", Address="A" }]);
        public Task<IReadOnlyList<FuelTypeDto>> GetFuelTypesAsync(CancellationToken ct = default) => Task.FromResult<IReadOnlyList<FuelTypeDto>>(_fuelTypeIds.Select(id => new FuelTypeDto { Id=id, Code=$"FUEL-{id}", Name=$"Yakıt {id}" }).ToArray());
        public Task<FuelMind.Desktop.Dtos.Live.StationLiveStatusDto> GetLiveStatusAsync(int id, CancellationToken ct = default) => throw new NotImplementedException();
    }
    private sealed class FakeForecasts(bool empty = false, bool fail = false, int fuelTypeId = 1) : IForecastService
    {
        public Task<IReadOnlyList<ForecastDto>> GetLatestForecastsAsync(int stationId, int? selectedFuelTypeId = null, CancellationToken ct = default) { if (fail) throw new HttpRequestException(); return Task.FromResult<IReadOnlyList<ForecastDto>>(empty ? [] : Enumerable.Range(1,7).Select(i => new ForecastDto { ForecastDate = new DateOnly(2026,12,i), StationId=1, FuelTypeId=fuelTypeId, PredictedDemand=100, LowerBound=90, UpperBound=110, ConfidenceScore=80, ModelVersion="baseline:seven_day_moving_average" }).ToArray()); }
        public Task<ForecastPerformanceDto?> GetPerformanceAsync(CancellationToken ct = default) => Task.FromResult<ForecastPerformanceDto?>(new() { Winner="baseline", ModelType="seven_day_moving_average", ModelVersion="baseline:seven_day_moving_average", Mae=2, Rmse=3 });
        public Task<IReadOnlyList<ForecastDto>> GenerateForecastAsync(int stationId, int? fuelTypeId = null, CancellationToken ct = default) => GetLatestForecastsAsync(stationId, fuelTypeId, ct);
    }
    private sealed class FakeOrders(string? priority = null, bool fail = false) : IOrderRecommendationService
    {
        public List<int> RequestedTankIds { get; } = [];
        public Task<OrderRecommendationDto> GetTankRecommendationAsync(int tankId, CancellationToken ct = default) { if (fail) throw new HttpRequestException(); RequestedTankIds.Add(tankId); return Task.FromResult(new OrderRecommendationDto { TankId=tankId, StationId=1, CurrentStockLiters=tankId == 2 ? 400m : 6190.946m, MinimumSafeStockLiters=tankId == 2 ? 300m : 6250m, RecommendedQuantity=tankId == 2 ? 0 : 154m, RecommendedOrderDate=new DateOnly(2026,12,2), RecommendedDeliveryDate=new DateOnly(2026,12,4), ConfidenceScore=88m, Priority=priority ?? (tankId == 2 ? "LOW" : "CRITICAL"), Explanation="Sipariş gerekmiyor" }); }
        public Task<OrderRecommendationDto> GenerateTankRecommendationAsync(int tankId, CancellationToken ct = default) => GetTankRecommendationAsync(tankId, ct);
    }
    private sealed class TankHandler : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct) => Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent("[{\"id\":1,\"station_id\":1,\"fuel_type_id\":1,\"code\":\"T-1\",\"capacity_liters\":1000,\"current_level_liters\":700,\"minimum_safe_level\":300,\"critical_level\":100,\"water_level\":0,\"sensor_status\":\"ACTIVE\",\"is_active\":true,\"created_at\":\"2026-01-01T00:00:00Z\"},{\"id\":2,\"station_id\":1,\"fuel_type_id\":1,\"code\":\"T-2\",\"capacity_liters\":1000,\"current_level_liters\":400,\"minimum_safe_level\":300,\"critical_level\":100,\"water_level\":0,\"sensor_status\":\"ACTIVE\",\"is_active\":true,\"created_at\":\"2026-01-01T00:00:00Z\"}]", Encoding.UTF8, "application/json") });
    }
    private sealed class RouterHandler : HttpMessageHandler
    {
        public List<string> Paths { get; } = [];
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct) { var path = request.RequestUri!.PathAndQuery.TrimStart('/').Replace("api/", ""); Paths.Add(path); if (path.Contains("404")) return Task.FromResult(new HttpResponseMessage(HttpStatusCode.NotFound) { Content = Json("{\"error\":{\"code\":\"RESOURCE_NOT_FOUND\",\"message\":\"not found\"}}") }); if (path.StartsWith("forecasts/performance")) return Task.FromResult(Ok("{\"winner\":\"baseline\",\"model_type\":\"seven_day_moving_average\",\"model_version\":\"baseline:seven_day_moving_average\",\"mae\":1,\"rmse\":2,\"training_row_count\":90}")); if (path.StartsWith("forecasts")) return Task.FromResult(Ok("[{\"forecast_date\":\"2026-12-03\",\"station_id\":2,\"fuel_type_id\":4,\"predicted_demand\":120,\"lower_bound\":100,\"upper_bound\":140,\"confidence_score\":88.25,\"model_version\":\"baseline:seven_day_moving_average\"}]")); return Task.FromResult(Ok(path.Contains("/2/") ? "{\"tank_id\":2,\"station_id\":1,\"current_stock_liters\":400,\"minimum_safe_stock_liters\":300,\"recommended_quantity\":0,\"recommended_order_date\":\"2026-12-02\",\"recommended_delivery_date\":\"2026-12-04\",\"confidence_score\":88,\"priority\":\"LOW\",\"status\":\"NEW\"}" : "{\"tank_id\":1,\"station_id\":1,\"current_stock_liters\":6190.946,\"minimum_safe_stock_liters\":6250,\"recommended_quantity\":154.3,\"recommended_order_date\":\"2026-12-02\",\"recommended_delivery_date\":\"2026-12-04\",\"confidence_score\":88,\"priority\":\"CRITICAL\",\"status\":\"NEW\"}")); }
        private static HttpResponseMessage Ok(string body) => new(HttpStatusCode.OK) { Content = Json(body) }; private static StringContent Json(string body) => new(body, Encoding.UTF8, "application/json");
    }
}
