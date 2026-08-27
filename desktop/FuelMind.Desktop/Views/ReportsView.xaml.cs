using System.Collections.Specialized;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using FuelMind.Desktop.Dtos.Reports;
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
                Width = new DataGridLength(column.Width, column.UsePixelWidth ? DataGridLengthUnitType.Pixel : DataGridLengthUnitType.Star),
                MinWidth = column.MinWidth,
                MaxWidth = column.MaxWidth ?? double.PositiveInfinity,
                HeaderStyle = (Style)FindResource("ReportColumnHeaderStyle"),
                ElementStyle = CreateCellTextStyle(column),
            });
        }
    }

    private static Style CreateCellTextStyle(ReportColumnDefinition column)
    {
        var style = new Style(typeof(TextBlock));
        style.Setters.Add(new Setter(TextBlock.TextTrimmingProperty, TextTrimming.CharacterEllipsis));
        style.Setters.Add(new Setter(TextBlock.TextWrappingProperty, TextWrapping.NoWrap));
        style.Setters.Add(new Setter(FrameworkElement.ToolTipProperty, new Binding($"[{column.Key}]")));
        style.Setters.Add(new Setter(TextBlock.TextAlignmentProperty, column.IsNumeric ? TextAlignment.Right : TextAlignment.Left));
        style.Setters.Add(new Setter(FrameworkElement.HorizontalAlignmentProperty, HorizontalAlignment.Stretch));
        style.Setters.Add(new Setter(FrameworkElement.VerticalAlignmentProperty, VerticalAlignment.Center));
        return style;
    }
}
