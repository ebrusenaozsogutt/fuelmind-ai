using FuelMind.Desktop.Services;
using System.IO;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class RuntimeDiagnosticsTests
{
    [Fact]
    public void Exception_writes_a_durable_crash_record_with_exception_details()
    {
        var exception = new InvalidOperationException("outer failure", new ArgumentException("inner failure"));

        RuntimeDiagnostics.Exception("RuntimeDiagnosticsTests", exception);

        var log = File.ReadAllText(RuntimeDiagnostics.LogPath);
        Assert.Contains("RuntimeDiagnosticsTests", log);
        Assert.Contains("System.InvalidOperationException", log);
        Assert.Contains("outer failure", log);
        Assert.Contains("inner failure", log);
        Assert.Contains("Stack trace:", log);
    }
}
