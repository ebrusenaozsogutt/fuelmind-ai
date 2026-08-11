using System.Windows;
using FuelMind.Desktop.ViewModels;

namespace FuelMind.Desktop.Views;

public partial class MainWindow : Window
{
    public MainWindow(MainViewModel viewModel)
    {
        InitializeComponent();
        DataContext = viewModel;
    }
}
