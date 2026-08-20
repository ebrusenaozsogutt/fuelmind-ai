using FuelMind.Desktop.Dtos.Commercial;

namespace FuelMind.Desktop.Services;

public interface ICommercialService
{
    Task<IReadOnlyList<CustomerReadDto>> GetCustomersAsync(string? search = null, CancellationToken cancellationToken = default);
    Task<CustomerReadDto> CreateCustomerAsync(CustomerSaveDto request, CancellationToken cancellationToken = default);
    Task<CustomerReadDto> UpdateCustomerAsync(int id, CustomerSaveDto request, CancellationToken cancellationToken = default);
    Task DeactivateCustomerAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<CustomerAuthorizedPersonReadDto>> GetAuthorizedPersonsAsync(int customerId, CancellationToken cancellationToken = default);
    Task<CustomerAuthorizedPersonReadDto> CreateAuthorizedPersonAsync(CustomerAuthorizedPersonSaveDto request, CancellationToken cancellationToken = default);
    Task<CustomerAuthorizedPersonReadDto> UpdateAuthorizedPersonAsync(int id, CustomerAuthorizedPersonSaveDto request, CancellationToken cancellationToken = default);
    Task DeactivateAuthorizedPersonAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FleetReadDto>> GetFleetsAsync(int? customerId = null, CancellationToken cancellationToken = default);
    Task<FleetReadDto> CreateFleetAsync(FleetSaveDto request, CancellationToken cancellationToken = default);
    Task<FleetReadDto> UpdateFleetAsync(int id, FleetSaveDto request, CancellationToken cancellationToken = default);
    Task DeactivateFleetAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FleetGroupReadDto>> GetFleetGroupsAsync(int? fleetId = null, CancellationToken cancellationToken = default);
    Task<FleetGroupReadDto> CreateFleetGroupAsync(FleetGroupSaveDto request, CancellationToken cancellationToken = default);
    Task<FleetGroupReadDto> UpdateFleetGroupAsync(int id, FleetGroupSaveDto request, CancellationToken cancellationToken = default);
    Task DeactivateFleetGroupAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<VehicleReadDto>> GetVehiclesAsync(int? fleetGroupId = null, CancellationToken cancellationToken = default);
    Task<VehicleReadDto> CreateVehicleAsync(VehicleSaveDto request, CancellationToken cancellationToken = default);
    Task<VehicleReadDto> UpdateVehicleAsync(int id, VehicleSaveDto request, CancellationToken cancellationToken = default);
    Task DeactivateVehicleAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<DriverReadDto>> GetDriversAsync(CancellationToken cancellationToken = default);
    Task<DriverReadDto> CreateDriverAsync(DriverSaveDto request, CancellationToken cancellationToken = default);
    Task<DriverReadDto> UpdateDriverAsync(int id, DriverSaveDto request, CancellationToken cancellationToken = default);
    Task DeactivateDriverAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<DriverVehicleAssignmentReadDto>> GetAssignmentsAsync(int? driverId = null, int? vehicleId = null, CancellationToken cancellationToken = default);
    Task<DriverVehicleAssignmentReadDto> CreateAssignmentAsync(DriverVehicleAssignmentSaveDto request, CancellationToken cancellationToken = default);
    Task<DriverVehicleAssignmentReadDto> UpdateAssignmentAsync(int id, DriverVehicleAssignmentSaveDto request, CancellationToken cancellationToken = default);
    Task CancelAssignmentAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FuelCardReadDto>> GetFuelCardsAsync(string? search = null, CancellationToken cancellationToken = default);
    Task<FuelCardReadDto> CreateFuelCardAsync(FuelCardSaveDto request, CancellationToken cancellationToken = default);
    Task<FuelCardReadDto> UpdateFuelCardAsync(int id, FuelCardSaveDto request, CancellationToken cancellationToken = default);
    Task DeactivateFuelCardAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FuelCardLimitReadDto>> GetCardLimitsAsync(int cardId, CancellationToken cancellationToken = default);
    Task<FuelCardLimitReadDto> CreateCardLimitAsync(FuelCardLimitSaveDto request, CancellationToken cancellationToken = default);
    Task<FuelCardLimitReadDto> UpdateCardLimitAsync(int id, FuelCardLimitSaveDto request, CancellationToken cancellationToken = default);
    Task DeactivateCardLimitAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FuelCardAllowedStationDto>> GetAllowedStationsAsync(int cardId, CancellationToken cancellationToken = default);
    Task AddAllowedStationAsync(int cardId, int stationId, CancellationToken cancellationToken = default);
    Task RemoveAllowedStationAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FuelCardAllowedFuelTypeDto>> GetAllowedFuelTypesAsync(int cardId, CancellationToken cancellationToken = default);
    Task AddAllowedFuelTypeAsync(int cardId, int fuelTypeId, CancellationToken cancellationToken = default);
    Task RemoveAllowedFuelTypeAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FuelCardUsageWindowDto>> GetUsageWindowsAsync(int cardId, CancellationToken cancellationToken = default);
    Task<FuelCardUsageWindowDto> CreateUsageWindowAsync(FuelCardUsageWindowSaveDto request, CancellationToken cancellationToken = default);
    Task<FuelCardUsageWindowDto> UpdateUsageWindowAsync(int id, FuelCardUsageWindowSaveDto request, CancellationToken cancellationToken = default);
    Task DeactivateUsageWindowAsync(int id, CancellationToken cancellationToken = default);
    Task<FuelCardAuthorizationResultDto> PreviewAuthorizationAsync(FuelCardAuthorizationRequestDto request, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FuelPriceReadDto>> GetFuelPricesAsync(CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FuelPriceReadDto>> GetFuelPriceHistoryAsync(int stationId, int fuelTypeId, CancellationToken cancellationToken = default);
    Task<FuelPriceReadDto> CreateFuelPriceAsync(FuelPriceSaveDto request, CancellationToken cancellationToken = default);
    Task<FuelPriceReadDto> UpdateFuelPriceAsync(int id, FuelPriceSaveDto request, CancellationToken cancellationToken = default);
    Task DeactivateFuelPriceAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<SaleReadDto>> GetSalesAsync(int? customerId = null, int? vehicleId = null, int? fuelCardId = null, CancellationToken cancellationToken = default);
}

public sealed class CommercialService(ApiClient apiClient) : ICommercialService
{
    private static string Query(string path, params (string Key, int? Value)[] values) =>
        path + (values.Where(x => x.Value is not null).Select(x => $"{x.Key}={x.Value}").ToArray() is { Length: > 0 } parts ? "?" + string.Join("&", parts) : string.Empty);
    public Task<IReadOnlyList<CustomerReadDto>> GetCustomersAsync(string? search = null, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<CustomerReadDto>>(string.IsNullOrWhiteSpace(search) ? "customers" : $"customers?search={Uri.EscapeDataString(search)}", ct);
    public Task<CustomerReadDto> CreateCustomerAsync(CustomerSaveDto r, CancellationToken ct = default) => apiClient.PostAsync<CustomerSaveDto, CustomerReadDto>("customers", r, ct);
    public Task<CustomerReadDto> UpdateCustomerAsync(int id, CustomerSaveDto r, CancellationToken ct = default) => apiClient.PutAsync<CustomerSaveDto, CustomerReadDto>($"customers/{id}", r, ct);
    public Task DeactivateCustomerAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"customers/{id}", ct);
    public Task<IReadOnlyList<CustomerAuthorizedPersonReadDto>> GetAuthorizedPersonsAsync(int customerId, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<CustomerAuthorizedPersonReadDto>>($"customers/{customerId}/authorized-persons", ct);
    public Task<CustomerAuthorizedPersonReadDto> CreateAuthorizedPersonAsync(CustomerAuthorizedPersonSaveDto r, CancellationToken ct = default) => apiClient.PostAsync<CustomerAuthorizedPersonSaveDto, CustomerAuthorizedPersonReadDto>("customer-authorized-persons", r, ct);
    public Task<CustomerAuthorizedPersonReadDto> UpdateAuthorizedPersonAsync(int id, CustomerAuthorizedPersonSaveDto r, CancellationToken ct = default) => apiClient.PutAsync<CustomerAuthorizedPersonSaveDto, CustomerAuthorizedPersonReadDto>($"customer-authorized-persons/{id}", r, ct);
    public Task DeactivateAuthorizedPersonAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"customer-authorized-persons/{id}", ct);
    public Task<IReadOnlyList<FleetReadDto>> GetFleetsAsync(int? customerId = null, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<FleetReadDto>>(Query("fleets", ("customer_id", customerId)), ct);
    public Task<FleetReadDto> CreateFleetAsync(FleetSaveDto r, CancellationToken ct = default) => apiClient.PostAsync<FleetSaveDto, FleetReadDto>("fleets", r, ct);
    public Task<FleetReadDto> UpdateFleetAsync(int id, FleetSaveDto r, CancellationToken ct = default) => apiClient.PutAsync<FleetSaveDto, FleetReadDto>($"fleets/{id}", r, ct);
    public Task DeactivateFleetAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"fleets/{id}", ct);
    public Task<IReadOnlyList<FleetGroupReadDto>> GetFleetGroupsAsync(int? fleetId = null, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<FleetGroupReadDto>>(Query("fleet-groups", ("fleet_id", fleetId)), ct);
    public Task<FleetGroupReadDto> CreateFleetGroupAsync(FleetGroupSaveDto r, CancellationToken ct = default) => apiClient.PostAsync<FleetGroupSaveDto, FleetGroupReadDto>("fleet-groups", r, ct);
    public Task<FleetGroupReadDto> UpdateFleetGroupAsync(int id, FleetGroupSaveDto r, CancellationToken ct = default) => apiClient.PutAsync<FleetGroupSaveDto, FleetGroupReadDto>($"fleet-groups/{id}", r, ct);
    public Task DeactivateFleetGroupAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"fleet-groups/{id}", ct);
    public Task<IReadOnlyList<VehicleReadDto>> GetVehiclesAsync(int? groupId = null, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<VehicleReadDto>>(Query("vehicles", ("fleet_group_id", groupId)), ct);
    public Task<VehicleReadDto> CreateVehicleAsync(VehicleSaveDto r, CancellationToken ct = default) => apiClient.PostAsync<VehicleSaveDto, VehicleReadDto>("vehicles", r, ct);
    public Task<VehicleReadDto> UpdateVehicleAsync(int id, VehicleSaveDto r, CancellationToken ct = default) => apiClient.PutAsync<VehicleSaveDto, VehicleReadDto>($"vehicles/{id}", r, ct);
    public Task DeactivateVehicleAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"vehicles/{id}", ct);
    public Task<IReadOnlyList<DriverReadDto>> GetDriversAsync(CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<DriverReadDto>>("drivers", ct);
    public Task<DriverReadDto> CreateDriverAsync(DriverSaveDto r, CancellationToken ct = default) => apiClient.PostAsync<DriverSaveDto, DriverReadDto>("drivers", r, ct);
    public Task<DriverReadDto> UpdateDriverAsync(int id, DriverSaveDto r, CancellationToken ct = default) => apiClient.PutAsync<DriverSaveDto, DriverReadDto>($"drivers/{id}", r, ct);
    public Task DeactivateDriverAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"drivers/{id}", ct);
    public Task<IReadOnlyList<DriverVehicleAssignmentReadDto>> GetAssignmentsAsync(int? driverId = null, int? vehicleId = null, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<DriverVehicleAssignmentReadDto>>(Query("driver-vehicle-assignments", ("driver_id", driverId), ("vehicle_id", vehicleId)), ct);
    public Task<DriverVehicleAssignmentReadDto> CreateAssignmentAsync(DriverVehicleAssignmentSaveDto r, CancellationToken ct = default) => apiClient.PostAsync<DriverVehicleAssignmentSaveDto, DriverVehicleAssignmentReadDto>("driver-vehicle-assignments", r, ct);
    public Task<DriverVehicleAssignmentReadDto> UpdateAssignmentAsync(int id, DriverVehicleAssignmentSaveDto r, CancellationToken ct = default) => apiClient.PutAsync<DriverVehicleAssignmentSaveDto, DriverVehicleAssignmentReadDto>($"driver-vehicle-assignments/{id}", r, ct);
    public Task CancelAssignmentAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"driver-vehicle-assignments/{id}", ct);
    public Task<IReadOnlyList<FuelCardReadDto>> GetFuelCardsAsync(string? search = null, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<FuelCardReadDto>>(string.IsNullOrWhiteSpace(search) ? "fuel-cards" : $"fuel-cards?search={Uri.EscapeDataString(search)}", ct);
    public Task<FuelCardReadDto> CreateFuelCardAsync(FuelCardSaveDto r, CancellationToken ct = default) => apiClient.PostAsync<FuelCardSaveDto, FuelCardReadDto>("fuel-cards", r, ct);
    public Task<FuelCardReadDto> UpdateFuelCardAsync(int id, FuelCardSaveDto r, CancellationToken ct = default) => apiClient.PutAsync<FuelCardSaveDto, FuelCardReadDto>($"fuel-cards/{id}", r, ct);
    public Task DeactivateFuelCardAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"fuel-cards/{id}", ct);
    public Task<IReadOnlyList<FuelCardLimitReadDto>> GetCardLimitsAsync(int id, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<FuelCardLimitReadDto>>($"fuel-cards/{id}/limits", ct);
    public Task<FuelCardLimitReadDto> CreateCardLimitAsync(FuelCardLimitSaveDto r, CancellationToken ct = default) => apiClient.PostAsync<FuelCardLimitSaveDto, FuelCardLimitReadDto>("fuel-card-limits", r, ct);
    public Task<FuelCardLimitReadDto> UpdateCardLimitAsync(int id, FuelCardLimitSaveDto r, CancellationToken ct = default) => apiClient.PutAsync<FuelCardLimitSaveDto, FuelCardLimitReadDto>($"fuel-card-limits/{id}", r, ct);
    public Task DeactivateCardLimitAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"fuel-card-limits/{id}", ct);
    public Task<IReadOnlyList<FuelCardAllowedStationDto>> GetAllowedStationsAsync(int id, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<FuelCardAllowedStationDto>>($"fuel-cards/{id}/allowed-stations", ct);
    public async Task AddAllowedStationAsync(int cardId, int stationId, CancellationToken ct = default) => _ = await apiClient.PostAsync<FuelCardPermissionSaveDto, FuelCardAllowedStationDto>("fuel-card-allowed-stations", new() { FuelCardId = cardId, StationId = stationId }, ct);
    public Task RemoveAllowedStationAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"fuel-card-allowed-stations/{id}", ct);
    public Task<IReadOnlyList<FuelCardAllowedFuelTypeDto>> GetAllowedFuelTypesAsync(int id, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<FuelCardAllowedFuelTypeDto>>($"fuel-cards/{id}/allowed-fuel-types", ct);
    public async Task AddAllowedFuelTypeAsync(int cardId, int fuelTypeId, CancellationToken ct = default) => _ = await apiClient.PostAsync<FuelCardPermissionSaveDto, FuelCardAllowedFuelTypeDto>("fuel-card-allowed-fuel-types", new() { FuelCardId = cardId, FuelTypeId = fuelTypeId }, ct);
    public Task RemoveAllowedFuelTypeAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"fuel-card-allowed-fuel-types/{id}", ct);
    public Task<IReadOnlyList<FuelCardUsageWindowDto>> GetUsageWindowsAsync(int id, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<FuelCardUsageWindowDto>>($"fuel-cards/{id}/usage-windows", ct);
    public Task<FuelCardUsageWindowDto> CreateUsageWindowAsync(FuelCardUsageWindowSaveDto r, CancellationToken ct = default) => apiClient.PostAsync<FuelCardUsageWindowSaveDto, FuelCardUsageWindowDto>("fuel-card-usage-windows", r, ct);
    public Task<FuelCardUsageWindowDto> UpdateUsageWindowAsync(int id, FuelCardUsageWindowSaveDto r, CancellationToken ct = default) => apiClient.PutAsync<FuelCardUsageWindowSaveDto, FuelCardUsageWindowDto>($"fuel-card-usage-windows/{id}", r, ct);
    public Task DeactivateUsageWindowAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"fuel-card-usage-windows/{id}", ct);
    public Task<FuelCardAuthorizationResultDto> PreviewAuthorizationAsync(FuelCardAuthorizationRequestDto r, CancellationToken ct = default) => apiClient.PostAsync<FuelCardAuthorizationRequestDto, FuelCardAuthorizationResultDto>("fuel-cards/authorize", r, ct);
    public Task<IReadOnlyList<FuelPriceReadDto>> GetFuelPricesAsync(CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<FuelPriceReadDto>>("fuel-prices", ct);
    public Task<IReadOnlyList<FuelPriceReadDto>> GetFuelPriceHistoryAsync(int stationId, int fuelTypeId, CancellationToken ct = default) => apiClient.GetAsync<IReadOnlyList<FuelPriceReadDto>>($"stations/{stationId}/fuel-prices/{fuelTypeId}/history", ct);
    public Task<FuelPriceReadDto> CreateFuelPriceAsync(FuelPriceSaveDto r, CancellationToken ct = default) => apiClient.PostAsync<FuelPriceSaveDto, FuelPriceReadDto>("fuel-prices", r, ct);
    public Task<FuelPriceReadDto> UpdateFuelPriceAsync(int id, FuelPriceSaveDto r, CancellationToken ct = default) => apiClient.PutAsync<FuelPriceSaveDto, FuelPriceReadDto>($"fuel-prices/{id}", r, ct);
    public Task DeactivateFuelPriceAsync(int id, CancellationToken ct = default) => apiClient.DeleteAsync($"fuel-prices/{id}", ct);
    public async Task<IReadOnlyList<SaleReadDto>> GetSalesAsync(int? customerId = null, int? vehicleId = null, int? fuelCardId = null, CancellationToken ct = default)
    {
        // The API defaults to 50 rows. Legacy sales are often older than the
        // commercial feed, so continue through the existing paged endpoint
        // instead of silently dropping them from the desktop list.
        const int defaultPageSize = 50;
        const int pageSize = 100;
        var path = Query("sales", ("customer_id", customerId), ("vehicle_id", vehicleId), ("fuel_card_id", fuelCardId));
        var firstPage = await apiClient.GetAsync<IReadOnlyList<SaleReadDto>>(path, ct);
        if (firstPage.Count < defaultPageSize) return firstPage;

        var sales = new List<SaleReadDto>(firstPage);
        for (var skip = defaultPageSize; ; skip += pageSize)
        {
            var separator = path.Contains('?') ? "&" : "?";
            var page = await apiClient.GetAsync<IReadOnlyList<SaleReadDto>>($"{path}{separator}skip={skip}&limit={pageSize}", ct);
            sales.AddRange(page);
            if (page.Count < pageSize) return sales;
        }
    }
}
