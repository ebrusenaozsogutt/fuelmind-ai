using System.Windows;
using System.Windows.Controls;
using FuelMind.Desktop.Dtos.Live;

namespace FuelMind.Desktop.Controls;

public partial class AiAnalysisControl : UserControl
{
    public static readonly DependencyProperty ResultProperty = DependencyProperty.Register(
        nameof(Result), typeof(LiveAnomalyResultDto), typeof(AiAnalysisControl));

    public AiAnalysisControl() => InitializeComponent();

    public LiveAnomalyResultDto? Result
    {
        get => (LiveAnomalyResultDto?)GetValue(ResultProperty);
        set => SetValue(ResultProperty, value);
    }
}
