using System.Collections.Specialized;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using FuelMind.Desktop.ViewModels;

namespace FuelMind.Desktop.Views;

public partial class ReportsView : UserControl
{
    private ReportsViewModel? _viewModel;

    public ReportsView()
    {
        InitializeComponent();
        DataContextChanged += OnDataContextChanged;
    }

    private void OnDataContextChanged(object sender, DependencyPropertyChangedEventArgs eventArgs)
    {
        if (_viewModel is not null) _viewModel.Columns.CollectionChanged -= OnColumnsChanged;
        _viewModel = eventArgs.NewValue as ReportsViewModel;
        if (_viewModel is not null) _viewModel.Columns.CollectionChanged += OnColumnsChanged;
        ConfigureColumns();
    }

    private void OnColumnsChanged(object? sender, NotifyCollectionChangedEventArgs eventArgs) => ConfigureColumns();

    private void ConfigureColumns()
    {
        ReportGrid.Columns.Clear();
        if (_viewModel is null) return;
        foreach (var column in _viewModel.Columns)
        {
            ReportGrid.Columns.Add(new DataGridTextColumn
            {
                Header = column.Header,
                Binding = new Binding($"[{column.Key}]"),
                Width = new DataGridLength(column.Width, DataGridLengthUnitType.Star),
                MinWidth = 84,
            });
        }
    }
}
