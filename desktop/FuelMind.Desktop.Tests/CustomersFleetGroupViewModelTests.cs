using System.Reflection;
using FuelMind.Desktop.Dtos.Auth;
using FuelMind.Desktop.Dtos.Commercial;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using FuelMind.Desktop.ViewModels;
using Xunit;

namespace FuelMind.Desktop.Tests;

public sealed class CustomersFleetGroupViewModelTests
{
    [Fact]
    public async Task FleetSelectionShowsOnlyItsGroupsAndNewGroupUsesSelectedFleet()
    {
        var (viewModel, service) = await CreateAsync();
        var konyaFleet = viewModel.Fleets.Single(item => item.Id == 11);
        var ankaraFleet = viewModel.Fleets.Single(item => item.Id == 12);

        Assert.Equal(2, konyaFleet.GroupCount);
        Assert.Equal(1, ankaraFleet.GroupCount);

        viewModel.SelectedFleet = konyaFleet;
        Assert.All(viewModel.FleetGroups, item => Assert.Equal(konyaFleet.Id, item.FleetId));

        viewModel.SelectedFleetGroup = viewModel.FleetGroups.First();
        viewModel.SelectedFleet = ankaraFleet;

        Assert.Null(viewModel.SelectedFleetGroup);
        Assert.Single(viewModel.FleetGroups);
        Assert.All(viewModel.FleetGroups, item => Assert.Equal(ankaraFleet.Id, item.FleetId));

        viewModel.NewGroupCode = "ANK-YENI";
        viewModel.NewGroupName = "Yeni Ankara Grubu";
        await viewModel.CreateFleetGroupCommand.ExecuteAsync(null);

        Assert.Equal(ankaraFleet.Id, service.LastCreatedGroup?.FleetId);
    }

    [Fact]
    public async Task CustomerChangeRemovesStaleFleetSelectionAndFleetToggleRefreshes()
    {
        var (viewModel, service) = await CreateAsync();
        var oldFleet = viewModel.SelectedFleet!;

        await viewModel.ToggleFleetActiveCommand.ExecuteAsync(null);

        Assert.False(service.Fleets.Single(item => item.Id == oldFleet.Id).IsActive);
        Assert.Equal(oldFleet.Id, viewModel.SelectedFleet?.Id);

        await viewModel.ToggleFleetActiveCommand.ExecuteAsync(null);

        Assert.True(service.Fleets.Single(item => item.Id == oldFleet.Id).IsActive);

        viewModel.SelectedCustomer = viewModel.Customers.Single(item => item.Id == 2);

        Assert.NotEqual(oldFleet.Id, viewModel.SelectedFleet?.Id);
        Assert.Equal(2, viewModel.SelectedFleet?.CustomerId);
        Assert.All(viewModel.FleetGroups, item => Assert.Equal(viewModel.SelectedFleet!.Id, item.FleetId));
    }

    private static async Task<(CustomersViewModel ViewModel, CommercialServiceProxy Service)> CreateAsync()
    {
        var service = DispatchProxy.Create<ICommercialService, CommercialServiceProxy>();
        var proxy = (CommercialServiceProxy)(object)service;
        var auth = new AuthState();
        auth.SetCurrentUser(new CurrentUserResponseDto { Id = 1, Username = "admin", FullName = "Development Admin", Role = "ADMIN", IsActive = true });
        var viewModel = new CustomersViewModel(service, auth);
        await viewModel.LoadAsync();
        return (viewModel, proxy);
    }

    private class CommercialServiceProxy : DispatchProxy
    {
        public List<CustomerReadDto> Customers { get; } =
        [
            new() { Id = 1, Code = "KONYA", Name = "Konya Lojistik", CustomerType = "COMPANY", RequestStatus = "APPROVED", IsActive = true },
            new() { Id = 2, Code = "ANKARA", Name = "Ankara Lojistik", CustomerType = "COMPANY", RequestStatus = "APPROVED", IsActive = true },
        ];

        public List<FleetReadDto> Fleets { get; } =
        [
            new() { Id = 11, CustomerId = 1, Code = "KONYA", Name = "Konya Filosu", IsActive = true },
            new() { Id = 12, CustomerId = 1, Code = "ANKARA", Name = "Ankara Filosu", IsActive = true },
            new() { Id = 21, CustomerId = 2, Code = "IZMIR", Name = "İzmir Filosu", IsActive = true },
        ];

        public List<FleetGroupReadDto> Groups { get; } =
        [
            new() { Id = 101, FleetId = 11, Code = "KON-A", Name = "Ağır Vasıta", IsActive = true },
            new() { Id = 102, FleetId = 11, Code = "KON-H", Name = "Hafif Ticari", IsActive = true },
            new() { Id = 103, FleetId = 12, Code = "ANK-A", Name = "Ankara Grup", IsActive = true },
            new() { Id = 104, FleetId = 21, Code = "IZM-A", Name = "İzmir Grup", IsActive = true },
        ];

        public FleetGroupSaveDto? LastCreatedGroup { get; private set; }

        protected override object? Invoke(MethodInfo? targetMethod, object?[]? args)
        {
            return targetMethod!.Name switch
            {
                nameof(ICommercialService.GetCustomersAsync) => Task.FromResult<IReadOnlyList<CustomerReadDto>>(Customers),
                nameof(ICommercialService.GetDriversAsync) => Task.FromResult<IReadOnlyList<DriverReadDto>>([]),
                nameof(ICommercialService.GetAuthorizedPersonsAsync) => Task.FromResult<IReadOnlyList<CustomerAuthorizedPersonReadDto>>([]),
                nameof(ICommercialService.GetFleetsAsync) => Task.FromResult<IReadOnlyList<FleetReadDto>>(Fleets.Where(item => args?[0] is not int customerId || item.CustomerId == customerId).ToList()),
                nameof(ICommercialService.GetFleetGroupsAsync) => Task.FromResult<IReadOnlyList<FleetGroupReadDto>>(Groups.Where(item => args?[0] is not int fleetId || item.FleetId == fleetId).ToList()),
                nameof(ICommercialService.GetVehiclesAsync) => Task.FromResult<IReadOnlyList<VehicleReadDto>>([]),
                nameof(ICommercialService.GetAssignmentsAsync) => Task.FromResult<IReadOnlyList<DriverVehicleAssignmentReadDto>>([]),
                nameof(ICommercialService.CreateFleetGroupAsync) => CreateGroup((FleetGroupSaveDto)args![0]!),
                nameof(ICommercialService.UpdateFleetAsync) => UpdateFleet((int)args![0]!, (FleetSaveDto)args[1]!),
                _ => throw new NotSupportedException(targetMethod.Name),
            };
        }

        private Task<FleetGroupReadDto> CreateGroup(FleetGroupSaveDto request)
        {
            LastCreatedGroup = request;
            var group = new FleetGroupReadDto { Id = Groups.Max(item => item.Id) + 1, FleetId = request.FleetId!.Value, Code = request.Code!, Name = request.Name!, Description = request.Description, IsActive = request.IsActive ?? true };
            Groups.Add(group);
            return Task.FromResult(group);
        }

        private Task<FleetReadDto> UpdateFleet(int id, FleetSaveDto request)
        {
            var existing = Fleets.Single(item => item.Id == id);
            var updated = new FleetReadDto { Id = id, CustomerId = request.CustomerId ?? existing.CustomerId, Code = request.Code ?? existing.Code, Name = request.Name ?? existing.Name, Description = request.Description, RequestStatus = request.RequestStatus ?? existing.RequestStatus, IsActive = request.IsActive ?? existing.IsActive };
            Fleets[Fleets.IndexOf(existing)] = updated;
            return Task.FromResult(updated);
        }
    }
}
