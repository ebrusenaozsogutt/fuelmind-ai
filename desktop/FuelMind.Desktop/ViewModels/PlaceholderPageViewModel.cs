namespace FuelMind.Desktop.ViewModels;

public sealed class PlaceholderPageViewModel(string title)
{
    public string Title { get; } = title;
    public string Message => "Bu modül sonraki aşamada bağlanacaktır.";
}
