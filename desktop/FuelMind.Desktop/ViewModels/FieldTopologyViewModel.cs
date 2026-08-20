using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Dtos.Pumps;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Models;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;

namespace FuelMind.Desktop.ViewModels;

/// <summary>Builds a technical controller/port/pump/probe view from shared live state.</summary>
public sealed partial class FieldTopologyViewModel : ObservableObject
{
    private readonly LiveDataStore _liveDataStore;
    private readonly LiveWebSocketService _liveWebSocketService;
    private readonly IStationService _stationService;
    private readonly ApiClient _apiClient;
    private IReadOnlyList<PumpDto> _pumpCatalog = [];

    public FieldTopologyViewModel(
        LiveDataStore liveDataStore,
        LiveWebSocketService liveWebSocketService,
        IStationService stationService,
        ApiClient apiClient)
    {
        _liveDataStore = liveDataStore;
        _liveWebSocketService = liveWebSocketService;
        _stationService = stationService;
        _apiClient = apiClient;
        SelectedStationId = liveDataStore.SelectedStationId;
        // WebSocket callbacks can originate on a worker thread.  Keep the derived
        // topology collection mutations on the WPF dispatcher so every live tick
        // is reflected by the bound items without cross-thread collection access.
        _liveDataStore.TopologyChanged += (_, _) => RequestTopologyRefresh();
        _liveDataStore.Pumps.CollectionChanged += (_, _) => RequestTopologyRefresh();
        _liveDataStore.Tanks.CollectionChanged += (_, _) => RequestTopologyRefresh();
        _liveDataStore.PropertyChanged += (_, args) =>
        {
            if (args.PropertyName == nameof(LiveDataStore.ConnectionState))
            {
                OnPropertyChanged(nameof(ConnectionState));
            }
            else if (args.PropertyName == nameof(LiveDataStore.SelectedStationId) &&
                     SelectedStationId != _liveDataStore.SelectedStationId)
            {
                SelectedStationId = _liveDataStore.SelectedStationId;
            }
        };
        _liveWebSocketService.ConnectionStateChanged += (_, state) =>
        {
            if (state != LiveConnectionState.Connected) return;
            var dispatcher = System.Windows.Application.Current?.Dispatcher;
            if (dispatcher is null || dispatcher.CheckAccess()) _ = LoadSnapshotAsync();
            else dispatcher.BeginInvoke(new Action(() => _ = LoadSnapshotAsync()));
        };
    }

    public ObservableCollection<StationDto> Stations { get; } = [];
    public ObservableCollection<ControllerTopologyItem> Controllers { get; } = [];
    public ObservableCollection<PumpTopologyItem> UnassignedPumps { get; } = [];
    public ObservableCollection<ProbeTopologyItem> UnassignedProbes { get; } = [];
    public ObservableCollection<CommunicationPortLiveDto> Ports => _liveDataStore.Ports;
    public ObservableCollection<NozzleLiveDto> Nozzles => _liveDataStore.Nozzles;
    public ObservableCollection<ProbeLiveDto> Probes => _liveDataStore.Probes;
    public ObservableCollection<TankLiveDataDto> Tanks => _liveDataStore.Tanks;
    public LiveConnectionState ConnectionState => _liveDataStore.ConnectionState;
    public bool HasTopology => Controllers.Count > 0 || UnassignedPumps.Count > 0 || UnassignedProbes.Count > 0;
    public bool HasUnassignedPumps => UnassignedPumps.Count > 0;
    public bool HasUnassignedProbes => UnassignedProbes.Count > 0;
    public bool ShowEmptyState => !IsLoading && string.IsNullOrWhiteSpace(ErrorMessage) && !HasTopology;

    [ObservableProperty] private int _selectedStationId;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;

    public async Task LoadAsync()
    {
        if (IsLoading) return;
        IsLoading = true;
        ErrorMessage = null;
        try
        {
            if (Stations.Count == 0)
            {
                foreach (var station in (await _stationService.GetActiveStationsAsync())
                    .OrderBy(station => string.Equals(station.Code, "KONYA_TEST", StringComparison.OrdinalIgnoreCase) ? 0 : 1)
                    .ThenBy(station => station.Code))
                {
                    Stations.Add(station);
                }
            }
            if (SelectedStationId <= 0) SelectedStationId = Stations.FirstOrDefault()?.Id ?? 0;
            if (SelectedStationId > 0) await RefreshAsync();
        }
        catch (Exception exception) { ErrorMessage = exception.Message; }
        finally { IsLoading = false; }
    }

    [RelayCommand]
    private async Task RefreshAsync()
    {
        if (SelectedStationId <= 0) return;
        ErrorMessage = null;
        try
        {
            _liveDataStore.SelectedStationId = SelectedStationId;
            await LoadSnapshotAsync();
            if (_liveWebSocketService.ConnectionState == LiveConnectionState.Connected &&
                _liveWebSocketService.ConnectedStationId != SelectedStationId)
            {
                await _liveWebSocketService.DisconnectAsync();
            }
            if (_liveWebSocketService.ConnectionState == LiveConnectionState.Disconnected)
            {
                await _liveWebSocketService.ConnectAsync(SelectedStationId);
            }
        }
        catch (Exception exception) { ErrorMessage = exception.Message; }
    }

    private async Task LoadSnapshotAsync()
    {
        if (SelectedStationId <= 0) return;
        var snapshot = await _stationService.GetLiveStatusAsync(SelectedStationId);
        _pumpCatalog = await _apiClient.GetAsync<IReadOnlyList<PumpDto>>(
            $"stations/{SelectedStationId}/pumps?limit=100");
        _liveDataStore.ApplyLiveStatus(snapshot);
        RequestTopologyRefresh();
    }

    private void RequestTopologyRefresh()
    {
        var dispatcher = System.Windows.Application.Current?.Dispatcher;
        if (dispatcher is null || dispatcher.CheckAccess())
        {
            RefreshTopology();
            return;
        }

        _ = dispatcher.BeginInvoke(new Action(RefreshTopology));
    }

    private void RefreshTopology()
    {
        var livePumps = _liveDataStore.Pumps.ToDictionary(item => item.PumpId);
        var tanks = _liveDataStore.Tanks.ToDictionary(item => item.TankId);
        var pumps = _pumpCatalog.ToDictionary(item => item.Id);
        var nozzles = _liveDataStore.Nozzles.GroupBy(item => item.PumpId)
            .ToDictionary(group => group.Key, group => group.ToList());
        var probesByPort = _liveDataStore.Probes
            .Where(item => item.CommunicationPortId is not null)
            .GroupBy(item => item.CommunicationPortId!.Value)
            .ToDictionary(group => group.Key, group => group.ToList());
        var unassignedProbes = _liveDataStore.Probes
            .Where(item => item.CommunicationPortId is null)
            .ToList();

        Sync(Controllers, _liveDataStore.Controllers, item => item.Id,
            item => new ControllerTopologyItem(item), (target, source) => target.Update(source));
        foreach (var controller in Controllers)
        {
            var ports = _liveDataStore.Ports.Where(item => item.ControllerId == controller.Controller.Id).ToList();
            Sync(controller.Ports, ports, item => item.Id,
                item => new PortTopologyItem(item), (target, source) => target.Update(source));
            foreach (var port in controller.Ports)
            {
                var portPumps = pumps.Values.Where(item => item.CommunicationPortId == port.Port.Id).ToList();
                Sync(port.Pumps, portPumps, item => item.Id,
                    item => new PumpTopologyItem(item, livePumps.GetValueOrDefault(item.Id)),
                    (target, source) => target.Update(source, livePumps.GetValueOrDefault(source.Id)));
                foreach (var pump in port.Pumps)
                {
                    Sync(pump.Nozzles, nozzles.GetValueOrDefault(pump.Pump.Id) ?? [], item => item.Id,
                        item => new NozzleTopologyItem(item), (target, source) => target.Update(source));
                }
                Sync(port.Probes, probesByPort.GetValueOrDefault(port.Port.Id) ?? [], item => item.Id,
                    item => new ProbeTopologyItem(item, tanks.GetValueOrDefault(item.TankId)),
                    (target, source) => target.Update(source, tanks.GetValueOrDefault(source.TankId)));
            }
        }
        Sync(UnassignedPumps, pumps.Values.Where(item => item.CommunicationPortId is null).ToList(), item => item.Id,
            item => new PumpTopologyItem(item, livePumps.GetValueOrDefault(item.Id)),
            (target, source) => target.Update(source, livePumps.GetValueOrDefault(source.Id)));
        Sync(UnassignedProbes, unassignedProbes, item => item.Id,
            item => new ProbeTopologyItem(item, tanks.GetValueOrDefault(item.TankId)),
            (target, source) => target.Update(source, tanks.GetValueOrDefault(source.TankId)));
        OnPropertyChanged(nameof(HasTopology));
        OnPropertyChanged(nameof(HasUnassignedPumps));
        OnPropertyChanged(nameof(HasUnassignedProbes));
        OnPropertyChanged(nameof(ShowEmptyState));
    }

    partial void OnSelectedStationIdChanged(int value)
    {
        if (_liveDataStore.SelectedStationId != value) _liveDataStore.SelectedStationId = value;
    }

    partial void OnIsLoadingChanged(bool value) => OnPropertyChanged(nameof(ShowEmptyState));
    partial void OnErrorMessageChanged(string? value) => OnPropertyChanged(nameof(ShowEmptyState));

    private static void Sync<TTarget, TSource>(
        ObservableCollection<TTarget> target,
        IReadOnlyList<TSource> source,
        Func<TSource, int> sourceId,
        Func<TSource, TTarget> create,
        Action<TTarget, TSource> update)
    {
        var sourceIds = source.Select(sourceId).ToHashSet();
        for (var index = target.Count - 1; index >= 0; index--)
            if (!sourceIds.Contains(GetId(target[index]))) target.RemoveAt(index);
        foreach (var item in source)
        {
            var existing = target.FirstOrDefault(candidate => GetId(candidate) == sourceId(item));
            if (existing is null) target.Add(create(item)); else update(existing, item);
        }
    }

    private static int GetId<T>(T item) => item switch
    {
        ControllerTopologyItem controller => controller.Controller.Id,
        PortTopologyItem port => port.Port.Id,
        PumpTopologyItem pump => pump.Pump.Id,
        NozzleTopologyItem nozzle => nozzle.Nozzle.Id,
        ProbeTopologyItem probe => probe.Probe.Id,
        _ => throw new ArgumentOutOfRangeException(nameof(item)),
    };
}
