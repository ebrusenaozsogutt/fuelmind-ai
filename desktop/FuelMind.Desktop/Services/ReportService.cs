using System.Text.Json;
using FuelMind.Desktop.Dtos.Reports;

namespace FuelMind.Desktop.Services;

public interface IReportService
{
    Task<IReadOnlyList<ReportRowDto>> GetAsync(string reportType, string query, CancellationToken cancellationToken = default);
    Task<byte[]> ExportAsync(string reportType, string format, string query, CancellationToken cancellationToken = default);
}

public sealed class ReportService(ApiClient apiClient) : IReportService
{
    public async Task<IReadOnlyList<ReportRowDto>> GetAsync(string reportType, string query, CancellationToken ct = default)
    {
        var json = await apiClient.GetAsync<JsonElement>($"reports/{reportType}{query}", ct);
        if (json.ValueKind == JsonValueKind.Array) return json.EnumerateArray().Select(ReportRowDto.From).ToList();
        return [ReportRowDto.From(json)];
    }
    public Task<byte[]> ExportAsync(string reportType, string format, string query, CancellationToken ct = default) =>
        apiClient.DownloadAsync($"reports/{reportType}/export/{format}{query}", ct);
}
