using System.Windows;
using System.Windows.Controls;
using FuelMind.Desktop.Dtos.Alarms;

namespace FuelMind.Desktop.Controls;

public partial class AlarmAiAnalysisControl : UserControl
{
    public static readonly DependencyProperty AlarmProperty = DependencyProperty.Register(
        nameof(Alarm),
        typeof(AlarmDto),
        typeof(AlarmAiAnalysisControl));

    public AlarmAiAnalysisControl() => InitializeComponent();

    public AlarmDto? Alarm
    {
        get => (AlarmDto?)GetValue(AlarmProperty);
        set => SetValue(AlarmProperty, value);
    }
}
