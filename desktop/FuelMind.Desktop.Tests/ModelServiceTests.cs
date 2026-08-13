using System.Net;
using System.Text.Json;
using FuelMind.Desktop.Dtos.Auth;
using FuelMind.Desktop.Dtos.Models;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class ModelServiceTests
{
    [Fact]
    public async Task GetModels_UsesAuthenticatedModelsEndpoint()
    {
        var handler = new RecordingHandler("[]");
        var service = CreateService(handler);

        var result = await service.GetModelsAsync();

        Assert.Empty(result);
        Assert.Equal(HttpMethod.Get, handler.Method);
        Assert.Equal("/api/models", handler.Path);
        Assert.Equal("Bearer", handler.AuthorizationScheme);
        Assert.Equal("test-token", handler.AuthorizationParameter);
    }

    [Fact]
    public async Task TrainModel_PostsBackendContract()
    {
        var handler = new RecordingHandler(ModelJson(includeDiagnostics: true));
        var service = CreateService(handler);

        var response = await service.TrainAnomalyModelAsync(new TrainAnomalyModelRequestDto
        {
            StationId = 9,
            ModelFamily = "pump",
            SourceTypes = ["SIMULATION"],
        });

        Assert.Equal(HttpMethod.Post, handler.Method);
        Assert.Equal("/api/ml/train-anomaly-model", handler.Path);
        Assert.Equal("v0001", response.Version);
        using var body = JsonDocument.Parse(handler.Body!);
        Assert.Equal(9, body.RootElement.GetProperty("station_id").GetInt32());
        Assert.Equal("pump", body.RootElement.GetProperty("model_family").GetString());
    }

    [Fact]
    public async Task ActivateModel_PatchesVersionWithoutArbitraryBodyOrPath()
    {
        var handler = new RecordingHandler(ModelJson(includeDiagnostics: false));
        var service = CreateService(handler);

        var response = await service.ActivateModelAsync(41);

        Assert.Equal(HttpMethod.Patch, handler.Method);
        Assert.Equal("/api/models/41/activate", handler.Path);
        Assert.Null(handler.Body);
        Assert.True(response.IsActive);
    }

    private static ModelService CreateService(RecordingHandler handler)
    {
        var auth = new AuthState();
        auth.SetAuthentication(new TokenResponseDto
        {
            AccessToken = "test-token",
            TokenType = "Bearer",
            ExpiresIn = 3600,
        });
        var client = new HttpClient(handler) { BaseAddress = new Uri("http://localhost/api/") };
        var api = new ApiClient(client, new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
        }, auth, NullLogger<ApiClient>.Instance);
        return new ModelService(api);
    }

    private static string ModelJson(bool includeDiagnostics) => $$"""
        {
          "id": 1,
          "model_type": "isolation_forest",
          "model_family": "pump",
          "version": "v0001",
          "trained_at": "2026-08-12T06:42:00Z",
          "training_start_date": "2026-05-14",
          "training_end_date": "2026-08-12",
          "training_row_count": 42,
          "feature_count": 20,
          "feature_names": ["flow_rate"],
          "is_active": true,
          "artifact_available": true,
          "artifact_file_name": "isolation_forest_pump_v0001.joblib",
          "artifact_size_bytes": 1066541,
          "artifact_schema_version": 1,
          "training_outlier_fraction": 0.03,
          "validation_status": null,
          "scenario_detection_count": null,
          "scenario_total_count": null,
          "normal_false_positive_rate": null,
          "latest_sensor_reading_at": "2026-08-19T08:30:00Z",
          "new_sensor_rows_since_training": 14230{{(includeDiagnostics ? ",\n  \"training_diagnostics\": {}" : string.Empty)}}
        }
        """;

    private sealed class RecordingHandler(string responseJson) : HttpMessageHandler
    {
        public HttpMethod? Method { get; private set; }
        public string? Path { get; private set; }
        public string? Body { get; private set; }
        public string? AuthorizationScheme { get; private set; }
        public string? AuthorizationParameter { get; private set; }

        protected override async Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            Method = request.Method;
            Path = request.RequestUri?.AbsolutePath;
            Body = request.Content is null
                ? null
                : await request.Content.ReadAsStringAsync(cancellationToken);
            AuthorizationScheme = request.Headers.Authorization?.Scheme;
            AuthorizationParameter = request.Headers.Authorization?.Parameter;
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(responseJson),
            };
        }
    }
}
