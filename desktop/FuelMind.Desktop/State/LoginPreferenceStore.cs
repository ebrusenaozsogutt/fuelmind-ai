using System.IO;
using System.Text.Json;

namespace FuelMind.Desktop.State;

public sealed class LoginPreferenceStore
{
    private static readonly string PreferencesPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "FuelMind AI",
        "login-preferences.json");

    public LoginPreferences Load()
    {
        try
        {
            if (!File.Exists(PreferencesPath)) return new LoginPreferences(false, string.Empty);
            return JsonSerializer.Deserialize<LoginPreferences>(File.ReadAllText(PreferencesPath))
                ?? new LoginPreferences(false, string.Empty);
        }
        catch (Exception)
        {
            return new LoginPreferences(false, string.Empty);
        }
    }

    public void Save(string username)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(PreferencesPath)!);
        File.WriteAllText(PreferencesPath, JsonSerializer.Serialize(new LoginPreferences(true, username)));
    }

    public void Clear()
    {
        if (File.Exists(PreferencesPath)) File.Delete(PreferencesPath);
    }
}

public sealed record LoginPreferences(bool RememberMe, string Username);
