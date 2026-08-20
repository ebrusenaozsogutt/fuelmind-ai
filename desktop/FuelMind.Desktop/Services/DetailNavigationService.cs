namespace FuelMind.Desktop.Services;
public sealed class DetailNavigationService
{
    public event Action<int>? TankRequested;
    public event Action<int>? PumpRequested;
    public event Action? BackToTanksRequested;
    public event Action? BackToPumpsRequested;
    public event Action<AlarmNavigationFilter>? AlarmsRequested;
    public event Action<int>? FaultRequested;
    public event Action? PumpsRequested;
    public event Action? TanksRequested;
    public event Action? LiveRiskRequested;
    public void ShowTank(int id) => TankRequested?.Invoke(id);
    public void ShowPump(int id) => PumpRequested?.Invoke(id);
    public void BackToTanks() => BackToTanksRequested?.Invoke();
    public void BackToPumps() => BackToPumpsRequested?.Invoke();
    public void ShowAlarms(AlarmNavigationFilter filter) => AlarmsRequested?.Invoke(filter);
    public void ShowFault(int id) => FaultRequested?.Invoke(id);
    public void ShowPumps() => PumpsRequested?.Invoke();
    public void ShowTanks() => TanksRequested?.Invoke();
    public void ShowLiveRisk() => LiveRiskRequested?.Invoke();
}

public sealed record AlarmNavigationFilter(string? Severity = null);
