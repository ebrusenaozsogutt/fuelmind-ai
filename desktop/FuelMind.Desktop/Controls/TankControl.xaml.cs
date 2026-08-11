using System.Windows;
using System.Windows.Controls;
using FuelMind.Desktop.Dtos.Live;

namespace FuelMind.Desktop.Controls;

/// <summary>
/// A reusable display of one live tank snapshot. It has no dependency on application state.
/// </summary>
public partial class TankControl : UserControl
{
    public static readonly DependencyProperty TankProperty = DependencyProperty.Register(
        nameof(Tank),
        typeof(TankLiveDataDto),
        typeof(TankControl),
        new PropertyMetadata(null, OnTankChanged));

    public static readonly DependencyProperty FillPercentageProperty = DependencyProperty.Register(
        nameof(FillPercentage),
        typeof(double?),
        typeof(TankControl),
        new PropertyMetadata(null));

    public static readonly DependencyProperty FillPercentageTextProperty = DependencyProperty.Register(
        nameof(FillPercentageText),
        typeof(string),
        typeof(TankControl),
        new PropertyMetadata("--"));

    public TankControl()
    {
        InitializeComponent();
    }

    public TankLiveDataDto? Tank
    {
        get => (TankLiveDataDto?)GetValue(TankProperty);
        set => SetValue(TankProperty, value);
    }

    public double? FillPercentage
    {
        get => (double?)GetValue(FillPercentageProperty);
        private set => SetValue(FillPercentageProperty, value);
    }

    public string FillPercentageText
    {
        get => (string)GetValue(FillPercentageTextProperty);
        private set => SetValue(FillPercentageTextProperty, value);
    }

    private static void OnTankChanged(DependencyObject dependencyObject, DependencyPropertyChangedEventArgs eventArgs)
    {
        var control = (TankControl)dependencyObject;
        control.FillPercentage = CalculateFillPercentage((TankLiveDataDto?)eventArgs.NewValue);
        control.FillPercentageText = control.FillPercentage is double percentage
            ? $"{percentage:N0}% dolu"
            : "--";
    }

    private static double? CalculateFillPercentage(TankLiveDataDto? tank) =>
        tank is { CapacityLiters: > 0 }
            ? Math.Clamp((double)(tank.MeasuredLevelLiters / tank.CapacityLiters * 100m), 0d, 100d)
            : null;
}
