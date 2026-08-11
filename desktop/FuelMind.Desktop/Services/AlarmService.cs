using FuelMind.Desktop.Dtos.Alarms;
namespace FuelMind.Desktop.Services;
public sealed class AlarmService(ApiClient api) { public Task<IReadOnlyList<AlarmDto>> GetAllAsync(CancellationToken token = default) => api.GetAsync<IReadOnlyList<AlarmDto>>("alarms", token); public Task<AlarmDto> UpdateAsync(int id, string action, string? note = null, CancellationToken token = default) => api.PatchAsync<AlarmResolutionRequest, AlarmDto>($"alarms/{id}/{action}", new(note), token); }
