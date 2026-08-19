using System.Text.Json;
using System.Text.Json.Serialization;
using FuelMind.Desktop.Dtos.Commercial;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class CommercialDtoContractTests
{
    [Fact]
    public void CommercialDtos_deserialize_backend_decimal_and_enum_contracts()
    {
        var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true, NumberHandling = JsonNumberHandling.AllowReadingFromString };
        var customer = JsonSerializer.Deserialize<CustomerReadDto>("""{"id":1,"code":"C-1","name":"Demo","customer_type":"COMPANY","discount_rate":"3.00","request_status":"APPROVED","is_active":true,"registration_date":"2026-08-17"}""", options);
        var card = JsonSerializer.Deserialize<FuelCardReadDto>("""{"id":2,"vehicle_id":3,"card_code":"CARD","display_name":"Demo","unit_id":"UNIT","status":"ACTIVE","payment_type":"CREDIT","prepaid_balance":"0","credit_limit":"5000.00","credit_used":"1000.00","is_active":true}""", options);
        var price = JsonSerializer.Deserialize<FuelPriceReadDto>("""{"id":4,"station_id":2,"fuel_type_id":1,"unit_price":"55.0000","effective_from":"2026-08-17T00:00:00+00:00","effective_until":null,"is_active":true}""", options);
        var sale = JsonSerializer.Deserialize<SaleReadDto>("""{"id":5,"sale_status":"COMPLETED","customer_id":1,"vehicle_id":3,"fuel_card_id":2,"nozzle_id":7,"sale_timestamp":"2026-08-17T10:00:00+00:00","quantity_liters":"40.500","list_unit_price":"55.0000","discount_rate":"3.00","unit_price":"53.3500","total_amount":"2160.68","start_totalizer_liters":"100000.000","end_totalizer_liters":"100040.500","payment_type":"PREPAID"}""", options);

        Assert.Equal("COMPANY", customer!.CustomerType);
        Assert.Equal(4000m, card!.AvailableCredit);
        Assert.Equal(55m, price!.UnitPrice);
        Assert.Equal(2160.68m, sale!.TotalAmount);
        Assert.Equal(100040.500m, sale.EndTotalizerLiters);
    }

    [Fact]
    public void Commercial_configuration_dtos_deserialize_date_time_and_decimal_values()
    {
        var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
        var limit = JsonSerializer.Deserialize<FuelCardLimitReadDto>("""{"id":1,"fuel_card_id":2,"limit_type":"DAILY","quantity_limit_liters":350.500,"valid_from":null,"valid_until":null,"is_active":true}""", options);
        var window = JsonSerializer.Deserialize<FuelCardUsageWindowDto>("""{"id":3,"fuel_card_id":2,"day_of_week":1,"start_time":"08:00:00","end_time":"18:00:00","is_active":true}""", options);

        Assert.Equal(350.5m, limit!.QuantityLimitLiters);
        Assert.Equal(new TimeOnly(8, 0), window!.StartTime);
    }

    [Fact]
    public void Commercial_update_dtos_serialize_only_real_backend_field_names()
    {
        var card = JsonSerializer.Serialize(new FuelCardSaveDto { VehicleId = 4, DisplayName = "Kart", CardCode = "K-1", UnitId = "UNIT-1", Status = "ACTIVE", ValidFrom = new DateOnly(2026, 8, 17), PaymentType = "CREDIT", CreditLimit = 5000, IsActive = true });
        var person = JsonSerializer.Serialize(new CustomerAuthorizedPersonSaveDto { CustomerId = 2, FullName = "Ada Lovelace", IsPrimary = true });
        var assignment = JsonSerializer.Serialize(new DriverVehicleAssignmentSaveDto { DriverId = 3, VehicleId = 4, AssignedFrom = new DateOnly(2026, 8, 17), Status = "ACTIVE" });

        Assert.Contains("\"vehicle_id\":4", card);
        Assert.Contains("\"credit_limit\":5000", card);
        Assert.Contains("\"customer_id\":2", person);
        Assert.Contains("\"assigned_from\":\"2026-08-17\"", assignment);
    }
}
