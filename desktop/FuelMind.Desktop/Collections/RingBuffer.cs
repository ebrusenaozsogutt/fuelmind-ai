namespace FuelMind.Desktop.Collections;
public sealed class RingBuffer<T>
{
    private readonly Queue<T> _items = []; private readonly object _sync = new();
    public RingBuffer(int capacity) { if (capacity <= 0) throw new ArgumentOutOfRangeException(nameof(capacity)); Capacity = capacity; }
    public int Capacity { get; } public int Count { get { lock (_sync) return _items.Count; } }
    public void Add(T item) { lock (_sync) { if (_items.Count == Capacity) _items.Dequeue(); _items.Enqueue(item); } }
    public void Clear() { lock (_sync) _items.Clear(); }
    public IReadOnlyList<T> Snapshot() { lock (_sync) return _items.ToArray(); }
}
