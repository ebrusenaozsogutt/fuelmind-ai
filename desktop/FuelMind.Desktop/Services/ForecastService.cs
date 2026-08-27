using FuelMind.Desktop.Dtos.Forecasts;

namespace FuelMind.Desktop.Services;

public interface IForecastService
{
    Task<IReadOnlyList<ForecastDto>> GetLatestForecastsAsync(int stationId, int? fuelTypeId = null, CancellationToken cancellationToken = default);
    Task<ForecastPerformanceDto?> GetPerformanceAsync(CancellationToken cancellationToken = default);
    Task<IReadOnlyList<ForecastDto>> GenerateForecastAsync(int stationId, int? fuelTypeId = null, CancellationToken cancellationToken = default);
}

public sealed class ForecastService(ApiClient apiClient) : IForecastService
{
    public Task<IReadOnlyList<ForecastDto>> GetLatestForecastsAsync(int stationId, int? fuelTypeId = null, CancellationToken cancellationToken = default) =>
        apiClient.GetAsync<IReadOnlyList<ForecastDto>>($"forecasts/latest?station_id={stationId}{(fuelTypeId is null ? "" : $"&fuel_type_id={fuelTypeId}")}", cancellationToken);
    public Task<ForecastPerformanceDto?> GetPerformanceAsync(CancellationToken cancellationToken = default) => apiClient.GetOrDefaultAsync<ForecastPerformanceDto>("forecasts/performance", cancellationToken);
    public Task<IReadOnlyList<ForecastDto>> GenerateForecastAsync(int stationId, int? fuelTypeId = null, CancellationToken cancellationToken = default) =>
        apiClient.PostAsync<IReadOnlyList<ForecastDto>>($"forecasts/generate?station_id={stationId}{(fuelTypeId is null ? "" : $"&fuel_type_id={fuelTypeId}")}", cancellationToken);
}
