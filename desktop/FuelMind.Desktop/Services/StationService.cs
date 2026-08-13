using FuelMind.Desktop.Dtos.Stations;

namespace FuelMind.Desktop.Services;

public interface IStationService
{
    Task<IReadOnlyList<StationDto>> GetActiveStationsAsync(
        CancellationToken cancellationToken = default);
}

public sealed class StationService(ApiClient apiClient) : IStationService
{
    public Task<IReadOnlyList<StationDto>> GetActiveStationsAsync(
        CancellationToken cancellationToken = default) =>
        apiClient.GetAsync<IReadOnlyList<StationDto>>(
            "stations?is_active=true", cancellationToken);
}
