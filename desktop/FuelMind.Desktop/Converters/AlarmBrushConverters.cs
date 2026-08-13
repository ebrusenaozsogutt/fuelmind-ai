using System.Globalization;
using System.Windows.Data;
using System.Windows.Media;
using System.Windows;

namespace FuelMind.Desktop.Converters;

public sealed class AlarmSeverityToBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture) =>
        Application.Current.Resources[$"AlarmSeverity{value}Brush"] as Brush
        ?? Application.Current.Resources["AlarmSeverityDefaultBrush"] as Brush
        ?? Brushes.SlateGray;

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
        throw new NotSupportedException();
}

public sealed class AlarmStatusToBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture) =>
        Application.Current.Resources[$"AlarmStatus{value}Brush"] as Brush
        ?? Application.Current.Resources["AlarmStatusDefaultBrush"] as Brush
        ?? Brushes.SlateGray;

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
        throw new NotSupportedException();
}

public sealed class AiRiskLevelToBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture) =>
        Application.Current.Resources[$"AiRisk{value}Brush"] as Brush
        ?? Application.Current.Resources["AiRiskDefaultBrush"] as Brush
        ?? Brushes.SlateGray;

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
        throw new NotSupportedException();
}
