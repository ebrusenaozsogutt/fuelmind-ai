using FuelMind.Desktop.Dtos.Orders;

namespace FuelMind.Desktop.Services;

public interface IOrderRecommendationService
{
    Task<OrderRecommendationDto> GetTankRecommendationAsync(int tankId, CancellationToken cancellationToken = default);
    Task<OrderRecommendationDto> GenerateTankRecommendationAsync(int tankId, CancellationToken cancellationToken = default);
}

public sealed class OrderRecommendationService(ApiClient apiClient) : IOrderRecommendationService
{
    public Task<OrderRecommendationDto> GetTankRecommendationAsync(int tankId, CancellationToken cancellationToken = default) => apiClient.GetAsync<OrderRecommendationDto>($"tanks/{tankId}/recommendation", cancellationToken);
    public Task<OrderRecommendationDto> GenerateTankRecommendationAsync(int tankId, CancellationToken cancellationToken = default) => apiClient.PostAsync<OrderRecommendationDto>($"tanks/{tankId}/recommendation/generate", cancellationToken);
}
