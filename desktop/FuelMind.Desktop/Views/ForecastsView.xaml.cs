using FuelMind.Desktop.Services;
using FuelMind.Desktop.ViewModels;

namespace FuelMind.Desktop.Views;

public partial class ForecastsView
{
    public ForecastsView()
    {
        RuntimeDiagnostics.Trace("ForecastsView constructor");
        InitializeComponent();
        DataContextChanged += (_, _) => RuntimeDiagnostics.Trace($"ForecastsView DataContext={DataContext?.GetType().Name ?? "<null>"}");
        Loaded += (_, _) => RuntimeDiagnostics.Trace(
            $"ForecastsView Loaded; DataContext={DataContext?.GetType().Name ?? "<null>"}; " +
            $"Visibility={Root.Visibility}; IsVisible={Root.IsVisible}; Size={Root.ActualWidth:F0}x{Root.ActualHeight:F0}; " +
            $"Forecasts={(DataContext as ForecastsViewModel)?.Forecasts.Count ?? 0}");
        Loaded += (_, _) => (DataContext as ForecastsViewModel)?.TraceState("View Loaded");
    }
}
