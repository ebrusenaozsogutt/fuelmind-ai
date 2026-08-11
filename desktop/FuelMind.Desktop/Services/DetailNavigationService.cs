namespace FuelMind.Desktop.Services;
public sealed class DetailNavigationService
{
    public event Action<int>? TankRequested;
    public event Action<int>? PumpRequested;
    public event Action? BackToTanksRequested;
    public event Action? BackToPumpsRequested;
    public void ShowTank(int id) => TankRequested?.Invoke(id);
    public void ShowPump(int id) => PumpRequested?.Invoke(id);
    public void BackToTanks() => BackToTanksRequested?.Invoke();
    public void BackToPumps() => BackToPumpsRequested?.Invoke();
}
