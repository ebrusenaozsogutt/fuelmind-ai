using System.Text;
using System.IO;

namespace FuelMind.Desktop.Services;

/// <summary>Development-only durable diagnostics for faults that can terminate the WPF process.</summary>
public static class RuntimeDiagnostics
{
    private static readonly object Sync = new();
    public static string LogPath { get; } = Path.Combine(AppContext.BaseDirectory, "logs", "runtime-crash.log");

    public static void Trace(string message)
    {
        Write("TRACE", message, null);
    }

    public static void Exception(string source, Exception exception)
    {
        Write(source, exception.Message, exception);
    }

    private static void Write(string source, string message, Exception? exception)
    {
        try
        {
            var builder = new StringBuilder()
                .Append('[').Append(DateTimeOffset.Now.ToString("O")).Append("] ")
                .Append(source).Append(": ").AppendLine(message);
            if (exception is not null)
            {
                builder.AppendLine($"Exception type: {exception.GetType().FullName}");
                builder.AppendLine($"Inner exception: {exception.InnerException?.ToString() ?? "<none>"}");
                builder.AppendLine($"Stack trace: {exception.StackTrace ?? "<none>"}");
            }
            builder.AppendLine();
            lock (Sync)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(LogPath)!);
                File.AppendAllText(LogPath, builder.ToString(), Encoding.UTF8);
            }
        }
        catch
        {
            // Diagnostics must never alter the original exception's termination behaviour.
        }
    }
}
