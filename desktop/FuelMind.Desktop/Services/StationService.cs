using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Dtos.Live;

namespace FuelMind.Desktop.Services;

public interface IStationService
{
    Task<IReadOnlyList<StationDto>> GetActiveStationsAsync(
        CancellationToken cancellationToken = default);
    Task<StationLiveStatusDto> GetLiveStatusAsync(
        int stationId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FuelTypeDto>> GetFuelTypesAsync(CancellationToken cancellationToken = default);
}

public sealed class StationService(ApiClient apiClient) : IStationService
{
    public Task<IReadOnlyList<StationDto>> GetActiveStationsAsync(
        CancellationToken cancellationToken = default) =>
        apiClient.GetAsync<IReadOnlyList<StationDto>>(
            "stations?is_active=true", cancellationToken);

    public Task<StationLiveStatusDto> GetLiveStatusAsync(
        int stationId, CancellationToken cancellationToken = default) =>
        apiClient.GetAsync<StationLiveStatusDto>(
            $"stations/{stationId}/live-status", cancellationToken);

    public Task<IReadOnlyList<FuelTypeDto>> GetFuelTypesAsync(CancellationToken cancellationToken = default) =>
        apiClient.GetAsync<IReadOnlyList<FuelTypeDto>>("fuel-types?is_active=true", cancellationToken);
}
