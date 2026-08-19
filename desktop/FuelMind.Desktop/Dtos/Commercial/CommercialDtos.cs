using System.Text.Json.Serialization;

namespace FuelMind.Desktop.Dtos.Commercial;

// API enum values are kept as strings deliberately. The desktop client must not
// silently turn a newly-added backend enum into an invalid local default.
public sealed class CustomerReadDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("code")] public required string Code { get; init; }
    [JsonPropertyName("name")] public required string Name { get; init; }
    [JsonPropertyName("customer_type")] public required string CustomerType { get; init; }
    [JsonPropertyName("sector")] public string? Sector { get; init; }
    [JsonPropertyName("tax_number")] public string? TaxNumber { get; init; }
    [JsonPropertyName("tax_office")] public string? TaxOffice { get; init; }
    [JsonPropertyName("phone")] public string? Phone { get; init; }
    [JsonPropertyName("email")] public string? Email { get; init; }
    [JsonPropertyName("discount_rate")] public decimal DiscountRate { get; init; }
    [JsonPropertyName("request_status")] public required string RequestStatus { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    [JsonPropertyName("registration_date")] public DateOnly RegistrationDate { get; init; }
}

public sealed class CustomerSaveDto
{
    [JsonPropertyName("code")] public string? Code { get; init; }
    [JsonPropertyName("name")] public string? Name { get; init; }
    [JsonPropertyName("customer_type")] public string? CustomerType { get; init; }
    [JsonPropertyName("sector")] public string? Sector { get; init; }
    [JsonPropertyName("tax_number")] public string? TaxNumber { get; init; }
    [JsonPropertyName("tax_office")] public string? TaxOffice { get; init; }
    [JsonPropertyName("phone")] public string? Phone { get; init; }
    [JsonPropertyName("email")] public string? Email { get; init; }
    [JsonPropertyName("address")] public string? Address { get; init; }
    [JsonPropertyName("registration_date")] public DateOnly? RegistrationDate { get; init; }
    [JsonPropertyName("discount_rate")] public decimal? DiscountRate { get; init; }
    [JsonPropertyName("request_status")] public string? RequestStatus { get; init; }
    [JsonPropertyName("is_active")] public bool? IsActive { get; init; }
}

public sealed class CustomerAuthorizedPersonReadDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("customer_id")] public int CustomerId { get; init; }
    [JsonPropertyName("full_name")] public required string FullName { get; init; }
    [JsonPropertyName("title")] public string? Title { get; init; }
    [JsonPropertyName("phone")] public string? Phone { get; init; }
    [JsonPropertyName("email")] public string? Email { get; init; }
    [JsonPropertyName("is_primary")] public bool IsPrimary { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
}

public sealed class CustomerAuthorizedPersonSaveDto
{
    [JsonPropertyName("customer_id")] public int? CustomerId { get; init; }
    [JsonPropertyName("full_name")] public string? FullName { get; init; }
    [JsonPropertyName("title")] public string? Title { get; init; }
    [JsonPropertyName("phone")] public string? Phone { get; init; }
    [JsonPropertyName("email")] public string? Email { get; init; }
    [JsonPropertyName("is_primary")] public bool? IsPrimary { get; init; }
    [JsonPropertyName("is_active")] public bool? IsActive { get; init; }
}

public sealed class FleetReadDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("customer_id")] public int CustomerId { get; init; }
    [JsonPropertyName("code")] public required string Code { get; init; }
    [JsonPropertyName("name")] public required string Name { get; init; }
    [JsonPropertyName("description")] public string? Description { get; init; }
    [JsonPropertyName("request_status")] public string? RequestStatus { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
}
public sealed class FleetSaveDto
{
    [JsonPropertyName("customer_id")] public int? CustomerId { get; init; }
    [JsonPropertyName("code")] public string? Code { get; init; }
    [JsonPropertyName("name")] public string? Name { get; init; }
    [JsonPropertyName("description")] public string? Description { get; init; }
    [JsonPropertyName("request_status")] public string? RequestStatus { get; init; }
    [JsonPropertyName("is_active")] public bool? IsActive { get; init; }
}

public sealed class FleetGroupReadDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("fleet_id")] public int FleetId { get; init; }
    [JsonPropertyName("code")] public required string Code { get; init; }
    [JsonPropertyName("name")] public required string Name { get; init; }
    [JsonPropertyName("description")] public string? Description { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
}
public sealed class FleetGroupSaveDto
{
    [JsonPropertyName("fleet_id")] public int? FleetId { get; init; }
    [JsonPropertyName("code")] public string? Code { get; init; }
    [JsonPropertyName("name")] public string? Name { get; init; }
    [JsonPropertyName("description")] public string? Description { get; init; }
    [JsonPropertyName("is_active")] public bool? IsActive { get; init; }
}

public sealed class VehicleReadDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("fleet_group_id")] public int FleetGroupId { get; init; }
    [JsonPropertyName("plate")] public required string Plate { get; init; }
    [JsonPropertyName("brand")] public string? Brand { get; init; }
    [JsonPropertyName("model")] public string? Model { get; init; }
    [JsonPropertyName("vehicle_type")] public string? VehicleType { get; init; }
    [JsonPropertyName("description")] public string? Description { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    [JsonIgnore] public bool HasActiveFuelCard { get; set; }
    [JsonIgnore] public string CardSelectionLabel => HasActiveFuelCard ? $"{Plate} — Aktif kart mevcut" : Plate;
}
public sealed class VehicleSaveDto
{
    [JsonPropertyName("fleet_group_id")] public int? FleetGroupId { get; init; }
    [JsonPropertyName("plate")] public string? Plate { get; init; }
    [JsonPropertyName("brand")] public string? Brand { get; init; }
    [JsonPropertyName("model")] public string? Model { get; init; }
    [JsonPropertyName("vehicle_type")] public string? VehicleType { get; init; }
    [JsonPropertyName("description")] public string? Description { get; init; }
    [JsonPropertyName("is_active")] public bool? IsActive { get; init; }
}

public sealed class DriverReadDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("full_name")] public required string FullName { get; init; }
    [JsonPropertyName("reference_code")] public string? ReferenceCode { get; init; }
    [JsonPropertyName("phone")] public string? Phone { get; init; }
    [JsonPropertyName("license_number")] public string? LicenseNumber { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
}
public sealed class DriverSaveDto
{
    [JsonPropertyName("full_name")] public string? FullName { get; init; }
    [JsonPropertyName("reference_code")] public string? ReferenceCode { get; init; }
    [JsonPropertyName("phone")] public string? Phone { get; init; }
    [JsonPropertyName("license_number")] public string? LicenseNumber { get; init; }
    [JsonPropertyName("is_active")] public bool? IsActive { get; init; }
}

public sealed class DriverVehicleAssignmentReadDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("driver_id")] public int DriverId { get; init; }
    [JsonPropertyName("vehicle_id")] public int VehicleId { get; init; }
    [JsonPropertyName("assigned_from")] public DateOnly AssignedFrom { get; init; }
    [JsonPropertyName("assigned_until")] public DateOnly? AssignedUntil { get; init; }
    [JsonPropertyName("status")] public required string Status { get; init; }
}
public sealed class DriverVehicleAssignmentSaveDto
{
    [JsonPropertyName("driver_id")] public int? DriverId { get; init; }
    [JsonPropertyName("vehicle_id")] public int? VehicleId { get; init; }
    [JsonPropertyName("assigned_from")] public DateOnly? AssignedFrom { get; init; }
    [JsonPropertyName("assigned_until")] public DateOnly? AssignedUntil { get; init; }
    [JsonPropertyName("status")] public string? Status { get; init; }
}

public sealed class FuelCardReadDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("vehicle_id")] public int VehicleId { get; init; }
    [JsonPropertyName("card_code")] public required string CardCode { get; init; }
    [JsonPropertyName("display_name")] public required string DisplayName { get; init; }
    [JsonPropertyName("unit_id")] public required string UnitId { get; init; }
    [JsonPropertyName("status")] public required string Status { get; init; }
    [JsonPropertyName("valid_from")] public DateOnly ValidFrom { get; init; }
    [JsonPropertyName("valid_until")] public DateOnly? ValidUntil { get; init; }
    [JsonPropertyName("payment_type")] public required string PaymentType { get; init; }
    [JsonPropertyName("prepaid_balance")] public decimal PrepaidBalance { get; init; }
    [JsonPropertyName("credit_limit")] public decimal CreditLimit { get; init; }
    [JsonPropertyName("credit_used")] public decimal CreditUsed { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    public decimal AvailableCredit => CreditLimit - CreditUsed;
    [JsonIgnore] public string VehicleLabel { get; set; } = "—";
    [JsonIgnore] public string CustomerLabel { get; set; } = "—";
    [JsonIgnore] public string FleetLabel { get; set; } = "—";
    [JsonIgnore] public string FleetGroupLabel { get; set; } = "—";
}
public sealed class FuelCardSaveDto
{
    [JsonPropertyName("vehicle_id")] public int? VehicleId { get; init; }
    [JsonPropertyName("card_code")] public string? CardCode { get; init; }
    [JsonPropertyName("display_name")] public string? DisplayName { get; init; }
    [JsonPropertyName("unit_id")] public string? UnitId { get; init; }
    [JsonPropertyName("status")] public string? Status { get; init; }
    [JsonPropertyName("valid_from")] public DateOnly? ValidFrom { get; init; }
    [JsonPropertyName("valid_until")] public DateOnly? ValidUntil { get; init; }
    [JsonPropertyName("payment_type")] public string? PaymentType { get; init; }
    [JsonPropertyName("prepaid_balance")] public decimal? PrepaidBalance { get; init; }
    [JsonPropertyName("credit_limit")] public decimal? CreditLimit { get; init; }
    [JsonPropertyName("is_active")] public bool? IsActive { get; init; }
}

public sealed class FuelCardLimitReadDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("fuel_card_id")] public int FuelCardId { get; init; }
    [JsonPropertyName("limit_type")] public required string LimitType { get; init; }
    [JsonPropertyName("quantity_limit_liters")] public decimal QuantityLimitLiters { get; init; }
    [JsonPropertyName("valid_from")] public DateOnly? ValidFrom { get; init; }
    [JsonPropertyName("valid_until")] public DateOnly? ValidUntil { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
}
public sealed class FuelCardLimitSaveDto
{
    [JsonPropertyName("fuel_card_id")] public int? FuelCardId { get; init; }
    [JsonPropertyName("limit_type")] public string? LimitType { get; init; }
    [JsonPropertyName("quantity_limit_liters")] public decimal? QuantityLimitLiters { get; init; }
    [JsonPropertyName("valid_from")] public DateOnly? ValidFrom { get; init; }
    [JsonPropertyName("valid_until")] public DateOnly? ValidUntil { get; init; }
    [JsonPropertyName("is_active")] public bool? IsActive { get; init; }
}

public sealed class FuelCardAllowedStationDto { [JsonPropertyName("id")] public int Id { get; init; } [JsonPropertyName("fuel_card_id")] public int FuelCardId { get; init; } [JsonPropertyName("station_id")] public int StationId { get; init; } [JsonIgnore] public string StationDisplayName { get; set; } = "—"; }
public sealed class FuelCardAllowedFuelTypeDto { [JsonPropertyName("id")] public int Id { get; init; } [JsonPropertyName("fuel_card_id")] public int FuelCardId { get; init; } [JsonPropertyName("fuel_type_id")] public int FuelTypeId { get; init; } [JsonIgnore] public string FuelTypeDisplayName { get; set; } = "—"; }
public sealed class FuelCardUsageWindowDto { [JsonPropertyName("id")] public int Id { get; init; } [JsonPropertyName("fuel_card_id")] public int FuelCardId { get; init; } [JsonPropertyName("day_of_week")] public int DayOfWeek { get; init; } [JsonPropertyName("start_time")] public TimeOnly StartTime { get; init; } [JsonPropertyName("end_time")] public TimeOnly EndTime { get; init; } [JsonPropertyName("is_active")] public bool IsActive { get; init; } }
public sealed class FuelCardPermissionSaveDto { [JsonPropertyName("fuel_card_id")] public int FuelCardId { get; init; } [JsonPropertyName("station_id")] public int? StationId { get; init; } [JsonPropertyName("fuel_type_id")] public int? FuelTypeId { get; init; } }
public sealed class FuelCardUsageWindowSaveDto { [JsonPropertyName("fuel_card_id")] public int? FuelCardId { get; init; } [JsonPropertyName("day_of_week")] public int? DayOfWeek { get; init; } [JsonPropertyName("start_time")] public TimeOnly? StartTime { get; init; } [JsonPropertyName("end_time")] public TimeOnly? EndTime { get; init; } [JsonPropertyName("is_active")] public bool? IsActive { get; init; } }
public sealed class FuelCardAuthorizationRequestDto { [JsonPropertyName("unit_id")] public required string UnitId { get; init; } [JsonPropertyName("vehicle_id")] public int VehicleId { get; init; } [JsonPropertyName("station_id")] public int StationId { get; init; } [JsonPropertyName("fuel_type_id")] public int FuelTypeId { get; init; } [JsonPropertyName("requested_quantity_liters")] public decimal RequestedQuantityLiters { get; init; } [JsonPropertyName("requested_at")] public DateTimeOffset? RequestedAt { get; init; } }
public sealed class FuelCardAuthorizationResultDto { [JsonPropertyName("authorized")] public bool Authorized { get; init; } [JsonPropertyName("decision_code")] public required string DecisionCode { get; init; } [JsonPropertyName("message")] public required string Message { get; init; } }

public sealed class FuelPriceReadDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("fuel_type_id")] public int FuelTypeId { get; init; }
    [JsonPropertyName("unit_price")] public decimal UnitPrice { get; init; }
    [JsonPropertyName("effective_from")] public DateTimeOffset EffectiveFrom { get; init; }
    [JsonPropertyName("effective_until")] public DateTimeOffset? EffectiveUntil { get; init; }
    [JsonPropertyName("is_active")] public bool IsActive { get; init; }
    [JsonIgnore] public string StationDisplayName { get; set; } = "—";
    [JsonIgnore] public string FuelTypeDisplayName { get; set; } = "—";
}
public sealed class FuelPriceSaveDto { [JsonPropertyName("station_id")] public int? StationId { get; init; } [JsonPropertyName("fuel_type_id")] public int? FuelTypeId { get; init; } [JsonPropertyName("unit_price")] public decimal? UnitPrice { get; init; } [JsonPropertyName("effective_from")] public DateTimeOffset? EffectiveFrom { get; init; } [JsonPropertyName("effective_until")] public DateTimeOffset? EffectiveUntil { get; init; } [JsonPropertyName("is_active")] public bool? IsActive { get; init; } }

public sealed class SaleReadDto
{
    [JsonPropertyName("id")] public int Id { get; init; }
    [JsonPropertyName("sale_status")] public required string SaleStatus { get; init; }
    [JsonPropertyName("station_id")] public int StationId { get; init; }
    [JsonPropertyName("tank_id")] public int TankId { get; init; }
    [JsonPropertyName("pump_id")] public int PumpId { get; init; }
    [JsonPropertyName("fuel_type_id")] public int FuelTypeId { get; init; }
    [JsonPropertyName("customer_id")] public int? CustomerId { get; init; }
    [JsonPropertyName("fleet_id")] public int? FleetId { get; init; }
    [JsonPropertyName("fleet_group_id")] public int? FleetGroupId { get; init; }
    [JsonPropertyName("vehicle_id")] public int? VehicleId { get; init; }
    [JsonPropertyName("driver_id")] public int? DriverId { get; init; }
    [JsonPropertyName("fuel_card_id")] public int? FuelCardId { get; init; }
    [JsonPropertyName("nozzle_id")] public int? NozzleId { get; init; }
    [JsonPropertyName("sale_timestamp")] public DateTimeOffset SaleTimestamp { get; init; }
    [JsonPropertyName("created_at")] public DateTimeOffset CreatedAt { get; init; }
    [JsonPropertyName("quantity_liters")] public decimal QuantityLiters { get; init; }
    [JsonPropertyName("list_unit_price")] public decimal? ListUnitPrice { get; init; }
    [JsonPropertyName("discount_rate")] public decimal? DiscountRate { get; init; }
    [JsonPropertyName("unit_price")] public decimal UnitPrice { get; init; }
    [JsonPropertyName("total_amount")] public decimal TotalAmount { get; init; }
    [JsonPropertyName("start_totalizer_liters")] public decimal? StartTotalizerLiters { get; init; }
    [JsonPropertyName("end_totalizer_liters")] public decimal? EndTotalizerLiters { get; init; }
    [JsonPropertyName("payment_type")] public string? PaymentType { get; init; }
    [JsonIgnore] public string CustomerLabel { get; set; } = "—";
    [JsonIgnore] public string VehicleLabel { get; set; } = "—";
    [JsonIgnore] public string CardLabel { get; set; } = "Legacy / kart yok";
    [JsonIgnore] public string FleetLabel { get; set; } = "—";
    [JsonIgnore] public string FleetGroupLabel { get; set; } = "—";
    [JsonIgnore] public string DriverLabel { get; set; } = "—";
    [JsonIgnore] public string StationLabel { get; set; } = "—";
    [JsonIgnore] public string PumpLabel { get; set; } = "—";
    [JsonIgnore] public string FuelTypeLabel { get; set; } = "—";
    [JsonIgnore] public string SaleKind => CustomerId is null || VehicleId is null || FuelCardId is null ? "Legacy" : "Ticari";
}
