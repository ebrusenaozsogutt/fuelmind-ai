using FuelMind.Desktop.Dtos.Models;

namespace FuelMind.Desktop.ViewModels;

public sealed class ModelVersionItemViewModel
{
    public ModelVersionItemViewModel(ModelVersionDto model) => Model = model;

    public ModelVersionDto Model { get; }
    public int Id => Model.Id;
    public string ModelType => Model.ModelType;
    public string ModelFamily => Model.ModelFamily;
    public string Version => Model.Version;
    public DateTimeOffset TrainedAt => Model.TrainedAt;
    public DateOnly TrainingStartDate => Model.TrainingStartDate;
    public DateOnly TrainingEndDate => Model.TrainingEndDate;
    public int TrainingRowCount => Model.TrainingRowCount;
    public int? FeatureCount => Model.FeatureCount;
    public string FeatureCountText => FeatureCount?.ToString("N0") ?? "—";
    public IReadOnlyList<string> FeatureNames => Model.FeatureNames;
    public bool IsActive => Model.IsActive;
    public bool ArtifactAvailable => Model.ArtifactAvailable;
    public int? ArtifactSchemaVersion => Model.ArtifactSchemaVersion;
    public long ArtifactSizeBytes => Model.ArtifactSizeBytes;
    public double? TrainingOutlierFraction => Model.TrainingOutlierFraction;
    public double? NormalFalsePositiveRate => Model.NormalFalsePositiveRate;
    public int? ScenarioDetectionCount => Model.ScenarioDetectionCount;
    public int? ScenarioTotalCount => Model.ScenarioTotalCount;
    public DateTimeOffset? LatestSensorReadingAt => Model.LatestSensorReadingAt;
    public long NewSensorRowsSinceTraining => Model.NewSensorRowsSinceTraining;

    public string StatusText => IsActive ? "ACTIVE" : "INACTIVE";
    public string ArtifactStatusText => ArtifactAvailable ? "READY" : "MISSING";
    public bool CanActivate => !IsActive && ArtifactAvailable;
    public string ModelDisplayName => ModelType.Replace('_', ' ').ToUpperInvariant();
    public string ModelFriendlyName => ModelType.Equals("isolation_forest", StringComparison.OrdinalIgnoreCase)
        ? "Isolation Forest"
        : ModelType.Replace('_', ' ');
    public string TargetText => ModelFamily.Equals("pump", StringComparison.OrdinalIgnoreCase)
        ? "Pompa anomalileri"
        : ModelFamily.Equals("tank", StringComparison.OrdinalIgnoreCase)
            ? "Tank anomalileri"
            : ModelFamily;
    public string TrainedAtText => TrainedAt.ToLocalTime().ToString("dd.MM.yyyy HH:mm");
    public string TrainingRangeText => $"{TrainingStartDate:dd.MM.yyyy} – {TrainingEndDate:dd.MM.yyyy}";
    public string TrainingRowsText => $"{TrainingRowCount:N0} temiz sensör kaydı";
    public string FeaturesSummaryText => FeatureCount is int count
        ? $"{count:N0} davranışsal özellik"
        : "—";
    public string TrainingOutlierText => TrainingOutlierFraction is double rate
        ? $"%{rate * 100:N2}"
        : "Henüz doğrulanmadı";
    public string NormalFalsePositiveText => NormalFalsePositiveRate is double rate
        ? $"%{rate * 100:N2}"
        : "Henüz doğrulanmadı";
    public string ScenarioDetectionText =>
        ScenarioDetectionCount is int detected && ScenarioTotalCount is int total
            ? $"{detected:N0} / {total:N0} senaryo"
            : "Henüz doğrulanmadı";
    public string ValidationStatusText => string.IsNullOrWhiteSpace(Model.ValidationStatus)
        ? "Henüz doğrulanmadı"
        : Model.ValidationStatus;
    public string LatestSensorReadingText => LatestSensorReadingAt is DateTimeOffset latest
        ? latest.ToLocalTime().ToString("dd.MM.yyyy HH:mm")
        : "Veri bulunamadı";
    public bool HasNewSensorData => NewSensorRowsSinceTraining > 0;
    public string NewSensorDataText => HasNewSensorData
        ? $"{NewSensorRowsSinceTraining:N0} yeni sensör kaydı mevcut. Model yeniden eğitilebilir."
        : "Eğitim döneminden sonra yeni sensör kaydı bulunmuyor.";
    public string ArtifactSchemaText => ArtifactSchemaVersion?.ToString() ?? "—";
}
