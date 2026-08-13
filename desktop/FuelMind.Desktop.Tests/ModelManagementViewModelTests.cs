using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Auth;
using FuelMind.Desktop.Dtos.Models;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using FuelMind.Desktop.ViewModels;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class ModelManagementViewModelTests
{
    [Fact]
    public async Task LoadModels_FillsCollectionAndSelectsActiveSummary()
    {
        var service = new FakeModelService { Models = [Model(1, active: false), Model(2, active: true)] };
        var viewModel = Create(service, "ADMIN");

        await viewModel.LoadModelsAsync();

        Assert.Equal(2, viewModel.Models.Count);
        Assert.Equal(2, viewModel.ActiveModel?.Id);
        Assert.Equal(2, viewModel.SelectedModel?.Id);
        Assert.True(viewModel.HasActiveModel);
        Assert.NotNull(viewModel.LastRefreshAt);
    }

    [Fact]
    public async Task EmptyResponse_ProducesEmptyState()
    {
        var viewModel = Create(new FakeModelService(), "ADMIN");

        await viewModel.LoadModelsAsync();

        Assert.True(viewModel.IsEmpty);
        Assert.Null(viewModel.ActiveModel);
        Assert.False(viewModel.HasActiveModel);
    }

    [Fact]
    public async Task LoadWhileBusy_DoesNotStartASecondRequest()
    {
        var completion = new TaskCompletionSource<IReadOnlyList<ModelVersionDto>>();
        var service = new FakeModelService { GetTask = completion.Task };
        var viewModel = Create(service, "ADMIN");

        var first = viewModel.LoadModelsAsync();
        await Task.Yield();
        await viewModel.LoadModelsAsync();

        Assert.True(viewModel.IsLoading);
        Assert.Equal(1, service.GetCalls);
        completion.SetResult([Model(1, active: true)]);
        await first;
    }

    [Fact]
    public async Task ApiFailure_ProducesFriendlyErrorMessage()
    {
        var service = new FakeModelService { GetException = new HttpRequestException("connection refused") };
        var viewModel = Create(service, "ADMIN");

        await viewModel.LoadModelsAsync();

        Assert.True(viewModel.HasError);
        Assert.Contains("Backend sunucusuna ulaşılamadı", viewModel.ErrorMessage);
        Assert.False(viewModel.IsBusy);
    }

    [Fact]
    public void AdminCanManageModels()
    {
        var viewModel = Create(new FakeModelService(), "ADMIN");

        Assert.True(viewModel.CanManageModels);
        Assert.Equal("ADMIN", viewModel.CurrentUserRole);
    }

    [Fact]
    public void OperatorCannotManageModels()
    {
        var viewModel = Create(new FakeModelService(), "OPERATOR");

        Assert.False(viewModel.CanManageModels);
        Assert.False(viewModel.TrainModelCommand.CanExecute(null));
    }

    [Fact]
    public async Task TrainCommand_ForAdminCallsServiceWithSelectedInputs()
    {
        var service = new FakeModelService { TrainResult = TrainingModel(3) };
        var viewModel = Create(service, "ADMIN");

        await viewModel.LoadModelsAsync();
        viewModel.SelectedModelFamily = "tank";
        viewModel.SelectedSourceType = "SIMULATION";
        await viewModel.TrainModelCommand.ExecuteAsync(null);

        Assert.Equal(1, service.TrainCalls);
        Assert.Equal("tank", service.LastTrainRequest?.ModelFamily);
        Assert.Equal(["SIMULATION"], service.LastTrainRequest?.SourceTypes);
        Assert.Contains("v0003", viewModel.SuccessMessage);
    }

    [Fact]
    public async Task TrainSuccess_RefreshesModelsAndSelectsNewVersion()
    {
        var trained = TrainingModel(3);
        var service = new FakeModelService
        {
            Models = [Model(1, active: true)],
            TrainResult = trained,
            ModelsAfterMutation = [Model(1, active: true), trained],
        };
        var viewModel = Create(service, "ADMIN");

        await viewModel.LoadModelsAsync();
        await viewModel.TrainModelCommand.ExecuteAsync(null);

        Assert.Equal(2, service.GetCalls);
        Assert.Equal(3, viewModel.SelectedModel?.Id);
        Assert.Equal(2, viewModel.Models.Count);
    }

    [Fact]
    public async Task TrainCommand_WhileBusyDoesNotStartSecondTraining()
    {
        var completion = new TaskCompletionSource<TrainAnomalyModelResponseDto>();
        var service = new FakeModelService { TrainTask = completion.Task };
        var viewModel = Create(service, "ADMIN");
        await viewModel.LoadModelsAsync();

        var first = viewModel.TrainModelCommand.ExecuteAsync(null);
        await Task.Yield();

        Assert.True(viewModel.IsTraining);
        Assert.False(viewModel.TrainModelCommand.CanExecute(null));
        Assert.Equal(1, service.TrainCalls);
        completion.SetResult(TrainingModel(4));
        await first;
    }

    [Fact]
    public async Task ActivateInactiveModel_CallsServiceAndRefreshesList()
    {
        var inactive = Model(2, active: false);
        var service = new FakeModelService
        {
            Models = [Model(1, active: true), inactive],
            ActivateResult = Model(2, active: true),
            ModelsAfterMutation = [Model(1, active: false), Model(2, active: true)],
        };
        var viewModel = Create(service, "ADMIN");
        await viewModel.LoadModelsAsync();
        var item = viewModel.Models.Single(model => model.Id == 2);

        await viewModel.ActivateModelCommand.ExecuteAsync(item);

        Assert.Equal(1, service.ActivateCalls);
        Assert.Equal(2, service.LastActivatedId);
        Assert.Equal(2, viewModel.ActiveModel?.Id);
        Assert.Equal(2, viewModel.SelectedModel?.Id);
    }

    [Fact]
    public async Task ActiveModel_CannotBeActivatedAgain()
    {
        var service = new FakeModelService { Models = [Model(1, active: true)] };
        var viewModel = Create(service, "ADMIN");
        await viewModel.LoadModelsAsync();

        Assert.False(viewModel.ActivateModelCommand.CanExecute(viewModel.Models[0]));
        Assert.Equal(0, service.ActivateCalls);
    }

    [Fact]
    public async Task OperatorCannotActivateInactiveModel()
    {
        var service = new FakeModelService { Models = [Model(2, active: false)] };
        var viewModel = Create(service, "OPERATOR");
        await viewModel.LoadModelsAsync();

        Assert.False(viewModel.ActivateModelCommand.CanExecute(viewModel.Models[0]));
        Assert.Equal(0, service.ActivateCalls);
    }

    [Fact]
    public async Task SelectedModel_UpdatesDetailProperties()
    {
        var service = new FakeModelService { Models = [Model(1, active: true), Model(2, active: false)] };
        var viewModel = Create(service, "ADMIN");
        await viewModel.LoadModelsAsync();

        viewModel.SelectedModel = viewModel.Models.Single(model => model.Id == 2);

        Assert.Contains("v0002", viewModel.SelectedModelTitle);
        Assert.Equal("pump", viewModel.SelectedModel.ModelFamily);
        Assert.Equal("READY", viewModel.SelectedModel.ArtifactStatusText);
    }

    [Fact]
    public async Task ActiveSummaryUsesOnlyBackendActiveFlag()
    {
        var service = new FakeModelService { Models = [Model(5, active: false), Model(6, active: true)] };
        var viewModel = Create(service, "ADMIN");

        await viewModel.LoadModelsAsync();

        Assert.Equal("v0006", viewModel.ActiveModel?.Version);
        Assert.Equal("ACTIVE", viewModel.ActiveModel?.StatusText);
    }

    [Fact]
    public async Task ModelSummaryShowsRealRangeAndSafeUnvalidatedDiagnostics()
    {
        var viewModel = Create(new FakeModelService { Models = [Model(2, active: true)] }, "ADMIN");

        await viewModel.LoadModelsAsync();

        Assert.Equal("14.05.2026 – 12.08.2026", viewModel.SelectedModel?.TrainingRangeText);
        Assert.Equal("Henüz doğrulanmadı", viewModel.SelectedModel?.NormalFalsePositiveText);
        Assert.Equal("Henüz doğrulanmadı", viewModel.SelectedModel?.ScenarioDetectionText);
        Assert.Equal("Henüz doğrulanmadı", viewModel.SelectedModel?.ValidationStatusText);
        Assert.Contains("belirlenemiyor", viewModel.RecommendationText);
    }

    [Fact]
    public async Task ActiveModelReportsNewSensorRowsWithoutAutomaticRetraining()
    {
        var service = new FakeModelService { Models = [Model(1, active: false), Model(2, active: true)] };
        var viewModel = Create(service, "ADMIN");

        await viewModel.LoadModelsAsync();

        Assert.Equal("v0002", viewModel.ActiveModel?.Version);
        Assert.True(viewModel.ActiveModel?.HasNewSensorData);
        Assert.Contains("14.230", viewModel.ActiveModel?.NewSensorDataText);
        Assert.Equal(0, service.TrainCalls);
        Assert.Equal(0, service.ActivateCalls);
    }

    [Fact]
    public void IsolationForestSummaryDoesNotExposeRegressionMetrics()
    {
        var names = typeof(ModelVersionItemViewModel).GetProperties()
            .Select(property => property.Name)
            .ToArray();

        Assert.DoesNotContain(names, name => name.Contains("Accuracy", StringComparison.OrdinalIgnoreCase));
        Assert.DoesNotContain(names, name => name.Contains("Mae", StringComparison.OrdinalIgnoreCase));
        Assert.DoesNotContain(names, name => name.Contains("Rmse", StringComparison.OrdinalIgnoreCase));
        Assert.DoesNotContain(names, name => name.Contains("Mape", StringComparison.OrdinalIgnoreCase));
    }

    private static ModelManagementViewModel Create(FakeModelService service, string role)
    {
        var auth = new AuthState();
        auth.SetCurrentUser(new CurrentUserResponseDto
        {
            Id = 1,
            Username = role.ToLowerInvariant(),
            FullName = role,
            Role = role,
            IsActive = true,
        });
        return new ModelManagementViewModel(service, new FakeStationService(), auth);
    }

    private static ModelVersionDto Model(int id, bool active) => new()
    {
        Id = id,
        ModelType = "isolation_forest",
        ModelFamily = "pump",
        Version = $"v{id:0000}",
        TrainedAt = new DateTimeOffset(2026, 8, 12, 9, id, 0, TimeSpan.Zero),
        TrainingStartDate = new DateOnly(2026, 5, 14),
        TrainingEndDate = new DateOnly(2026, 8, 12),
        TrainingRowCount = 42 + id,
        FeatureCount = 20,
        FeatureNames = ["flow_rate", "pressure"],
        IsActive = active,
        ArtifactAvailable = true,
        ArtifactFileName = $"isolation_forest_pump_v{id:0000}.joblib",
        ArtifactSizeBytes = 1_000_000,
        ArtifactSchemaVersion = 1,
        TrainingOutlierFraction = 0.03,
        LatestSensorReadingAt = new DateTimeOffset(2026, 8, 19, 9, 0, 0, TimeSpan.Zero),
        NewSensorRowsSinceTraining = 14230,
    };

    private static TrainAnomalyModelResponseDto TrainingModel(int id) => new()
    {
        Id = id,
        ModelType = "isolation_forest",
        ModelFamily = "pump",
        Version = $"v{id:0000}",
        TrainedAt = new DateTimeOffset(2026, 8, 12, 10, id, 0, TimeSpan.Zero),
        TrainingStartDate = new DateOnly(2026, 5, 14),
        TrainingEndDate = new DateOnly(2026, 8, 12),
        TrainingRowCount = 50,
        FeatureCount = 20,
        FeatureNames = ["flow_rate", "pressure"],
        IsActive = false,
        ArtifactAvailable = true,
        ArtifactFileName = $"isolation_forest_pump_v{id:0000}.joblib",
        ArtifactSizeBytes = 1_100_000,
        ArtifactSchemaVersion = 1,
        TrainingOutlierFraction = 0.03,
        LatestSensorReadingAt = new DateTimeOffset(2026, 8, 19, 9, 0, 0, TimeSpan.Zero),
        NewSensorRowsSinceTraining = 14230,
    };

    private sealed class FakeModelService : IModelService
    {
        public IReadOnlyList<ModelVersionDto> Models { get; init; } = [];
        public IReadOnlyList<ModelVersionDto>? ModelsAfterMutation { get; init; }
        public Exception? GetException { get; init; }
        public Task<IReadOnlyList<ModelVersionDto>>? GetTask { get; init; }
        public TrainAnomalyModelResponseDto TrainResult { get; init; } = TrainingModel(2);
        public Task<TrainAnomalyModelResponseDto>? TrainTask { get; init; }
        public ModelVersionDto ActivateResult { get; init; } = Model(2, active: true);
        public int GetCalls { get; private set; }
        public int TrainCalls { get; private set; }
        public int ActivateCalls { get; private set; }
        public int? LastActivatedId { get; private set; }
        public TrainAnomalyModelRequestDto? LastTrainRequest { get; private set; }

        public Task<IReadOnlyList<ModelVersionDto>> GetModelsAsync(CancellationToken cancellationToken = default)
        {
            GetCalls++;
            if (GetException is not null) return Task.FromException<IReadOnlyList<ModelVersionDto>>(GetException);
            if (GetTask is not null) return GetTask;
            return Task.FromResult(GetCalls > 1 && ModelsAfterMutation is not null ? ModelsAfterMutation : Models);
        }

        public Task<TrainAnomalyModelResponseDto> TrainAnomalyModelAsync(
            TrainAnomalyModelRequestDto request,
            CancellationToken cancellationToken = default)
        {
            TrainCalls++;
            LastTrainRequest = request;
            return TrainTask ?? Task.FromResult(TrainResult);
        }

        public Task<ModelVersionDto> ActivateModelAsync(int modelId, CancellationToken cancellationToken = default)
        {
            ActivateCalls++;
            LastActivatedId = modelId;
            return Task.FromResult(ActivateResult);
        }
    }

    private sealed class FakeStationService : IStationService
    {
        public Task<IReadOnlyList<StationDto>> GetActiveStationsAsync(CancellationToken cancellationToken = default) =>
            Task.FromResult<IReadOnlyList<StationDto>>(
                [new StationDto
                {
                    Id = 7,
                    Code = "IST-7",
                    Name = "Test İstasyonu",
                    City = "İstanbul",
                    District = "Test",
                    Address = "Test",
                    IsActive = true,
                    CreatedAt = DateTimeOffset.UtcNow,
                }]);
    }
}
