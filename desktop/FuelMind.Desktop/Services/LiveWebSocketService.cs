using System.Net.WebSockets;
using System.IO;
using System.Text;
using FuelMind.Desktop.Configuration;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.State;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace FuelMind.Desktop.Services;

public enum LiveConnectionState { Disconnected, Connecting, Connected, Reconnecting, Disconnecting }

public sealed class LiveWebSocketService : IDisposable
{
    private const int MaxMessageBytes = 1_048_576;
    private readonly LiveMessageParser _parser;
    private readonly ApiSettings _settings;
    private readonly ConnectionSettings _connectionSettings;
    private readonly ILogger<LiveWebSocketService> _logger;
    private readonly LiveDataStore _liveDataStore;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly SemaphoreSlim _sendGate = new(1, 1);
    private ClientWebSocket? _socket;
    private CancellationTokenSource? _receiveCancellation;
    private Task? _receiveTask;
    private Task? _reconnectTask;
    private CancellationTokenSource? _reconnectCancellation;
    private readonly object _reconnectSync = new();
    private int? _lastStationId;
    private bool _manualDisconnectRequested;
    private const string PongPayload = "{\"event_type\":\"pong\"}";

    public LiveWebSocketService(LiveMessageParser parser, IOptions<ApiSettings> settings, IOptions<ConnectionSettings> connectionSettings, ILogger<LiveWebSocketService> logger, LiveDataStore liveDataStore)
    { _parser = parser; _settings = settings.Value; _connectionSettings = connectionSettings.Value; _logger = logger; _liveDataStore = liveDataStore; }

    public LiveConnectionState ConnectionState { get; private set; } = LiveConnectionState.Disconnected;
    public int? ConnectedStationId { get; private set; }
    public int ReconnectSeconds => _connectionSettings.ReconnectSeconds;
    public event EventHandler<LiveMessageParseResult>? MessageReceived;
    public event EventHandler<LiveConnectionState>? ConnectionStateChanged;

    public async Task ConnectAsync(int stationId, CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken);
        try
        {
            _manualDisconnectRequested = false;
            if (ConnectionState is LiveConnectionState.Connecting or LiveConnectionState.Connected) return;
            SetState(LiveConnectionState.Connecting);
            _logger.LogInformation("Connecting live socket for station {StationId}", stationId);
            var socket = new ClientWebSocket();
            await socket.ConnectAsync(BuildUri(stationId), cancellationToken);
            _socket = socket; ConnectedStationId = stationId; _receiveCancellation = new CancellationTokenSource();
            _lastStationId = stationId;
            SetState(LiveConnectionState.Connected);
            _receiveTask = ReceiveLoopAsync(socket, _receiveCancellation.Token);
            _logger.LogInformation("Live socket connected for station {StationId}", stationId);
        }
        catch
        {
            SetState(LiveConnectionState.Disconnected);
            throw;
        }
        finally { _gate.Release(); }
    }

    public async Task DisconnectAsync(CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync();
        try { _manualDisconnectRequested = true; _reconnectCancellation?.Cancel(); await CleanupAsync(cancellationToken, awaitReceiveTask: true); }
        finally { _gate.Release(); }
    }

    private async Task<bool> ReconnectOnceAsync(CancellationToken cancellationToken = default)
    {
        if (_lastStationId is not int stationId)
        {
            _logger.LogWarning("Live reconnect skipped because no station is available.");
            return false;
        }

        SetState(LiveConnectionState.Reconnecting);
        try
        {
            await Task.Delay(TimeSpan.FromSeconds(ReconnectSeconds), cancellationToken);
            await ConnectAsync(stationId, cancellationToken);
            return ConnectionState == LiveConnectionState.Connected;
        }
        catch (Exception exception) when (exception is WebSocketException or OperationCanceledException)
        {
            _logger.LogWarning(exception, "Live reconnect attempt failed for station {StationId}", stationId);
            SetState(LiveConnectionState.Disconnected);
            return false;
        }
    }

    private void StartReconnectLoop(CancellationToken cancellationToken)
    {
        lock (_reconnectSync)
        {
            if (_reconnectTask is { IsCompleted: false }) return;
            _reconnectCancellation?.Dispose();
            _reconnectCancellation = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            _reconnectTask = ReconnectLoopAsync(_reconnectCancellation.Token);
        }
    }

    private async Task ReconnectLoopAsync(CancellationToken cancellationToken)
    {
        try
        {
            while (!cancellationToken.IsCancellationRequested && !_manualDisconnectRequested)
            {
                if (await ReconnectOnceAsync(cancellationToken)) return;
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested) { }
        catch (Exception exception) { _logger.LogWarning(exception, "Live reconnect loop failed"); }
        finally { lock (_reconnectSync) { _reconnectTask = null; _reconnectCancellation?.Dispose(); _reconnectCancellation = null; } }
    }

    private async Task ReceiveLoopAsync(ClientWebSocket socket, CancellationToken cancellationToken)
    {
        try
        {
            while (socket.State == WebSocketState.Open && !cancellationToken.IsCancellationRequested)
            {
                var message = await ReceiveTextAsync(socket, cancellationToken);
                if (message is null) { _logger.LogInformation("Live socket remote close received"); break; }
                var result = _parser.Parse(message);
                if (result.Message is Dtos.Live.PingDto) { _logger.LogDebug("Live ping received"); await SendPongAsync(socket, cancellationToken); continue; }
                UpdateLiveDataStore(result.Message);
                _logger.LogDebug("Live message received: {EventType}", result.EventType);
                MessageReceived?.Invoke(this, result);
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested) { }
        catch (Exception exception) { _logger.LogWarning(exception, "Live socket receive loop failed"); }
        finally
        {
            if (!cancellationToken.IsCancellationRequested && !_manualDisconnectRequested)
            {
                await CleanupAsync(CancellationToken.None, awaitReceiveTask: false);
                StartReconnectLoop(CancellationToken.None);
            }

            _logger.LogInformation("Live socket receive loop ended");
        }
    }

    private static async Task<string?> ReceiveTextAsync(ClientWebSocket socket, CancellationToken cancellationToken)
    {
        var buffer = new byte[8192]; await using var stream = new MemoryStream();
        WebSocketReceiveResult result;
        do { result = await socket.ReceiveAsync(buffer, cancellationToken); if (result.MessageType == WebSocketMessageType.Close) return null; if (result.MessageType != WebSocketMessageType.Text) continue; if (stream.Length + result.Count > MaxMessageBytes) throw new InvalidDataException("Live message size limit exceeded."); await stream.WriteAsync(buffer.AsMemory(0, result.Count), cancellationToken); } while (!result.EndOfMessage);
        return Encoding.UTF8.GetString(stream.ToArray());
    }

    private Uri BuildUri(int stationId) => new(_settings.WebSocketBaseUrl.TrimEnd('/') + $"/stations/{stationId}/live", UriKind.Absolute);
    private async Task SendPongAsync(ClientWebSocket socket, CancellationToken token) { var bytes = Encoding.UTF8.GetBytes(PongPayload); await _sendGate.WaitAsync(token); try { await socket.SendAsync(bytes, WebSocketMessageType.Text, true, token); _logger.LogDebug("Live pong sent"); } finally { _sendGate.Release(); } }
    private async Task CleanupAsync(CancellationToken token, bool awaitReceiveTask) { if (_socket is null) return; SetState(LiveConnectionState.Disconnecting); _logger.LogInformation("Live socket disconnect requested"); _receiveCancellation?.Cancel(); var socket = _socket; _socket = null; if (socket.State is WebSocketState.Open or WebSocketState.CloseReceived) { try { await socket.CloseOutputAsync(WebSocketCloseStatus.NormalClosure, "Client disconnect", token); } catch (WebSocketException) { } } if (awaitReceiveTask && _receiveTask is not null) { try { await _receiveTask; } catch (OperationCanceledException) { } } socket.Dispose(); _receiveCancellation?.Dispose(); _receiveCancellation = null; _receiveTask = null; ConnectedStationId = null; SetState(LiveConnectionState.Disconnected); _logger.LogInformation("Live socket disconnected"); }
    private void SetState(LiveConnectionState state) { if (ConnectionState == state) return; ConnectionState = state; _liveDataStore.UpdateConnectionState(state); ConnectionStateChanged?.Invoke(this, state); }
    private void UpdateLiveDataStore(object? message)
    {
        switch (message)
        {
            case ConnectionReadyDto connectionReady:
                _liveDataStore.ApplyConnectionReady(connectionReady);
                break;
            case SimulationTickDto simulationTick:
                _liveDataStore.ApplySimulationTick(simulationTick);
                break;
            case AlarmCreatedDto:
                // Alarm consumers receive this through MessageReceived.  It must
                // never replace or clear the station telemetry collections.
                break;
        }
    }
    public void Dispose() { _manualDisconnectRequested = true; _reconnectCancellation?.Cancel(); CleanupAsync(CancellationToken.None, awaitReceiveTask: true).GetAwaiter().GetResult(); _reconnectCancellation?.Dispose(); _gate.Dispose(); _sendGate.Dispose(); }
}
