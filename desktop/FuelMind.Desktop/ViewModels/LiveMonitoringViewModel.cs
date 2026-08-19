using System.ComponentModel;
using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class LiveMonitoringViewModel : ObservableObject
{
    private readonly LiveDataStore _liveDataStore;
    private readonly LiveWebSocketService _liveWebSocketService;

    public LiveMonitoringViewModel(LiveDataStore liveDataStore, LiveWebSocketService liveWebSocketService)
    {
        _liveDataStore = liveDataStore;
        _liveWebSocketService = liveWebSocketService;
        StationId = _liveDataStore.SelectedStationId;
        _liveDataStore.PropertyChanged += OnLiveDataStorePropertyChanged;
        _liveDataStore.Tanks.CollectionChanged += (_, _) => OnPropertyChanged(nameof(TankCount));
        _liveDataStore.Pumps.CollectionChanged += (_, _) => OnPropertyChanged(nameof(PumpCount));
    }

    [ObservableProperty]
    private int _stationId;

    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(ConnectCommand))]
    [NotifyCanExecuteChangedFor(nameof(DisconnectCommand))]
    private bool _isBusy;

    [ObservableProperty]
    private string? _lastError;

    public LiveConnectionState ConnectionState => _liveDataStore.ConnectionState;
    public int? ConnectedStationId => _liveDataStore.ConnectedStationId;
    public DateTimeOffset? LastMessageAt => _liveDataStore.LastMessageAt;
    public int? LastSequence => _liveDataStore.LastSequence;
    public ObservableCollection<TankLiveDataDto> Tanks => _liveDataStore.Tanks;
    public int TankCount => _liveDataStore.Tanks.Count;
    public ObservableCollection<PumpLiveDataDto> Pumps => _liveDataStore.Pumps;
    public int PumpCount => _liveDataStore.Pumps.Count;
    public bool HasSequenceGap => _liveDataStore.HasSequenceGap;
    public int? ExpectedSequence => _liveDataStore.ExpectedSequence;
    public int? ReceivedSequence => _liveDataStore.ReceivedSequence;

    public async Task ConnectForSelectedStationAsync()
    {
        var stationId = _liveDataStore.SelectedStationId;
        if (stationId <= 0 || IsBusy)
        {
            return;
        }

        StationId = stationId;
        if (_liveWebSocketService.ConnectionState == LiveConnectionState.Connected &&
            _liveWebSocketService.ConnectedStationId == stationId)
        {
            return;
        }

        LastError = null;
        IsBusy = true;
        try
        {
            if (_liveWebSocketService.ConnectionState is not LiveConnectionState.Disconnected)
            {
                await _liveWebSocketService.DisconnectAsync();
            }
            await _liveWebSocketService.ConnectAsync(stationId);
        }
        catch (Exception exception) { LastError = exception.Message; }
        finally { IsBusy = false; }
    }

    [RelayCommand(CanExecute = nameof(CanConnect))]
    private async Task ConnectAsync()
    {
        LastError = null;
        IsBusy = true;
        try
        {
            _liveDataStore.SelectedStationId = StationId;
            await _liveWebSocketService.ConnectAsync(StationId);
        }
        catch (Exception exception) { LastError = exception.Message; }
        finally { IsBusy = false; }
    }

    [RelayCommand(CanExecute = nameof(CanDisconnect))]
    private async Task DisconnectAsync()
    {
        LastError = null;
        IsBusy = true;
        try { await _liveWebSocketService.DisconnectAsync(); }
        catch (Exception exception) { LastError = exception.Message; }
        finally { IsBusy = false; }
    }

    private bool CanConnect() => !IsBusy && StationId > 0 && ConnectionState == LiveConnectionState.Disconnected;
    private bool CanDisconnect() => !IsBusy && ConnectionState is LiveConnectionState.Connecting or LiveConnectionState.Connected or LiveConnectionState.Reconnecting;

    partial void OnStationIdChanged(int value)
    {
        if (_liveDataStore.SelectedStationId != value)
        {
            _liveDataStore.SelectedStationId = value;
        }
        ConnectCommand.NotifyCanExecuteChanged();
    }

    private void OnLiveDataStorePropertyChanged(object? sender, PropertyChangedEventArgs eventArgs)
    {
        switch (eventArgs.PropertyName)
        {
            case nameof(LiveDataStore.ConnectionState):
                OnPropertyChanged(nameof(ConnectionState));
                ConnectCommand.NotifyCanExecuteChanged();
                DisconnectCommand.NotifyCanExecuteChanged();
                break;
            case nameof(LiveDataStore.SelectedStationId):
                if (StationId != _liveDataStore.SelectedStationId)
                {
                    StationId = _liveDataStore.SelectedStationId;
                }
                break;
            case nameof(LiveDataStore.ConnectedStationId): OnPropertyChanged(nameof(ConnectedStationId)); break;
            case nameof(LiveDataStore.LastMessageAt): OnPropertyChanged(nameof(LastMessageAt)); break;
            case nameof(LiveDataStore.LastSequence): OnPropertyChanged(nameof(LastSequence)); break;
            case nameof(LiveDataStore.Tanks):
                OnPropertyChanged(nameof(Tanks));
                OnPropertyChanged(nameof(TankCount));
                break;
            case nameof(LiveDataStore.Pumps):
                OnPropertyChanged(nameof(Pumps));
                OnPropertyChanged(nameof(PumpCount));
                break;
            case nameof(LiveDataStore.HasSequenceGap): OnPropertyChanged(nameof(HasSequenceGap)); break;
            case nameof(LiveDataStore.ExpectedSequence): OnPropertyChanged(nameof(ExpectedSequence)); break;
            case nameof(LiveDataStore.ReceivedSequence): OnPropertyChanged(nameof(ReceivedSequence)); break;
        }
    }
}
