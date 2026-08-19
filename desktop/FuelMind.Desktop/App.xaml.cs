using System.Windows;
using System.Windows.Threading;
using FuelMind.Desktop.ViewModels;
using FuelMind.Desktop.Views;
using FuelMind.Desktop.State;
using FuelMind.Desktop.Configuration;
using FuelMind.Desktop.Services;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace FuelMind.Desktop;

public partial class App : Application
{
    private ServiceProvider? _serviceProvider;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        var services = new ServiceCollection();
        ConfigureServices(services);
        _serviceProvider = services.BuildServiceProvider();
        _ = _serviceProvider.GetRequiredService<IOptions<ApiSettings>>().Value;
        _ = _serviceProvider.GetRequiredService<IOptions<LiveChartsSettings>>().Value;
        _ = _serviceProvider.GetRequiredService<IOptions<ConnectionSettings>>().Value;
        _ = _serviceProvider.GetRequiredService<LiveDataStore>();

        var mainWindow = _serviceProvider.GetRequiredService<MainWindow>();
        MainWindow = mainWindow;
        mainWindow.Show();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _serviceProvider?.GetService<LiveWebSocketService>()?.Dispose();
        _serviceProvider?.Dispose();
        base.OnExit(e);
    }

    private static void ConfigureServices(IServiceCollection services)
    {
        IConfiguration configuration = new ConfigurationBuilder()
            .SetBasePath(AppContext.BaseDirectory)
            .AddJsonFile("appsettings.json", optional: true, reloadOnChange: false)
            .Build();

        services.AddSingleton(configuration);
        services.AddOptions<ApiSettings>()
            .Bind(configuration.GetRequiredSection(ApiSettings.SectionName))
            .Validate(settings => Uri.TryCreate(settings.BaseUrl, UriKind.Absolute, out _),
                "Api:BaseUrl must be an absolute URI.")
            .Validate(settings => Uri.TryCreate(settings.WebSocketBaseUrl, UriKind.Absolute, out var uri)
                && (uri.Scheme == Uri.UriSchemeWs || uri.Scheme == Uri.UriSchemeWss),
                "Api:WebSocketBaseUrl must be an absolute ws or wss URI.")
            .ValidateOnStart();
        services.AddOptions<LiveChartsSettings>()
            .Bind(configuration.GetRequiredSection(LiveChartsSettings.SectionName))
            .Validate(settings => settings.MaxPoints > 0, "LiveCharts:MaxPoints must be greater than zero.")
            .Validate(settings => settings.RefreshMilliseconds > 0,
                "LiveCharts:RefreshMilliseconds must be greater than zero.")
            .ValidateOnStart();
        services.AddOptions<ConnectionSettings>()
            .Bind(configuration.GetRequiredSection(ConnectionSettings.SectionName))
            .Validate(settings => settings.ReconnectSeconds > 0,
                "Connection:ReconnectSeconds must be greater than zero.")
            .ValidateOnStart();

        services.AddSingleton(new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            PropertyNamingPolicy = null,
            NumberHandling = JsonNumberHandling.AllowReadingFromString,
        });
        services.AddSingleton<LiveMessageParser>();
        services.AddSingleton<DetailNavigationService>();
        services.AddSingleton<LiveChartDataService>(_ => new LiveChartDataService(Current.Dispatcher,
            _.GetRequiredService<IOptions<LiveChartsSettings>>()));
        services.AddSingleton<LiveDataStore>(_ => new LiveDataStore(Current.Dispatcher,
            _.GetRequiredService<LiveChartDataService>()));
        services.AddSingleton<LiveWebSocketService>();
        services.AddLogging(builder => builder.AddDebug());
        services.AddSingleton<AuthState>();
        services.AddTransient<AuthenticationHandler>();
        services.AddHttpClient<ApiClient>((serviceProvider, client) =>
        {
            var apiSettings = serviceProvider.GetRequiredService<IOptions<ApiSettings>>().Value;
            client.BaseAddress = new Uri(apiSettings.BaseUrl.TrimEnd('/') + "/", UriKind.Absolute);
            client.DefaultRequestHeaders.Accept.Add(
                new MediaTypeWithQualityHeaderValue("application/json"));
        }).AddHttpMessageHandler<AuthenticationHandler>();

        services.AddSingleton<LoginPreferenceStore>();
        services.AddSingleton<AuthService>();
        services.AddSingleton<AlarmService>();
        services.AddSingleton<IAlarmService>(provider => provider.GetRequiredService<AlarmService>());
        services.AddSingleton<ModelService>();
        services.AddSingleton<IModelService>(provider => provider.GetRequiredService<ModelService>());
        services.AddSingleton<StationService>();
        services.AddSingleton<IStationService>(provider => provider.GetRequiredService<StationService>());
        services.AddSingleton<CommercialService>();
        services.AddSingleton<ICommercialService>(provider => provider.GetRequiredService<CommercialService>());
        services.AddSingleton<IReportService, ReportService>();
        services.AddSingleton<IOperationsService, OperationsService>();
        services.AddSingleton<IFaultService, FaultService>();
        services.AddSingleton<LoginViewModel>();
        services.AddSingleton<LiveMonitoringViewModel>();
        services.AddSingleton<FieldTopologyViewModel>();
        services.AddSingleton<TanksViewModel>();
        services.AddSingleton<PumpsViewModel>();
        services.AddSingleton<DashboardViewModel>();
        services.AddSingleton<SimulatorViewModel>();
        services.AddSingleton<AlarmsViewModel>();
        services.AddSingleton<EndOfDayAlarmReportViewModel>();
        services.AddSingleton<ModelManagementViewModel>();
        services.AddSingleton<TankDetailViewModel>();
        services.AddSingleton<PumpDetailViewModel>();
        services.AddSingleton<CustomersViewModel>();
        services.AddSingleton<FuelCardsViewModel>();
        services.AddSingleton<FuelPricesViewModel>();
        services.AddSingleton<SalesHistoryViewModel>();
        services.AddSingleton<ReportsViewModel>();
        services.AddSingleton<FaultsViewModel>();
        services.AddSingleton<AttendantsViewModel>();
        services.AddSingleton<MainViewModel>();
        services.AddSingleton<MainWindow>();
        services.AddTransient<ModelManagementView>();
    }
}
