namespace FuelMind.Desktop.Configuration;

public sealed class ApiSettings
{
    public const string SectionName = "Api";

    public string BaseUrl { get; init; } = string.Empty;

    public string WebSocketBaseUrl { get; init; } = string.Empty;
}

public sealed class LiveChartsSettings
{
    public const string SectionName = "LiveCharts";

    public int MaxPoints { get; init; }

    public int RefreshMilliseconds { get; init; }
}

public sealed class ConnectionSettings
{
    public const string SectionName = "Connection";

    public int ReconnectSeconds { get; init; }
}
