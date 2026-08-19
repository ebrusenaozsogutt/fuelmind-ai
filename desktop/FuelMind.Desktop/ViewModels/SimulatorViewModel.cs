using System.Net;
using System.Net.Http;
using System.Net.WebSockets;
using System.Text.Json;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Simulations;
using FuelMind.Desktop.Dtos.Tanks;
using FuelMind.Desktop.Dtos.Deliveries;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using Microsoft.Extensions.Logging;

namespace FuelMind.Desktop.ViewModels;

/// <summary>Creates and controls one REALTIME simulation run through the authenticated API client.</summary>
public sealed partial class SimulatorViewModel : ObservableObject
{
    private readonly ApiClient _apiClient;
    private readonly ILogger<SimulatorViewModel> _logger;
    private readonly LiveDataStore _liveDataStore;
    private readonly LiveWebSocketService _liveWebSocketService;

    public SimulatorViewModel(
        ApiClient apiClient,
        ILogger<SimulatorViewModel> logger,
        LiveDataStore liveDataStore,
        LiveWebSocketService liveWebSocketService)
    {
        _apiClient = apiClient;
        _logger = logger;
        _liveDataStore = liveDataStore;
        _liveWebSocketService = liveWebSocketService;
        StationId = _liveDataStore.SelectedStationId;
        _liveDataStore.PropertyChanged += (_, args) =>
        {
            if (args.PropertyName == nameof(LiveDataStore.SelectedStationId) &&
                StationId != _liveDataStore.SelectedStationId)
            {
                StationId = _liveDataStore.SelectedStationId;
            }
        };
    }

    [ObservableProperty, NotifyCanExecuteChangedFor(nameof(CreateSimulationCommand)), NotifyCanExecuteChangedFor(nameof(PrepareDemoStockCommand)), NotifyCanExecuteChangedFor(nameof(StartCommand)), NotifyCanExecuteChangedFor(nameof(PauseCommand)), NotifyCanExecuteChangedFor(nameof(ResumeCommand)), NotifyCanExecuteChangedFor(nameof(StopCommand))] private int _stationId;
    [ObservableProperty, NotifyCanExecuteChangedFor(nameof(CreateSimulationCommand))] private int _tickIntervalMilliseconds = 1000;
    [ObservableProperty, NotifyCanExecuteChangedFor(nameof(CreateSimulationCommand))] private int _simulationStepSeconds = 5;
    [ObservableProperty, NotifyCanExecuteChangedFor(nameof(CreateSimulationCommand))] private double _speedMultiplier = 1;
    [ObservableProperty] private int _randomSeed = 42;
    [ObservableProperty, NotifyCanExecuteChangedFor(nameof(CreateSimulationCommand))] private int _persistEveryNTicks = 1;
    [ObservableProperty, NotifyCanExecuteChangedFor(nameof(CreateSimulationCommand)), NotifyCanExecuteChangedFor(nameof(PrepareDemoStockCommand)), NotifyCanExecuteChangedFor(nameof(StartCommand)), NotifyCanExecuteChangedFor(nameof(PauseCommand)), NotifyCanExecuteChangedFor(nameof(ResumeCommand)), NotifyCanExecuteChangedFor(nameof(StopCommand))] private bool _isBusy;
    [ObservableProperty] private string? _lastError;
    [ObservableProperty] private SimulationRunDto? _currentRun;
    [ObservableProperty] private SimulationRunDto? _activeRun;
    [ObservableProperty] private string? _stockPreparationResult;

    public int? RunId => CurrentRun?.Id;
    public string Status => CurrentRun?.Status ?? "--";
    public string Mode => CurrentRun?.Mode ?? "REALTIME";
    public int? SequenceNumber => CurrentRun?.SequenceNumber;
    public DateTimeOffset? CurrentSimulationTime => CurrentRun?.CurrentSimulationTime;
    public int? RunStationId => CurrentRun?.StationId;
    public int? ActiveRunId => ActiveRun?.Id;
    public string ActiveRunStatus => ActiveRun?.Status ?? "Aktif run yok";
    public int? ActiveRunStationId => ActiveRun?.StationId;
    public int? ActiveRunSequenceNumber => ActiveRun?.SequenceNumber;
    public DateTimeOffset? ActiveRunSimulationTime => ActiveRun?.CurrentSimulationTime;
    public string StartAvailabilityMessage => ActiveRun is null ? string.Empty : $"Önce aktif run {ActiveRun.Id}'u durdurun.";

    [RelayCommand(CanExecute = nameof(CanCreateSimulation))]
    private Task CreateSimulationAsync() => ExecuteAsync("Simülasyon oluşturulamadı.", () =>
        _apiClient.PostAsync<CreateSimulationRequestDto, SimulationRunDto>("simulations", new CreateSimulationRequestDto
        {
            StationId = StationId, Mode = "REALTIME", SimulationStartTime = DateTimeOffset.Now,
            TickIntervalMilliseconds = TickIntervalMilliseconds, SimulationStepSeconds = SimulationStepSeconds,
            SpeedMultiplier = SpeedMultiplier, RandomSeed = RandomSeed, PersistEveryNTicks = PersistEveryNTicks,
        }));

    [RelayCommand(CanExecute = nameof(CanPrepareDemoStock))]
    private async Task PrepareDemoStockAsync()
    {
        LastError = null; StockPreparationResult = null; IsBusy = true;
        try
        {
            _logger.LogInformation("Demo stock command started");
            _logger.LogInformation("Selected station: {StationId}", StationId);

            // The backend manager owns the only authoritative runner registry.
            // Do not infer activity from persisted historical run rows.
            var activeRun = await _apiClient.GetAsync<SimulationRunDto?>(
                $"simulations/active?station_id={StationId}");
            if (activeRun is not null)
            {
                _logger.LogInformation("Active realtime run found: {RunId}/{Status}", activeRun.Id, activeRun.Status);
                LastError = "Demo stoklarını hazırlamak için önce aktif simülasyonu durdurun.";
                return;
            }

            _logger.LogInformation("Active realtime run found: NONE");
            var tanks = await _apiClient.GetAsync<List<TankDto>>($"stations/{StationId}/tanks");
            _logger.LogInformation("Tank count: {TankCount}", tanks.Count);
            var prepared = 0;
            var skipped = 0;
            string? failedTank = null;
            string? failureReason = null;
            foreach (var tank in tanks)
            {
                var target = decimal.Round(tank.CapacityLiters * 0.65m, 3);
                var missing = decimal.Round(target - tank.CurrentLevelLiters, 3);
                _logger.LogInformation(
                    "Tank ID: {TankId}; Code: {Code}; Current: {CurrentLevel}; Capacity: {Capacity}; Target: {Target}; Missing: {Missing}",
                    tank.Id,
                    tank.Code,
                    tank.CurrentLevelLiters,
                    tank.CapacityLiters,
                    target,
                    missing);
                if (missing <= 0) { skipped++; continue; }
                try
                {
                    _logger.LogInformation("Sending delivery for tank {TankId} quantity {QuantityLiters}", tank.Id, missing);
                    var delivery = await _apiClient.PostAsync<CreateDeliveryRequestDto, DeliveryDto>("deliveries", new CreateDeliveryRequestDto { TankId = tank.Id, DeliveryTimestamp = DateTimeOffset.Now, QuantityLiters = missing });
                    _logger.LogInformation("Delivery response received for tank {TankId}", tank.Id);
                    if (delivery.Id <= 0 ||
                        delivery.TankId != tank.Id ||
                        delivery.DeliveryTimestamp == default ||
                        delivery.QuantityLiters != missing ||
                        delivery.LevelAfter < delivery.LevelBefore ||
                        string.IsNullOrWhiteSpace(delivery.SupplierName))
                    {
                        failedTank = tank.Code;
                        failureReason = "Sunucu yanıtı doğrulanamadı.";
                        break;
                    }
                    prepared++;
                }
                catch (ApiException exception) { failedTank = tank.Code; failureReason = GetUserMessage(exception, "Teslimat isteği başarısız oldu."); break; }
                catch (JsonException) { failedTank = tank.Code; failureReason = "Sunucudan geçersiz veri alındı."; break; }
                catch (HttpRequestException) { failedTank = tank.Code; failureReason = "Sunucuya ulaşılamadı."; break; }
                catch (TaskCanceledException) { failedTank = tank.Code; failureReason = "İstek zaman aşımına uğradı."; break; }
                catch (Exception) { failedTank = tank.Code; failureReason = "Beklenmeyen bir hata oluştu."; break; }
            }
            if (failedTank is null)
            {
                StockPreparationResult = $"{prepared} tank hazırlandı, {skipped} tank hedef seviyedeydi.";
            }
            else
            {
                StockPreparationResult = $"{prepared}/{tanks.Count} tank hazırlandı. {failedTank} işleminde hata oluştu.";
                LastError = $"Demo stok hazırlığı başarısız: {failureReason}";
            }
        }
        catch (ApiException exception) { LastError = GetUserMessage(exception, "Demo stokları hazırlanamadı."); }
        catch (HttpRequestException) { LastError = "Sunucuya ulaşılamadı."; }
        catch (TaskCanceledException) { LastError = "İstek zaman aşımına uğradı."; }
        catch (JsonException) { LastError = "Sunucudan geçersiz veri alındı."; }
        catch (Exception) { LastError = "Demo stokları hazırlanırken beklenmeyen bir hata oluştu."; }
        finally { IsBusy = false; }
    }

    [RelayCommand(CanExecute = nameof(CanStart))] private Task StartAsync() => ExecuteLifecycleAsync("start", "Simülasyon başlatılamadı.");
    [RelayCommand(CanExecute = nameof(CanPause))] private Task PauseAsync() => ExecuteLifecycleAsync("pause", "Simülasyon duraklatılamadı.");
    [RelayCommand(CanExecute = nameof(CanResume))] private Task ResumeAsync() => ExecuteLifecycleAsync("resume", "Simülasyona devam edilemedi.");
    [RelayCommand(CanExecute = nameof(CanStop))] private Task StopAsync() => ExecuteLifecycleAsync("stop", "Simülasyon durdurulamadı.");

    partial void OnCurrentRunChanged(SimulationRunDto? value)
    {
        OnPropertyChanged(nameof(RunId)); OnPropertyChanged(nameof(Status)); OnPropertyChanged(nameof(Mode));
        OnPropertyChanged(nameof(SequenceNumber)); OnPropertyChanged(nameof(CurrentSimulationTime)); OnPropertyChanged(nameof(RunStationId));
        NotifyLifecycleCommands();
    }

    partial void OnActiveRunChanged(SimulationRunDto? value)
    {
        OnPropertyChanged(nameof(ActiveRunId)); OnPropertyChanged(nameof(ActiveRunStatus));
        OnPropertyChanged(nameof(ActiveRunStationId)); OnPropertyChanged(nameof(ActiveRunSequenceNumber));
        OnPropertyChanged(nameof(ActiveRunSimulationTime)); OnPropertyChanged(nameof(StartAvailabilityMessage));
        NotifyLifecycleCommands();
    }

    partial void OnStationIdChanged(int value)
    {
        _liveDataStore.SelectedStationId = value;
        _ = RefreshActiveRunAsync();
    }

    private async Task ExecuteLifecycleAsync(string action, string failureMessage)
    {
        var runId = action == "start" ? CurrentRun?.Id : ActiveRun?.Id;
        if (runId is null) return;
        LastError = null; IsBusy = true;
        try
        {
            var updatedRun = await _apiClient.PostAsync<SimulationRunDto>($"simulations/{runId}/{action}");
            if (action == "start" || CurrentRun?.Id == updatedRun.Id) CurrentRun = updatedRun;
            if (ActiveRun?.Id == updatedRun.Id) ActiveRun = updatedRun;
            if (action == "start" &&
                string.Equals(updatedRun.Status, "RUNNING", StringComparison.OrdinalIgnoreCase))
            {
                await SelectStationAndConnectLiveAsync(updatedRun.StationId);
            }
            await RefreshActiveRunCoreAsync();
            if (string.Equals(updatedRun.Status, "FAILED", StringComparison.OrdinalIgnoreCase))
            {
                LastError = updatedRun.LastError ?? failureMessage;
            }
        }
        catch (ApiException exception) { LastError = GetUserMessage(exception, failureMessage); }
        catch (HttpRequestException) { LastError = "Sunucuya ulaşılamadı."; }
        catch (WebSocketException) { LastError = "Canlı istasyon bağlantısı kurulamadı."; }
        catch (TaskCanceledException) { LastError = "İstek zaman aşımına uğradı."; }
        finally { IsBusy = false; }
    }

    private async Task SelectStationAndConnectLiveAsync(int stationId)
    {
        _liveDataStore.SelectedStationId = stationId;
        if (StationId != stationId) StationId = stationId;

        if (_liveWebSocketService.ConnectionState == LiveConnectionState.Connected &&
            _liveWebSocketService.ConnectedStationId == stationId)
        {
            return;
        }

        if (_liveWebSocketService.ConnectionState is not LiveConnectionState.Disconnected)
        {
            await _liveWebSocketService.DisconnectAsync();
        }

        await _liveWebSocketService.ConnectAsync(stationId);
    }

    private async Task ExecuteAsync(string failureMessage, Func<Task<SimulationRunDto>> operation)
    {
        LastError = null; IsBusy = true;
        try { CurrentRun = await operation(); await RefreshActiveRunCoreAsync(); }
        catch (ApiException exception) { LastError = GetUserMessage(exception, failureMessage); }
        catch (HttpRequestException) { LastError = "Sunucuya ulaşılamadı."; }
        catch (TaskCanceledException) { LastError = "İstek zaman aşımına uğradı."; }
        finally { IsBusy = false; }
    }

    private bool CanCreateSimulation() => !IsBusy && StationId > 0 && TickIntervalMilliseconds > 0 && SimulationStepSeconds > 0 && SpeedMultiplier > 0 && PersistEveryNTicks > 0;
    private bool CanPrepareDemoStock() => !IsBusy && StationId > 0;
    public async Task RefreshActiveRunAsync()
    {
        if (IsBusy || StationId <= 0) return;
        LastError = null; IsBusy = true;
        try { await RefreshActiveRunCoreAsync(); }
        catch (ApiException exception) { LastError = GetUserMessage(exception, "Aktif run bilgisi alınamadı."); }
        catch (HttpRequestException) { LastError = "Sunucuya ulaşılamadı."; }
        catch (TaskCanceledException) { LastError = "İstek zaman aşımına uğradı."; }
        finally { IsBusy = false; }
    }

    private async Task RefreshActiveRunCoreAsync()
    {
        if (CurrentRun is not null)
        {
            CurrentRun = await _apiClient.GetAsync<SimulationRunDto>($"simulations/{CurrentRun.Id}");
        }
        ActiveRun = await _apiClient.GetAsync<SimulationRunDto?>(
            $"simulations/active?station_id={StationId}");
    }

    private bool CanStart() => !IsBusy && ActiveRun is null && string.Equals(CurrentRun?.Status, "CREATED", StringComparison.OrdinalIgnoreCase);
    private bool CanPause() => !IsBusy && string.Equals(ActiveRun?.Status, "RUNNING", StringComparison.OrdinalIgnoreCase);
    private bool CanResume() => !IsBusy && string.Equals(ActiveRun?.Status, "PAUSED", StringComparison.OrdinalIgnoreCase);
    private bool CanStop() => !IsBusy && ActiveRun is not null;
    private void NotifyLifecycleCommands() { StartCommand.NotifyCanExecuteChanged(); PauseCommand.NotifyCanExecuteChanged(); ResumeCommand.NotifyCanExecuteChanged(); StopCommand.NotifyCanExecuteChanged(); }

    private static string GetUserMessage(ApiException exception, string fallback) => exception.StatusCode switch
    {
        HttpStatusCode.Unauthorized => "Oturum doğrulanamadı. Lütfen tekrar giriş yapın.",
        HttpStatusCode.Forbidden => "Bu işlem için yetkiniz yok.",
        HttpStatusCode.UnprocessableEntity => "İstek doğrulanamadı.",
        _ => string.IsNullOrWhiteSpace(exception.Message) ? fallback : exception.Message,
    };
}
