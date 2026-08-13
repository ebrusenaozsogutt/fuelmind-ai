using FuelMind.Desktop.Dtos.Models;

namespace FuelMind.Desktop.Services;

public interface IModelService
{
    Task<IReadOnlyList<ModelVersionDto>> GetModelsAsync(CancellationToken cancellationToken = default);
    Task<TrainAnomalyModelResponseDto> TrainAnomalyModelAsync(
        TrainAnomalyModelRequestDto request,
        CancellationToken cancellationToken = default);
    Task<ModelVersionDto> ActivateModelAsync(int modelId, CancellationToken cancellationToken = default);
}

public sealed class ModelService(ApiClient apiClient) : IModelService
{
    public Task<IReadOnlyList<ModelVersionDto>> GetModelsAsync(
        CancellationToken cancellationToken = default) =>
        apiClient.GetAsync<IReadOnlyList<ModelVersionDto>>("models", cancellationToken);

    public Task<TrainAnomalyModelResponseDto> TrainAnomalyModelAsync(
        TrainAnomalyModelRequestDto request,
        CancellationToken cancellationToken = default) =>
        apiClient.PostAsync<TrainAnomalyModelRequestDto, TrainAnomalyModelResponseDto>(
            "ml/train-anomaly-model", request, cancellationToken);

    public Task<ModelVersionDto> ActivateModelAsync(
        int modelId,
        CancellationToken cancellationToken = default) =>
        apiClient.PatchAsync<ModelVersionDto>($"models/{modelId}/activate", cancellationToken);
}
