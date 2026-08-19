using FuelMind.Desktop.Dtos.Faults;
using FuelMind.Desktop.Dtos.Pumps;
using FuelMind.Desktop.Dtos.Tanks;

namespace FuelMind.Desktop.Services;

public interface IFaultService
{
    Task<IReadOnlyList<FaultDto>> ListAsync(string query, CancellationToken ct = default);
    Task<FaultDto> CreateAsync(FaultCreateDto request, CancellationToken ct = default);
    Task<FaultDto> InvestigateAsync(int id, CancellationToken ct = default);
    Task<FaultDto> ResolveAsync(int id, string note, CancellationToken ct = default);
    Task<IReadOnlyList<FaultTargetOption>> GetTargetsAsync(int stationId, string targetType, CancellationToken ct = default);
}

public sealed class FaultService(ApiClient api) : IFaultService
{
    public Task<IReadOnlyList<FaultDto>> ListAsync(string query, CancellationToken ct = default) => api.GetAsync<IReadOnlyList<FaultDto>>("faults" + query, ct);
    public Task<FaultDto> CreateAsync(FaultCreateDto request, CancellationToken ct = default) => api.PostAsync<FaultCreateDto, FaultDto>("faults", request, ct);
    public Task<FaultDto> InvestigateAsync(int id, CancellationToken ct = default) => api.PatchAsync<FaultDto>($"faults/{id}/investigate", ct);
    public Task<FaultDto> ResolveAsync(int id, string note, CancellationToken ct = default) => api.PatchAsync<FaultResolutionDto, FaultDto>($"faults/{id}/resolve", new() { ResolutionNote = note }, ct);

    public async Task<IReadOnlyList<FaultTargetOption>> GetTargetsAsync(int stationId, string targetType, CancellationToken ct = default) => targetType switch
    {
        "PUMP" => (await api.GetAsync<IReadOnlyList<PumpDto>>($"stations/{stationId}/pumps?is_active=true", ct)).Select(x => new FaultTargetOption(x.Id, $"{x.Code} (Pompa #{x.Id})")).ToArray(),
        "TANK" => (await api.GetAsync<IReadOnlyList<TankDto>>($"stations/{stationId}/tanks?is_active=true", ct)).Select(x => new FaultTargetOption(x.Id, $"{x.Code} (Tank #{x.Id})")).ToArray(),
        "CONTROLLER" => (await api.GetAsync<IReadOnlyList<DeviceControllerTargetDto>>($"stations/{stationId}/device-controllers?is_active=true", ct)).Select(x => new FaultTargetOption(x.Id, $"{x.Code} — {x.Name}")).ToArray(),
        "PORT" => (await api.GetAsync<IReadOnlyList<CommunicationPortTargetDto>>("communication-ports?is_active=true&limit=100", ct)).Where(x => x.StationId == stationId).Select(x => new FaultTargetOption(x.Id, $"Port {x.PortNumber} — {x.Name}")).ToArray(),
        "NOZZLE" => await GetNozzlesAsync(stationId, ct),
        "PROBE" => await GetProbesAsync(stationId, ct, "Prob"),
        // Backend validates SENSOR against the same persisted tank-probe entity.
        "SENSOR" => await GetProbesAsync(stationId, ct, "Sensör / prob"),
        _ => [],
    };

    private async Task<IReadOnlyList<FaultTargetOption>> GetNozzlesAsync(int stationId, CancellationToken ct)
    {
        var pumpIds = (await api.GetAsync<IReadOnlyList<PumpDto>>($"stations/{stationId}/pumps?is_active=true", ct)).Select(x => x.Id).ToHashSet();
        return (await api.GetAsync<IReadOnlyList<NozzleTargetDto>>("nozzles?is_active=true&limit=100", ct)).Where(x => pumpIds.Contains(x.PumpId)).Select(x => new FaultTargetOption(x.Id, $"{x.Code} — Nozul {x.NozzleNumber}")).ToArray();
    }

    private async Task<IReadOnlyList<FaultTargetOption>> GetProbesAsync(int stationId, CancellationToken ct, string label)
    {
        var tankIds = (await api.GetAsync<IReadOnlyList<TankDto>>($"stations/{stationId}/tanks?is_active=true", ct)).Select(x => x.Id).ToHashSet();
        return (await api.GetAsync<IReadOnlyList<ProbeTargetDto>>("tank-probes?is_active=true&limit=100", ct)).Where(x => tankIds.Contains(x.TankId)).Select(x => new FaultTargetOption(x.Id, $"{x.Code} — {label}: {x.Name}")).ToArray();
    }
}
