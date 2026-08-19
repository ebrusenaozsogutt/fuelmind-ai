using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Dtos.Pumps;

namespace FuelMind.Desktop.Models;

public sealed class ControllerTopologyItem(ControllerLiveDto controller) : ObservableObject
{
    public ControllerLiveDto Controller { get; private set; } = controller;
    public ObservableCollection<PortTopologyItem> Ports { get; } = [];
    public string Code => Controller.Code ?? "-";
    public string Name => Controller.Name ?? "-";
    public string ControllerType => Controller.ControllerType ?? "-";
    public string Status => Controller.Status ?? "UNKNOWN";
    public DateTimeOffset? LastCommunicationAt => Controller.LastCommunicationAt;
    public void Update(ControllerLiveDto controller) { Controller = controller; OnPropertyChanged(string.Empty); }
}

public sealed class PortTopologyItem(CommunicationPortLiveDto port) : ObservableObject
{
    public CommunicationPortLiveDto Port { get; private set; } = port;
    public ObservableCollection<PumpTopologyItem> Pumps { get; } = [];
    public ObservableCollection<ProbeTopologyItem> Probes { get; } = [];
    public string Name => Port.Name ?? "-";
    public string PortType => Port.PortType ?? "-";
    public string Protocol => string.IsNullOrWhiteSpace(Port.Protocol) ? "-" : Port.Protocol;
    public string Status => Port.Status ?? "UNKNOWN";
    public void Update(CommunicationPortLiveDto port) { Port = port; OnPropertyChanged(string.Empty); }
}

public sealed class PumpTopologyItem(PumpDto pump, PumpLiveDataDto? livePump) : ObservableObject
{
    public PumpDto Pump { get; private set; } = pump;
    public PumpLiveDataDto? LivePump { get; private set; } = livePump;
    public ObservableCollection<NozzleTopologyItem> Nozzles { get; } = [];
    public string Code => Pump.Code;
    public string Status => LivePump?.Status ?? Pump.Status;
    public int TankId => Pump.TankId;
    public void Update(PumpDto pump, PumpLiveDataDto? livePump) { Pump = pump; LivePump = livePump; OnPropertyChanged(string.Empty); }
}

public sealed class NozzleTopologyItem(NozzleLiveDto nozzle) : ObservableObject
{
    public NozzleLiveDto Nozzle { get; private set; } = nozzle;
    public string Code => Nozzle.Code ?? "-";
    public string FuelType => Nozzle.FuelTypeName ?? Nozzle.FuelTypeCode ?? "-";
    public string Status => Nozzle.Status ?? "UNKNOWN";
    public decimal TotalizerLiters => Nozzle.TotalizerLiters;
    public void Update(NozzleLiveDto nozzle) { Nozzle = nozzle; OnPropertyChanged(string.Empty); }
}

public sealed class ProbeTopologyItem(ProbeLiveDto probe, TankLiveDataDto? tank) : ObservableObject
{
    public ProbeLiveDto Probe { get; private set; } = probe;
    public TankLiveDataDto? Tank { get; private set; } = tank;
    public string Code => Probe.Code ?? "-";
    public string Status => Probe.Status ?? "UNKNOWN";
    public string TankDisplay => Tank?.Code ?? $"Tank ID: {Probe.TankId}";
    public void Update(ProbeLiveDto probe, TankLiveDataDto? tank) { Probe = probe; Tank = tank; OnPropertyChanged(string.Empty); }
}
