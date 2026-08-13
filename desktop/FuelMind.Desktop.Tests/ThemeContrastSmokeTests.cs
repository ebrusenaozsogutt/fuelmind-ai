using System.Runtime.ExceptionServices;
using System.Threading;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Media;
using FuelMind.Desktop.Controls;
using FuelMind.Desktop.Dtos.Alarms;
using FuelMind.Desktop.Views;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class ThemeContrastSmokeTests
{
    [Fact]
    public void DarkTheme_TargetViewsLoadAndCriticalColorPairsRemainReadable()
    {
        ExceptionDispatchInfo? failure = null;
        var uiThread = new Thread(() =>
        {
            try
            {
                var app = new App();
                app.InitializeComponent();

                AssertStyleExists(app.Resources, "DarkComboBoxStyle");
                AssertStyleExists(app.Resources, "DarkTextBoxStyle");
                AssertStyleExists(app.Resources, "DarkPasswordBoxStyle");
                AssertStyleExists(app.Resources, "DarkDatePickerStyle");
                AssertStyleExists(app.Resources, "DarkDatePickerTextBoxStyle");
                AssertStyleExists(app.Resources, "DarkCalendarButtonStyle");
                AssertStyleExists(app.Resources, "DarkDataGridStyle");
                AssertStyleExists(app.Resources, "DarkDataGridRowStyle");
                AssertStyleExists(app.Resources, "DarkDataGridCellStyle");
                AssertStyleExists(app.Resources, "DarkDataGridColumnHeaderStyle");

                AssertContrast(app.Resources, "AppForegroundBrush", "CardBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "ControlBackgroundBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "TableHeaderBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "RowHoverBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "RowSelectedBrush", 4.5);
                AssertContrast(app.Resources, "DisabledForegroundBrush", "ControlBackgroundBrush", 4.5);
                AssertContrast(app.Resources, "MutedForegroundBrush", "CardBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "SuccessBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "DangerBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "InactiveBrush", 4.5);
                AssertContrast(app.Resources, "SuccessForegroundBrush", "CardBrush", 4.5);
                AssertContrast(app.Resources, "WarningForegroundBrush", "CardBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "AiRiskNORMALBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "AiRiskWATCHBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "AiRiskMEDIUMBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "AiRiskHIGHBrush", 4.5);
                AssertContrast(app.Resources, "AppForegroundBrush", "AiRiskCRITICALBrush", 4.5);

                var alarmAiPanel = new AlarmAiAnalysisControl
                {
                    Alarm = new AlarmDto
                    {
                        Id = 17,
                        StationId = 2,
                        PumpId = 3,
                        AnomalyScore = 96.62m,
                        RiskLevel = "CRITICAL",
                        DecisionSource = "HYBRID",
                        AnomalyType = "EQUIPMENT_ANOMALY",
                        ModelVersion = "v0002",
                        Findings = [new AlarmFindingDto
                        {
                            FeatureName = "motor_current",
                            DisplayName = "Motor akımı",
                            CurrentValue = 14.8m,
                            ReferenceValue = 10.6m,
                            PercentDifference = 39m,
                            Direction = "HIGH",
                        }],
                        ProbableCauses = [new AlarmCauseDto { Description = "Filter blockage" }],
                        RecommendedChecks = ["Check the pump filter."],
                    },
                };
                var datePicker = new DatePicker
                {
                    SelectedDate = new DateTime(2026, 8, 12),
                    Style = (Style)app.Resources["DarkDatePickerStyle"],
                };
                var disabledButton = new Button
                {
                    Content = "Aktif",
                    IsEnabled = false,
                    Style = (Style)app.Resources["DarkButtonStyle"],
                };
                FrameworkElement[] targetViews =
                [
                    new ModelManagementView(),
                    new LoginView(),
                    new LiveMonitoringView(),
                    new AlarmsView(),
                    new TanksView(),
                    new PumpsView(),
                    new TankDetailView(),
                    new PumpDetailView(),
                    new TankControl(),
                    new PumpControl(),
                    new AiAnalysisControl(),
                    alarmAiPanel,
                    datePicker,
                    disabledButton,
                ];

                foreach (var view in targetViews)
                {
                    view.Measure(new Size(1100, 700));
                    view.Arrange(new Rect(0, 0, 1100, 700));
                    view.UpdateLayout();
                    Assert.True(view.IsMeasureValid, $"{view.GetType().Name} could not be measured.");
                }

                var renderedTexts = FindVisualChildren<TextBlock>(alarmAiPanel)
                    .Select(item => item.Text)
                    .ToArray();
                Assert.Contains("97 / 100", renderedTexts);
                Assert.Contains("Kritik", renderedTexts);
                Assert.Contains(renderedTexts, text => text.Contains("Kural ve yapay zekâ"));
                Assert.Contains("v0002", renderedTexts);
                Assert.Contains("Ekipman anomalisi", renderedTexts);
                Assert.Contains(renderedTexts, text => text.Contains("Motor akımı"));
                Assert.Contains(renderedTexts, text => text.Contains("Filtre tıkanıklığı"));
                Assert.Contains(renderedTexts, text => text.Contains("Pompa filtresini"));

                datePicker.ApplyTemplate();
                datePicker.UpdateLayout();
                var dateTextBox = Assert.Single(FindVisualChildren<DatePickerTextBox>(datePicker));
                Assert.Equal(
                    ((SolidColorBrush)app.Resources["ControlBackgroundBrush"]).Color,
                    ((SolidColorBrush)dateTextBox.Background).Color);
                Assert.Equal(
                    ((SolidColorBrush)app.Resources["DisabledForegroundBrush"]).Color,
                    ((SolidColorBrush)disabledButton.Foreground).Color);
            }
            catch (Exception exception)
            {
                failure = ExceptionDispatchInfo.Capture(exception);
            }
        });

        uiThread.SetApartmentState(ApartmentState.STA);
        uiThread.Start();

        Assert.True(uiThread.Join(TimeSpan.FromSeconds(30)), "Theme smoke test timed out.");
        failure?.Throw();
    }

    private static void AssertStyleExists(ResourceDictionary resources, string key) =>
        Assert.IsType<Style>(resources[key]);

    private static void AssertContrast(
        ResourceDictionary resources,
        string foregroundKey,
        string backgroundKey,
        double minimumRatio)
    {
        var foreground = Assert.IsType<SolidColorBrush>(resources[foregroundKey]);
        var background = Assert.IsType<SolidColorBrush>(resources[backgroundKey]);
        var ratio = ContrastRatio(foreground.Color, background.Color);

        Assert.True(
            ratio >= minimumRatio,
            $"{foregroundKey} / {backgroundKey} contrast was {ratio:F2}:1; expected at least {minimumRatio:F1}:1.");
    }

    private static double ContrastRatio(Color first, Color second)
    {
        var firstLuminance = RelativeLuminance(first);
        var secondLuminance = RelativeLuminance(second);
        var lighter = Math.Max(firstLuminance, secondLuminance);
        var darker = Math.Min(firstLuminance, secondLuminance);
        return (lighter + 0.05) / (darker + 0.05);
    }

    private static double RelativeLuminance(Color color) =>
        (0.2126 * Linearize(color.R)) +
        (0.7152 * Linearize(color.G)) +
        (0.0722 * Linearize(color.B));

    private static double Linearize(byte component)
    {
        var channel = component / 255d;
        return channel <= 0.04045
            ? channel / 12.92
            : Math.Pow((channel + 0.055) / 1.055, 2.4);
    }

    private static IEnumerable<T> FindVisualChildren<T>(DependencyObject parent)
        where T : DependencyObject
    {
        for (var index = 0; index < VisualTreeHelper.GetChildrenCount(parent); index++)
        {
            var child = VisualTreeHelper.GetChild(parent, index);
            if (child is T match)
            {
                yield return match;
            }

            foreach (var descendant in FindVisualChildren<T>(child))
            {
                yield return descendant;
            }
        }
    }
}
