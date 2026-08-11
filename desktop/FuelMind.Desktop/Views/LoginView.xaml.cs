using System.Windows;
using System.Windows.Controls;
using FuelMind.Desktop.ViewModels;

namespace FuelMind.Desktop.Views;

public partial class LoginView : UserControl
{
    private bool _synchronizingPassword;
    private string _currentPassword = string.Empty;

    public LoginView()
    {
        InitializeComponent();
    }

    private void OnLoginClick(object sender, RoutedEventArgs e)
    {
        if (DataContext is LoginViewModel viewModel && viewModel.LoginCommand.CanExecute(_currentPassword))
        {
            viewModel.LoginCommand.Execute(_currentPassword);
        }
    }

    private void OnPasswordVisibilityChanged(object sender, RoutedEventArgs e)
    {
        var isVisible = sender is CheckBox { IsChecked: true };
        _synchronizingPassword = true;
        try
        {
            PasswordInput.Visibility = isVisible ? Visibility.Collapsed : Visibility.Visible;
            VisiblePasswordInput.Visibility = isVisible ? Visibility.Visible : Visibility.Collapsed;
            PasswordInput.Password = _currentPassword;
            VisiblePasswordInput.Text = _currentPassword;
        }
        finally
        {
            _synchronizingPassword = false;
        }
    }

    private void OnPasswordChanged(object sender, RoutedEventArgs e)
    {
        if (_synchronizingPassword) return;
        _currentPassword = PasswordInput.Password;
        _synchronizingPassword = true;
        try { VisiblePasswordInput.Text = _currentPassword; }
        finally { _synchronizingPassword = false; }
    }

    private void OnVisiblePasswordChanged(object sender, TextChangedEventArgs e)
    {
        if (_synchronizingPassword) return;
        _currentPassword = VisiblePasswordInput.Text;
        _synchronizingPassword = true;
        try { PasswordInput.Password = _currentPassword; }
        finally { _synchronizingPassword = false; }
    }
}
