using System.Windows;
using System.Windows.Controls;
using FuelMind.Desktop.Services;

namespace FuelMind.Desktop.Views;

public partial class CustomersView : UserControl
{
    public CustomersView()
    {
        RuntimeDiagnostics.Trace("CustomersView constructor");
        InitializeComponent();
        RuntimeDiagnostics.Trace("CustomersView InitializeComponent completed");
        Loaded += OnLoaded;
    }

    private static void OnLoaded(object sender, RoutedEventArgs e) =>
        RuntimeDiagnostics.Trace("CustomersView Loaded event");
}
