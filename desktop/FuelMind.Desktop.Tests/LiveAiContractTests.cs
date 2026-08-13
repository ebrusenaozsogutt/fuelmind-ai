using System.Text.Json;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class LiveAiContractTests
{
    private const string LiveTick = """
        {
          "event_type":"simulation_tick","simulation_run_id":8,"station_id":1,
          "simulation_time":"2026-08-12T09:30:00Z","sequence":31,
          "tanks":[],
          "pumps":[{"pump_id":4,"tank_id":1,"status":"ACTIVE","flow_rate":4.2,"pressure":3.1,"motor_current":12.4,"temperature":42.0,"error_count":0,"working_duration":100.0}],
          "sales":[],"events":[],"active_scenarios":[],
          "ai_results":[{
            "entity_type":"PUMP","entity_id":4,"station_id":1,"timestamp":"2026-08-12T09:30:00Z",
            "ai_state":"READY","risk_score":91,"risk_level":"CRITICAL","decision_source":"HYBRID",
            "severity":"CRITICAL","anomaly_type":"EQUIPMENT_ANOMALY","model_outlier":true,
            "triggered_rules":["LOW_FLOW"],"findings":[{"feature_name":"flow_rate","display_name":"Pompa debisi","current_value":4.2,"reference_value":40,"percent_difference":-89.5,"direction":"LOW","message":"Pompa debisi düşük."}],
            "probable_causes":["Filter restriction"],"recommended_checks":["Check pump filter."],
            "data_quality_note":null,"model_version":"v0001","decision_function":-0.41,"is_anomaly":true
          }],"generated_at":"2026-08-12T09:30:00Z"
        }
        """;
    private const string AiEvaluation = """
        {
          "event_type":"anomaly_evaluation","simulation_run_id":8,"station_id":1,
          "simulation_time":"2026-08-12T09:30:00Z","sequence":31,"results":[{
            "entity_type":"PUMP","entity_id":4,"station_id":1,"timestamp":"2026-08-12T09:30:00Z",
            "ai_state":"READY","risk_score":91,"risk_level":"CRITICAL","decision_source":"HYBRID",
            "severity":"CRITICAL","anomaly_type":"EQUIPMENT_ANOMALY","model_outlier":true,
            "triggered_rules":["LOW_FLOW"],"findings":[{"feature_name":"flow_rate","display_name":"Pompa debisi","current_value":4.2,"reference_value":40,"percent_difference":-89.5,"direction":"LOW","message":"Pompa debisi düşük."}],
            "probable_causes":["Filter restriction"],"recommended_checks":["Check pump filter."],
            "data_quality_note":null,"model_version":"v0001","decision_function":-0.41,"is_anomaly":true
          }]
        }
        """;

    [Fact]
    public void PumpAiResultDeserializesWithAllOperationalFields()
    {
        var parser = new LiveMessageParser(new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        var parsed = parser.Parse(LiveTick);
        var tick = Assert.IsType<SimulationTickDto>(parsed.Message);
        var result = Assert.Single(tick.AiResults);

        Assert.Equal(91, result.RiskScore);
        Assert.Equal("CRITICAL", result.RiskLevel);
        Assert.Equal("HYBRID", result.DecisionSource);
        Assert.Equal("v0001", result.ModelVersion);
        Assert.Equal("Risk: 91 (CRITICAL)", result.PumpBadgeDisplay);
        Assert.Single(result.Findings);
        Assert.Contains("Mevcut: 4.2 L/dk", result.FindingsDisplay.Single());
        Assert.Single(result.ProbableCauses);
        Assert.Single(result.RecommendedChecks);
    }

    [Fact]
    public void LiveStoreAssociatesAiResultWithPumpWithoutBlockingCaller()
    {
        var dispatcher = System.Windows.Threading.Dispatcher.CurrentDispatcher;
        var store = new LiveDataStore(dispatcher);
        var tick = Assert.IsType<SimulationTickDto>(
            new LiveMessageParser(new JsonSerializerOptions { PropertyNameCaseInsensitive = true }).Parse(LiveTick).Message);

        store.ApplySimulationTick(tick);
        var evaluation = Assert.IsType<AnomalyEvaluationDto>(
            new LiveMessageParser(new JsonSerializerOptions { PropertyNameCaseInsensitive = true }).Parse(AiEvaluation).Message);
        store.ApplyAnomalyEvaluation(evaluation);
        dispatcher.Invoke(() => { }, System.Windows.Threading.DispatcherPriority.ApplicationIdle);

        var pump = Assert.Single(store.Pumps);
        Assert.NotNull(pump.AiAnalysis);
        Assert.Equal(91, pump.AiAnalysis!.RiskScore);
        Assert.Equal("HYBRID", pump.AiAnalysis.DecisionSource);
    }

    [Theory]
    [InlineData("WARMING_UP", "Geçmiş verisi toplanıyor…")]
    [InlineData("NO_ACTIVE_MODEL", "Aktif yapay zekâ modeli yok")]
    [InlineData("UNAVAILABLE", "Yapay zekâ geçici olarak kullanılamıyor")]
    [InlineData("READY", "NORMAL")]
    public void AiOperationalStatesHaveUserFacingText(string state, string expected)
    {
        var result = new LiveAnomalyResultDto { AiState = state, RiskLevel = "NORMAL" };
        Assert.Equal(expected, result.StateDisplay);
    }

    [Fact]
    public void PumpBadgeNeverFallsBackToMeaninglessAiPlaceholder()
    {
        var warmingUp = new LiveAnomalyResultDto { AiState = "WARMING_UP" };

        Assert.Equal("Geçmiş verisi toplanıyor…", warmingUp.PumpBadgeDisplay);
        Assert.NotEqual("AI", warmingUp.PumpBadgeDisplay);
    }
}
