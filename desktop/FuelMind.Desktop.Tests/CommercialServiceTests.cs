using System.Net;
using System.Text;
using System.Text.Json;
using FuelMind.Desktop.Dtos.Auth;
using FuelMind.Desktop.Dtos.Commercial;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class CommercialServiceTests
{
    [Fact]
    public async Task Customers_deserializes_the_backend_list_contract_with_optional_fields()
    {
        var handler = new RecordingHandler("""[{"id":7,"code":"C-007","name":"Örnek Lojistik","customer_type":"COMPANY","sector":null,"tax_number":null,"tax_office":null,"phone":null,"email":null,"address":null,"registration_date":"2026-08-25","discount_rate":2.50,"request_status":"APPROVED","is_active":true,"created_at":"2026-08-25T09:30:00Z","updated_at":"2026-08-25T09:30:00Z"}]""");
        var service = CreateService(handler);

        var customers = await service.GetCustomersAsync();

        var customer = Assert.Single(customers);
        Assert.Equal(7, customer.Id);
        Assert.Equal("C-007", customer.Code);
        Assert.Null(customer.Email);
        Assert.Null(customer.TaxNumber);
        Assert.Equal(new DateOnly(2026, 8, 25), customer.RegistrationDate);
        Assert.Equal(2.50m, customer.DiscountRate);
    }

    [Fact]
    public async Task Sales_filter_uses_single_query_string_without_empty_parameters()
    {
        var handler = new RecordingHandler("[]");
        var service = CreateService(handler);

        await service.GetSalesAsync(customerId: 3, fuelCardId: 7);

        Assert.Equal(HttpMethod.Get, handler.Method);
        Assert.Equal("/api/sales?customer_id=3&fuel_card_id=7", handler.PathAndQuery);
    }

    [Fact]
    public async Task Authorization_preview_posts_backend_snake_case_contract()
    {
        var handler = new RecordingHandler("""{"authorized":true,"decision_code":"AUTHORIZED","message":"OK"}""");
        var service = CreateService(handler);

        var response = await service.PreviewAuthorizationAsync(new FuelCardAuthorizationRequestDto
        {
            UnitId = "UNIT-1", VehicleId = 2, StationId = 3, FuelTypeId = 4, RequestedQuantityLiters = 25.5m,
        });

        Assert.Equal(HttpMethod.Post, handler.Method);
        Assert.Equal("/api/fuel-cards/authorize", handler.PathAndQuery);
        using var body = JsonDocument.Parse(handler.Body!);
        Assert.Equal("UNIT-1", body.RootElement.GetProperty("unit_id").GetString());
        Assert.Equal(25.5m, body.RootElement.GetProperty("requested_quantity_liters").GetDecimal());
        Assert.True(response.Authorized);
    }

    [Fact]
    public async Task Price_history_uses_station_scoped_endpoint()
    {
        var handler = new RecordingHandler("[]");
        var service = CreateService(handler);

        await service.GetFuelPriceHistoryAsync(5, 8);

        Assert.Equal("/api/stations/5/fuel-prices/8/history", handler.PathAndQuery);
    }

    [Fact]
    public async Task Usage_window_crud_uses_existing_soft_deactivate_routes()
    {
        var handler = new RecordingHandler("""{"id":3,"fuel_card_id":2,"day_of_week":0,"start_time":"08:00:00","end_time":"18:00:00","is_active":true}""");
        var service = CreateService(handler);
        var request = new FuelCardUsageWindowSaveDto { FuelCardId = 2, DayOfWeek = 0, StartTime = new TimeOnly(8, 0), EndTime = new TimeOnly(18, 0), IsActive = true };

        await service.CreateUsageWindowAsync(request);
        Assert.Equal(HttpMethod.Post, handler.Method); Assert.Equal("/api/fuel-card-usage-windows", handler.PathAndQuery);
        await service.UpdateUsageWindowAsync(3, request);
        Assert.Equal(HttpMethod.Put, handler.Method); Assert.Equal("/api/fuel-card-usage-windows/3", handler.PathAndQuery);
        await service.DeactivateUsageWindowAsync(3);
        Assert.Equal(HttpMethod.Delete, handler.Method); Assert.Equal("/api/fuel-card-usage-windows/3", handler.PathAndQuery);
    }

    private static CommercialService CreateService(RecordingHandler handler)
    {
        var auth = new AuthState();
        auth.SetAuthentication(new TokenResponseDto { AccessToken = "test-token", TokenType = "Bearer", ExpiresIn = 3600 });
        var api = new ApiClient(new HttpClient(handler) { BaseAddress = new Uri("http://localhost/api/") }, new JsonSerializerOptions { PropertyNameCaseInsensitive = true }, auth, NullLogger<ApiClient>.Instance);
        return new CommercialService(api);
    }

    private sealed class RecordingHandler(string responseJson) : HttpMessageHandler
    {
        public HttpMethod? Method { get; private set; }
        public string? PathAndQuery { get; private set; }
        public string? Body { get; private set; }
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Method = request.Method; PathAndQuery = request.RequestUri?.PathAndQuery;
            Body = request.Content is null ? null : await request.Content.ReadAsStringAsync(cancellationToken);
            return new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(responseJson, Encoding.UTF8, "application/json") };
        }
    }
}
