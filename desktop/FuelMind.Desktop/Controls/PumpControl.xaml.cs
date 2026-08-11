using System.Windows;
using System.Windows.Controls;
using FuelMind.Desktop.Dtos.Live;

namespace FuelMind.Desktop.Controls;

/// <summary>
/// A reusable display of one live pump snapshot. It has no dependency on application state.
/// </summary>
public partial class PumpControl : UserControl
{
    public static readonly DependencyProperty PumpProperty = DependencyProperty.Register(
        nameof(Pump),
        typeof(PumpLiveDataDto),
        typeof(PumpControl),
        new PropertyMetadata(null));

    public PumpControl()
    {
        InitializeComponent();
    }

    public PumpLiveDataDto? Pump
    {
        get => (PumpLiveDataDto?)GetValue(PumpProperty);
        set => SetValue(PumpProperty, value);
    }
}
