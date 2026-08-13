using System.Collections.ObjectModel;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Models;
using FuelMind.Desktop.Dtos.Stations;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;

namespace FuelMind.Desktop.ViewModels;

public sealed partial class ModelManagementViewModel : ObservableObject
{
    private readonly IModelService _modelService;
    private readonly IStationService _stationService;
    private readonly AuthState _authState;

    public ModelManagementViewModel(
        IModelService modelService,
        IStationService stationService,
        AuthState authState)
    {
        _modelService = modelService;
        _stationService = stationService;
        _authState = authState;
    }

    public ObservableCollection<ModelVersionItemViewModel> Models { get; } = [];
    public ObservableCollection<StationDto> Stations { get; } = [];
    public IReadOnlyList<string> ModelFamilies { get; } = ["pump", "tank"];
    public IReadOnlyList<string> SourceTypes { get; } =
        ["Tümü", "SIMULATION", "CSV_IMPORT", "REAL_DEVICE", "MANUAL"];

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(SelectedModelTitle))]
    private ModelVersionItemViewModel? _selectedModel;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(IsBusy))]
    [NotifyCanExecuteChangedFor(nameof(LoadModelsCommand))]
    [NotifyCanExecuteChangedFor(nameof(RefreshCommand))]
    [NotifyCanExecuteChangedFor(nameof(TrainModelCommand))]
    [NotifyCanExecuteChangedFor(nameof(ActivateModelCommand))]
    private bool _isLoading;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(IsBusy))]
    [NotifyCanExecuteChangedFor(nameof(LoadModelsCommand))]
    [NotifyCanExecuteChangedFor(nameof(RefreshCommand))]
    [NotifyCanExecuteChangedFor(nameof(TrainModelCommand))]
    [NotifyCanExecuteChangedFor(nameof(ActivateModelCommand))]
    private bool _isTraining;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(IsBusy))]
    [NotifyCanExecuteChangedFor(nameof(LoadModelsCommand))]
    [NotifyCanExecuteChangedFor(nameof(RefreshCommand))]
    [NotifyCanExecuteChangedFor(nameof(TrainModelCommand))]
    [NotifyCanExecuteChangedFor(nameof(ActivateModelCommand))]
    private bool _isActivating;

    [ObservableProperty, NotifyPropertyChangedFor(nameof(HasError))]
    private string? _errorMessage;
    [ObservableProperty, NotifyPropertyChangedFor(nameof(HasSuccess))]
    private string? _successMessage;
    [ObservableProperty] private DateTimeOffset? _lastRefreshAt;
    [ObservableProperty, NotifyCanExecuteChangedFor(nameof(TrainModelCommand))]
    private StationDto? _selectedStation;
    [ObservableProperty, NotifyCanExecuteChangedFor(nameof(TrainModelCommand))]
    private string _selectedModelFamily = "pump";
    [ObservableProperty, NotifyCanExecuteChangedFor(nameof(TrainModelCommand))]
    private DateTime? _trainingStartDate;
    [ObservableProperty, NotifyCanExecuteChangedFor(nameof(TrainModelCommand))]
    private DateTime? _trainingEndDate;
    [ObservableProperty] private string _selectedSourceType = "Tümü";

    public bool IsBusy => IsLoading || IsTraining || IsActivating;
    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);
    public bool HasSuccess => !string.IsNullOrWhiteSpace(SuccessMessage);
    public bool IsEmpty => Models.Count == 0;
    public bool CanManageModels => string.Equals(
        _authState.CurrentUser?.Role, "ADMIN", StringComparison.OrdinalIgnoreCase);
    public string CurrentUserRole => _authState.CurrentUser?.Role ?? "UNKNOWN";
    public ModelVersionItemViewModel? ActiveModel => Models.FirstOrDefault(model => model.IsActive);
    public bool HasActiveModel => ActiveModel is not null;
    public bool HasMultipleModels => Models.Count > 1;
    public ModelVersionItemViewModel? RecommendedModel => Models
        .Where(model =>
            model.ArtifactAvailable
            && string.Equals(model.Model.ValidationStatus, "PASS", StringComparison.OrdinalIgnoreCase)
            && model.NormalFalsePositiveRate is not null
            && model.ScenarioDetectionCount is not null
            && model.ScenarioTotalCount is > 0)
        .OrderBy(model => model.NormalFalsePositiveRate)
        .ThenByDescending(model =>
            (double)model.ScenarioDetectionCount!.Value / model.ScenarioTotalCount!.Value)
        .FirstOrDefault();
    public bool HasRecommendedModel => RecommendedModel is not null;
    public string RecommendationText => RecommendedModel is null
        ? "Önerilen model henüz belirlenemiyor. Normal veri yanlış uyarı ve senaryo doğrulama sonuçları gerekli."
        : $"{RecommendedModel.Version}, doğrulanmış modeller arasında daha düşük normal veri yanlış uyarı oranı ve daha yüksek senaryo yakalama oranına göre öneriliyor.";
    public string LastRefreshText => LastRefreshAt is null
        ? "Henüz yenilenmedi"
        : $"Son yenileme: {LastRefreshAt.Value.ToLocalTime():dd.MM.yyyy HH:mm:ss}";
    public string SelectedModelTitle => SelectedModel is null
        ? "Model seçin"
        : $"{SelectedModel.ModelDisplayName} · {SelectedModel.Version}";

    public Task LoadModelsAsync(CancellationToken cancellationToken = default) =>
        LoadAsync(cancellationToken);

    [RelayCommand(CanExecute = nameof(CanLoad))]
    private Task LoadModels(CancellationToken cancellationToken) =>
        LoadAsync(cancellationToken);

    [RelayCommand(CanExecute = nameof(CanLoad))]
    private Task RefreshAsync(CancellationToken cancellationToken) =>
        LoadAsync(cancellationToken);

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        if (IsBusy) return;
        NotifyAuthorizationChanged();
        ErrorMessage = null;
        SuccessMessage = null;
        IsLoading = true;
        try
        {
            await LoadModelsCoreAsync(cancellationToken);
            if (Stations.Count == 0)
            {
                var stations = await _stationService.GetActiveStationsAsync(cancellationToken);
                ReplaceStations(stations);
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested) { }
        catch (Exception exception)
        {
            ErrorMessage = UserMessage(
                exception,
                "Model bilgileri alınamadı. Backend bağlantısını kontrol edin.");
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand(CanExecute = nameof(CanTrain))]
    private async Task TrainModelAsync(CancellationToken cancellationToken)
    {
        if (!CanTrain()) return;
        ErrorMessage = null;
        SuccessMessage = null;
        IsTraining = true;
        try
        {
            var response = await _modelService.TrainAnomalyModelAsync(
                new TrainAnomalyModelRequestDto
                {
                    StationId = SelectedStation!.Id,
                    ModelFamily = SelectedModelFamily,
                    StartTime = ToOffset(TrainingStartDate),
                    EndTime = ToOffset(TrainingEndDate),
                    SourceTypes = SelectedSourceType == "Tümü" ? null : [SelectedSourceType],
                },
                cancellationToken);
            SuccessMessage = $"Model başarıyla eğitildi. Sürüm: {response.Version}";
            await LoadModelsCoreAsync(cancellationToken);
            SelectedModel = Models.FirstOrDefault(model => model.Id == response.Id);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested) { }
        catch (Exception exception)
        {
            ErrorMessage = UserMessage(exception, "Model eğitilemedi.");
        }
        finally
        {
            IsTraining = false;
        }
    }

    [RelayCommand(CanExecute = nameof(CanActivateModel))]
    private async Task ActivateModelAsync(
        ModelVersionItemViewModel? model,
        CancellationToken cancellationToken)
    {
        if (!CanActivateModel(model)) return;
        ErrorMessage = null;
        SuccessMessage = null;
        IsActivating = true;
        try
        {
            var activated = await _modelService.ActivateModelAsync(model!.Id, cancellationToken);
            SuccessMessage = $"{activated.Version} sürümü aktif model olarak seçildi.";
            await LoadModelsCoreAsync(cancellationToken);
            SelectedModel = Models.FirstOrDefault(item => item.Id == activated.Id);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested) { }
        catch (Exception exception)
        {
            ErrorMessage = UserMessage(exception, "Model aktive edilemedi.");
        }
        finally
        {
            IsActivating = false;
        }
    }

    private async Task LoadModelsCoreAsync(CancellationToken cancellationToken)
    {
        var loaded = await _modelService.GetModelsAsync(cancellationToken);
        var selectedId = SelectedModel?.Id;
        Models.Clear();
        foreach (var model in loaded.OrderByDescending(model => model.TrainedAt))
        {
            Models.Add(new ModelVersionItemViewModel(model));
        }
        SelectedModel = Models.FirstOrDefault(model => model.Id == selectedId)
            ?? ActiveModel
            ?? Models.FirstOrDefault();
        LastRefreshAt = DateTimeOffset.Now;
        NotifyModelSummaryChanged();
    }

    private void ReplaceStations(IReadOnlyList<StationDto> stations)
    {
        Stations.Clear();
        foreach (var station in stations.Where(station => station.IsActive))
        {
            Stations.Add(station);
        }
        SelectedStation ??= Stations.FirstOrDefault();
    }

    private void NotifyModelSummaryChanged()
    {
        OnPropertyChanged(nameof(IsEmpty));
        OnPropertyChanged(nameof(ActiveModel));
        OnPropertyChanged(nameof(HasActiveModel));
        OnPropertyChanged(nameof(HasMultipleModels));
        OnPropertyChanged(nameof(RecommendedModel));
        OnPropertyChanged(nameof(HasRecommendedModel));
        OnPropertyChanged(nameof(RecommendationText));
        OnPropertyChanged(nameof(LastRefreshText));
    }

    private void NotifyAuthorizationChanged()
    {
        OnPropertyChanged(nameof(CanManageModels));
        OnPropertyChanged(nameof(CurrentUserRole));
        TrainModelCommand.NotifyCanExecuteChanged();
        ActivateModelCommand.NotifyCanExecuteChanged();
    }

    private bool CanLoad() => !IsBusy;
    private bool CanTrain() =>
        CanManageModels && !IsBusy && SelectedStation is not null
        && !string.IsNullOrWhiteSpace(SelectedModelFamily)
        && (TrainingStartDate is null || TrainingEndDate is null
            || TrainingStartDate <= TrainingEndDate);
    private bool CanActivateModel(ModelVersionItemViewModel? model) =>
        CanManageModels && !IsBusy && model?.CanActivate == true;

    private static DateTimeOffset? ToOffset(DateTime? value) =>
        value is null ? null : new DateTimeOffset(DateTime.SpecifyKind(value.Value, DateTimeKind.Local));

    private static string UserMessage(Exception exception, string fallback) => exception switch
    {
        ApiException { StatusCode: HttpStatusCode.Unauthorized } =>
            "Oturum süresi doldu. Lütfen tekrar giriş yapın.",
        ApiException { StatusCode: HttpStatusCode.Forbidden } =>
            "Bu işlem için ADMIN yetkisi gerekiyor.",
        ApiException apiException when !string.IsNullOrWhiteSpace(apiException.Message) =>
            apiException.Message,
        HttpRequestException => "Backend sunucusuna ulaşılamadı. Bağlantıyı kontrol edin.",
        TaskCanceledException => "Model işlemi zaman aşımına uğradı.",
        JsonException => "Backend geçersiz bir model yanıtı döndürdü.",
        _ => fallback,
    };
}
