using FuelMind.Desktop.Dtos.Alarms;

namespace FuelMind.Desktop.Services;

public interface IAlarmService
{
    Task<IReadOnlyList<AlarmDto>> GetAllAsync(
        bool includeFalsePositives = false,
        CancellationToken token = default);
    Task<AlarmDto> GetByIdAsync(int id, CancellationToken token = default);
    Task<AlarmDto> UpdateAsync(
        int id,
        string action,
        string? note = null,
        CancellationToken token = default);
}

public sealed class AlarmService(ApiClient api) : IAlarmService
{
    public Task<IReadOnlyList<AlarmDto>> GetAllAsync(
        bool includeFalsePositives = false,
        CancellationToken token = default) =>
        api.GetAsync<IReadOnlyList<AlarmDto>>(
            includeFalsePositives ? "alarms?include_false_positives=true" : "alarms", token);

    public Task<AlarmDto> GetByIdAsync(int id, CancellationToken token = default) =>
        api.GetAsync<AlarmDto>($"alarms/{id}", token);

    public Task<AlarmDto> UpdateAsync(
        int id,
        string action,
        string? note = null,
        CancellationToken token = default) =>
        api.PatchAsync<AlarmResolutionRequest, AlarmDto>(
            $"alarms/{id}/{action}", new(note), token);
}
