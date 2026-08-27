using FuelMind.Desktop.Services;
using FuelMind.Desktop.ViewModels;
using System.Windows.Markup;

namespace FuelMind.Desktop.Views;

public partial class OrdersView
{
    public OrdersView()
    {
        RuntimeDiagnostics.Trace("OrdersView constructor");
        InitializeComponent();
        Language = XmlLanguage.GetLanguage("tr-TR");
        DataContextChanged += (_, _) => RuntimeDiagnostics.Trace($"OrdersView DataContext={DataContext?.GetType().Name ?? "<null>"}");
        Loaded += (_, _) => RuntimeDiagnostics.Trace(
            $"OrdersView Loaded; DataContext={DataContext?.GetType().Name ?? "<null>"}; " +
            $"Visibility={Visibility}; IsVisible={IsVisible}; Size={ActualWidth:F0}x{ActualHeight:F0}; " +
            $"Tanks={(DataContext as OrdersViewModel)?.Tanks.Count ?? 0}; HasOrder={(DataContext as OrdersViewModel)?.HasOrder}");
        Loaded += (_, _) => (DataContext as OrdersViewModel)?.TraceState("View Loaded");
    }
}
