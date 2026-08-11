using FuelMind.Desktop.Collections;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class RingBufferTests
{
    [Fact]
    public void Add_WhenCapacityIsExceeded_KeepsTheMostRecentPointsAndCanBeCleared()
    {
        var buffer = new RingBuffer<int>(3);

        buffer.Add(1);
        buffer.Add(2);
        buffer.Add(3);
        buffer.Add(4);

        Assert.Equal([2, 3, 4], buffer.Snapshot());

        buffer.Clear();

        Assert.Empty(buffer.Snapshot());
        Assert.Equal(0, buffer.Count);
    }
}
