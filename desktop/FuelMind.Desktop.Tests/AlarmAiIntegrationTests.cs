using System.Text.Json;
using System.Windows.Threading;
using FuelMind.Desktop.Configuration;
using FuelMind.Desktop.Dtos.Alarms;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using FuelMind.Desktop.ViewModels;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class AlarmAiIntegrationTests
{
    private const string HybridAlarmJson = """
        {
          "id":14,"station_id":1,"tank_id":null,"pump_id":4,"alarm_type":"LOW_FLOW",
          "severity":"CRITICAL","title":"Low Flow","description":"Flow is below normal.",
          "recommended_action":"Check the pump filter.",
          "probable_causes":[{"description":"Filter restriction"}],
          "anomaly_score":91.25,"risk_level":"CRITICAL","decision_source":"HYBRID",
          "anomaly_type":"EQUIPMENT_ANOMALY","model_version":"v0001","model_outlier":true,
          "triggered_rules_json":["LOW_FLOW"],
          "findings_json":[{
            "feature_name":"flow_rate","display_name":"Pompa debisi",
            "current_value":24.3,"reference_value":42.1,
            "percent_difference":-42.3,"direction":"LOW",
            "message":"Pompa debisi normal medyanın yaklaşık %42.3 altında."
          }],
          "recommended_checks_json":["Check the pump filter."],"data_quality_note":null,
          "status":"NEW","detected_at":"2026-08-12T09:30:00Z","resolution_note":null
        }
        """;

    [Fact]
    public void AlarmDetailDtoDeserializesCompleteAiContract()
    {
        var alarm = JsonSerializer.Deserialize<AlarmDto>(HybridAlarmJson);

        Assert.NotNull(alarm);
        Assert.Equal(91.25m, alarm.AnomalyScore);
        Assert.Equal("CRITICAL", alarm.RiskLevel);
        Assert.Equal("HYBRID", alarm.DecisionSource);
        Assert.Equal("EQUIPMENT_ANOMALY", alarm.AnomalyType);
        Assert.Equal("v0001", alarm.ModelVersion);
        Assert.True(alarm.ModelOutlier);
        Assert.Equal(["LOW_FLOW"], alarm.TriggeredRules);
        Assert.Single(alarm.Findings!);
        Assert.Contains("Mevcut: 24.3 L/dk", alarm.FindingsDisplay.Single());
        Assert.Contains("Sapma: %42 düşük", alarm.FindingsDisplay.Single());
        Assert.Single(alarm.ProbableCauses!);
        Assert.Single(alarm.RecommendedChecks!);
        Assert.True(alarm.HasAiAnalysis);
        Assert.Contains("Kural ve yapay zekâ", alarm.DecisionSourceDisplay);
        Assert.Equal("Pompa Debi Düşüşü", alarm.TitleDisplay);
        Assert.Equal("Yeni", alarm.StatusDisplay);
        Assert.Equal("Kritik", alarm.RiskLevelDisplay);
        Assert.Equal("Pompa filtresini, hat basıncını ve pompa performansını kontrol edin.", alarm.RecommendedActionDisplay);
    }

    [Fact]
    public void LegacyRuleOnlyAlarmHasSafeNoAiState()
    {
        var alarm = JsonSerializer.Deserialize<AlarmDto>("""
            {"id":2,"station_id":1,"alarm_type":"LOW_FLOW","severity":"HIGH",
             "title":"Low Flow","status":"NEW","detected_at":"2026-08-12T09:00:00Z"}
            """);

        Assert.NotNull(alarm);
        Assert.False(alarm.HasAiAnalysis);
        Assert.True(alarm.HasNoAiAnalysis);
        Assert.Equal("—", alarm.AiRiskDisplay);
    }

    [Fact]
    public void SelectedAlarmLoadsRestDetailAndRefreshesAiPanelSource()
    {
        var hybrid = JsonSerializer.Deserialize<AlarmDto>(HybridAlarmJson)!;
        var service = new FakeAlarmService { Detail = hybrid };
        using var socket = CreateSocket();
        var viewModel = new AlarmsViewModel(service, socket);
        var summary = new AlarmDto { Id = 14, StationId = 1, Title = "Low Flow", Status = "NEW" };
        viewModel.Alarms.Add(summary);

        viewModel.SelectedAlarm = summary;

        Assert.Equal(14, service.LastDetailId);
        Assert.Same(hybrid, viewModel.SelectedAlarm);
        Assert.Equal("v0001", viewModel.SelectedAlarm.ModelVersion);
        Assert.Equal("HYBRID", viewModel.SelectedAlarm.DecisionSource);
        Assert.Single(viewModel.SelectedAlarm.Findings!);
    }

    [Fact]
    public async Task ExistingAlarmLifecycleStillUsesOriginalTransitionEndpoint()
    {
        var current = new AlarmDto { Id = 14, StationId = 1, Status = "NEW" };
        var acknowledged = new AlarmDto
        {
            Id = 14,
            StationId = 1,
            Status = "ACKNOWLEDGED",
            DecisionSource = "HYBRID",
            ModelVersion = "v0001",
        };
        var service = new FakeAlarmService { Detail = current, UpdateResult = acknowledged };
        using var socket = CreateSocket();
        var viewModel = new AlarmsViewModel(service, socket);
        viewModel.Alarms.Add(current);
        viewModel.SelectedAlarm = current;

        await viewModel.AcknowledgeCommand.ExecuteAsync(null);

        Assert.Equal("acknowledge", service.LastAction);
        Assert.Equal("ACKNOWLEDGED", viewModel.SelectedAlarm?.Status);
        Assert.Equal("v0001", viewModel.SelectedAlarm?.ModelVersion);
    }

    private static LiveWebSocketService CreateSocket()
    {
        var store = new LiveDataStore(Dispatcher.CurrentDispatcher);
        return new LiveWebSocketService(
            new LiveMessageParser(new JsonSerializerOptions { PropertyNameCaseInsensitive = true }),
            Options.Create(new ApiSettings
            {
                BaseUrl = "http://localhost:8000/api/",
                WebSocketBaseUrl = "ws://localhost:8000/api/ws",
            }),
            Options.Create(new ConnectionSettings { ReconnectSeconds = 1 }),
            NullLogger<LiveWebSocketService>.Instance,
            store);
    }

    private sealed class FakeAlarmService : IAlarmService
    {
        public AlarmDto Detail { get; init; } = new();
        public AlarmDto? UpdateResult { get; init; }
        public int? LastDetailId { get; private set; }
        public string? LastAction { get; private set; }

        public Task<IReadOnlyList<AlarmDto>> GetAllAsync(CancellationToken token = default) =>
            Task.FromResult<IReadOnlyList<AlarmDto>>([]);

        public Task<AlarmDto> GetByIdAsync(int id, CancellationToken token = default)
        {
            LastDetailId = id;
            return Task.FromResult(Detail);
        }

        public Task<AlarmDto> UpdateAsync(
            int id,
            string action,
            string? note = null,
            CancellationToken token = default)
        {
            LastAction = action;
            return Task.FromResult(UpdateResult ?? Detail);
        }
    }
}
