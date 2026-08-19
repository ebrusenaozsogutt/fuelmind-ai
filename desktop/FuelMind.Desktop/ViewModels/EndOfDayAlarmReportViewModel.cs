using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Alarms;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.ViewModels;

/// <summary>Shows every alarm state for a selected calendar day, including closed records.</summary>
public sealed partial class EndOfDayAlarmReportViewModel(IAlarmService alarmService) : ObservableObject
{
    public ObservableCollection<AlarmDto> Alarms { get; } = [];

    [ObservableProperty] private DateTime _reportDate = DateTime.Today;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;

    public bool IsEmpty => !IsLoading && Alarms.Count == 0 && string.IsNullOrEmpty(ErrorMessage);

    [RelayCommand]
    public async Task LoadAsync()
    {
        if (IsLoading) return;
        IsLoading = true;
        ErrorMessage = null;
        try
        {
            var alarms = await alarmService.GetAllAsync(includeFalsePositives: true);
            var date = DateOnly.FromDateTime(ReportDate);
            Replace(Alarms, alarms
                .Where(alarm => DateOnly.FromDateTime(alarm.DetectedAt.LocalDateTime) == date)
                .OrderByDescending(alarm => alarm.DetectedAt));
            OnPropertyChanged(nameof(IsEmpty));
        }
        catch (Exception ex)
        {
            ErrorMessage = ex is ApiException api ? api.Message : ex.Message;
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsEmpty));
        }
    }

    private static void Replace<T>(ObservableCollection<T> target, IEnumerable<T> source)
    {
        target.Clear();
        foreach (var item in source) target.Add(item);
    }
}
