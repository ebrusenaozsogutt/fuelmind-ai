namespace FuelMind.Desktop.Collections;

/// <summary>
/// A single measured value from a live simulation tick. The timestamp is always
/// supplied by the simulation; this model does not generate synthetic time.
/// </summary>
public sealed record LiveChartPoint(DateTimeOffset Timestamp, double Value)
{
    public double ChartTimestamp => Timestamp.LocalDateTime.ToOADate();
    public double ChartValue => Value;
}
