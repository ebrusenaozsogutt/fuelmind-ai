using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Dtos.Commercial;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;

namespace FuelMind.Desktop.ViewModels;

/// <summary>Hierarchical commercial master-data editor. Children load only on selection, not per grid row.</summary>
public sealed partial class CustomersViewModel(ICommercialService commercialService, AuthState authState) : ObservableObject
{
    public ObservableCollection<CustomerReadDto> Customers { get; } = [];
    public ObservableCollection<CustomerAuthorizedPersonReadDto> AuthorizedPersons { get; } = [];
    public ObservableCollection<FleetReadDto> Fleets { get; } = [];
    public ObservableCollection<FleetGroupReadDto> FleetGroups { get; } = [];
    public ObservableCollection<VehicleReadDto> Vehicles { get; } = [];
    public ObservableCollection<DriverReadDto> Drivers { get; } = [];
    public ObservableCollection<DriverVehicleAssignmentReadDto> Assignments { get; } = [];

    [ObservableProperty] private CustomerReadDto? _selectedCustomer;
    [ObservableProperty, NotifyPropertyChangedFor(nameof(CanCreateFleetGroup))] private FleetReadDto? _selectedFleet;
    [ObservableProperty, NotifyPropertyChangedFor(nameof(CanCreateVehicle))] private FleetGroupReadDto? _selectedFleetGroup;
    [ObservableProperty] private VehicleReadDto? _selectedVehicle;
    [ObservableProperty] private DriverReadDto? _selectedDriver;
    [ObservableProperty] private string _newCode = string.Empty;
    [ObservableProperty] private string _newName = string.Empty;
    [ObservableProperty] private string _newCustomerType = "COMPANY";
    [ObservableProperty] private string _newCustomerSector = string.Empty;
    [ObservableProperty] private decimal _newCustomerDiscountRate;
    [ObservableProperty] private string _newCustomerRequestStatus = "PENDING";
    [ObservableProperty] private string _newCustomerPhone = string.Empty;
    [ObservableProperty] private string _newCustomerEmail = string.Empty;
    [ObservableProperty] private string _newCustomerTaxNumber = string.Empty;
    [ObservableProperty] private string _newCustomerTaxOffice = string.Empty;
    [ObservableProperty] private bool _isEditingCustomer;
    [ObservableProperty] private string _newFleetCode = string.Empty;
    [ObservableProperty] private string _newFleetName = string.Empty;
    [ObservableProperty] private string _newFleetDescription = string.Empty;
    [ObservableProperty, NotifyPropertyChangedFor(nameof(FleetFormTitle))] private bool _isEditingFleet;
    [ObservableProperty] private bool _isFleetFormOpen;
    [ObservableProperty] private string _newGroupCode = string.Empty;
    [ObservableProperty] private string _newGroupName = string.Empty;
    [ObservableProperty] private string _newGroupDescription = string.Empty;
    [ObservableProperty, NotifyPropertyChangedFor(nameof(FleetGroupFormTitle))] private bool _isEditingFleetGroup;
    [ObservableProperty] private bool _isFleetGroupFormOpen;
    [ObservableProperty] private string _newPlate = string.Empty;
    [ObservableProperty] private string _newVehicleBrand = string.Empty;
    [ObservableProperty] private string _newVehicleModel = string.Empty;
    [ObservableProperty] private string _newVehicleType = string.Empty;
    [ObservableProperty] private string _newVehicleDescription = string.Empty;
    [ObservableProperty] private bool _isEditingVehicle;
    [ObservableProperty] private string _newDriverName = string.Empty;
    [ObservableProperty] private string _newDriverPhone = string.Empty;
    [ObservableProperty] private string _newDriverReferenceCode = string.Empty;
    [ObservableProperty] private string _newDriverLicenseNumber = string.Empty;
    [ObservableProperty] private bool _isEditingDriver;
    [ObservableProperty] private string _newAuthorizedPersonName = string.Empty;
    [ObservableProperty] private string _newAuthorizedPersonTitle = string.Empty;
    [ObservableProperty] private string _newAuthorizedPersonPhone = string.Empty;
    [ObservableProperty] private string _newAuthorizedPersonEmail = string.Empty;
    [ObservableProperty] private bool _newAuthorizedPersonIsPrimary;
    [ObservableProperty] private bool _isEditingAuthorizedPerson;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private string? _errorMessage;
    public bool IsAdmin => string.Equals(authState.CurrentUser?.Role, "ADMIN", StringComparison.OrdinalIgnoreCase);
    public bool IsEmpty => !IsLoading && Customers.Count == 0 && string.IsNullOrEmpty(ErrorMessage);
    public IReadOnlyList<string> CustomerTypes { get; } = ["COMPANY", "INDIVIDUAL"];
    public IReadOnlyList<string> RequestStatuses { get; } = ["PENDING", "APPROVED", "REJECTED", "SUSPENDED"];
    public bool CanCreateFleetGroup => IsAdmin && SelectedFleet is not null;
    public bool CanCreateVehicle => IsAdmin && SelectedFleetGroup is not null;
    public bool CanAssignDriver => IsAdmin && SelectedVehicle is not null && SelectedDriver is not null;
    public string FleetFormTitle => IsEditingFleet ? "Filoyu Düzenle" : "Yeni Filo";
    public string FleetGroupFormTitle => IsEditingFleetGroup ? "Grubu Düzenle" : "Yeni Grup";

    partial void OnSelectedCustomerChanged(CustomerReadDto? value) => _ = LoadCustomerChildrenAsync(value);
    partial void OnSelectedFleetChanged(FleetReadDto? value)
    {
        SelectedFleetGroup = null;
        ResetFleetGroupForm();
        _ = LoadFleetGroupsAsync(value);
    }
    partial void OnSelectedFleetGroupChanged(FleetGroupReadDto? value) { _ = LoadVehiclesAsync(value); }
    partial void OnSelectedVehicleChanged(VehicleReadDto? value) { OnPropertyChanged(nameof(CanAssignDriver)); _ = LoadAssignmentsAsync(value); }
    partial void OnSelectedDriverChanged(DriverReadDto? value) { OnPropertyChanged(nameof(CanAssignDriver)); _ = LoadAssignmentsForDriverAsync(value); }

    [RelayCommand] public async Task LoadAsync() => await ExecuteAsync(async () =>
    {
        Replace(Customers, await commercialService.GetCustomersAsync());
        Replace(Drivers, await commercialService.GetDriversAsync());
        SelectedCustomer ??= Customers.FirstOrDefault();
        OnPropertyChanged(nameof(IsEmpty));
    });

    [RelayCommand] public async Task CreateCustomerAsync()
    {
        if (!ValidateCustomer()) return;
        await ExecuteAsync(async () =>
        {
            var request = CustomerRequest();
            var saved = IsEditingCustomer && SelectedCustomer is not null
                ? await commercialService.UpdateCustomerAsync(SelectedCustomer.Id, request)
                : await commercialService.CreateCustomerAsync(request);
            ReplaceOrAdd(Customers, saved); SelectedCustomer = saved; ResetCustomerForm();
        });
    }

    [RelayCommand] private void NewCustomer() => ResetCustomerForm();
    [RelayCommand] private void EditCustomer()
    {
        if (SelectedCustomer is null) { ErrorMessage = "Düzenlemek için müşteri seçin."; return; }
        IsEditingCustomer = true; NewCode = SelectedCustomer.Code; NewName = SelectedCustomer.Name;
        NewCustomerType = SelectedCustomer.CustomerType; NewCustomerSector = SelectedCustomer.Sector ?? string.Empty;
        NewCustomerDiscountRate = SelectedCustomer.DiscountRate; NewCustomerRequestStatus = SelectedCustomer.RequestStatus;
        NewCustomerPhone = SelectedCustomer.Phone ?? string.Empty; NewCustomerEmail = SelectedCustomer.Email ?? string.Empty;
        NewCustomerTaxNumber = SelectedCustomer.TaxNumber ?? string.Empty; NewCustomerTaxOffice = SelectedCustomer.TaxOffice ?? string.Empty;
    }

    [RelayCommand] public async Task DeactivateCustomerAsync()
    {
        if (SelectedCustomer is null) return;
        await ExecuteAsync(async () => { await commercialService.DeactivateCustomerAsync(SelectedCustomer.Id); await LoadAsync(); });
    }

    [RelayCommand] public async Task CreateAuthorizedPersonAsync()
    {
        if (SelectedCustomer is null || !ValidateEmail(NewAuthorizedPersonEmail) || !Require(NewAuthorizedPersonName, "Yetkili kişi adı")) return;
        await ExecuteAsync(async () =>
        {
            var request = AuthorizedPersonRequest(SelectedCustomer.Id);
            var item = IsEditingAuthorizedPerson
                ? await commercialService.UpdateAuthorizedPersonAsync(SelectedAuthorizedPersonId, request)
                : await commercialService.CreateAuthorizedPersonAsync(request);
            ReplaceOrAdd(AuthorizedPersons, item); ResetAuthorizedPersonForm();
        });
    }

    private int SelectedAuthorizedPersonId { get; set; }
    [RelayCommand] private void EditAuthorizedPerson(CustomerAuthorizedPersonReadDto? person)
    {
        if (person is null) return;
        SelectedAuthorizedPersonId = person.Id; IsEditingAuthorizedPerson = true; NewAuthorizedPersonName = person.FullName;
        NewAuthorizedPersonTitle = person.Title ?? string.Empty; NewAuthorizedPersonPhone = person.Phone ?? string.Empty;
        NewAuthorizedPersonEmail = person.Email ?? string.Empty; NewAuthorizedPersonIsPrimary = person.IsPrimary;
    }

    [RelayCommand] public async Task DeactivateAuthorizedPersonAsync(CustomerAuthorizedPersonReadDto? person)
    {
        if (person is null) return;
        await ExecuteAsync(async () => { await commercialService.DeactivateAuthorizedPersonAsync(person.Id); await LoadCustomerChildrenAsync(SelectedCustomer); });
    }

    [RelayCommand] public async Task CreateFleetAsync()
    {
        if (SelectedCustomer is null || !Require(NewFleetCode, "Filo kodu") || !Require(NewFleetName, "Filo adı")) return;
        await ExecuteAsync(async () =>
        {
            var request = new FleetSaveDto { CustomerId = SelectedCustomer.Id, Code = NewFleetCode, Name = NewFleetName, Description = Blank(NewFleetDescription), RequestStatus = "PENDING", IsActive = true };
            var item = IsEditingFleet && SelectedFleet is not null ? await commercialService.UpdateFleetAsync(SelectedFleet.Id, request) : await commercialService.CreateFleetAsync(request);
            ReplaceOrAdd(Fleets, item); SelectedFleet = item; ResetFleetForm();
        });
    }

    [RelayCommand] private void NewFleet() { ResetFleetForm(); IsFleetFormOpen = true; }
    [RelayCommand] private void CancelFleetForm() => ResetFleetForm();
    [RelayCommand] private void EditFleet(FleetReadDto? fleet)
    {
        if (fleet is null) return;
        SelectedFleet = fleet; IsEditingFleet = true; IsFleetFormOpen = true; NewFleetCode = fleet.Code; NewFleetName = fleet.Name; NewFleetDescription = fleet.Description ?? string.Empty;
    }

    [RelayCommand] public async Task CreateFleetGroupAsync()
    {
        if (SelectedFleet is null) { ErrorMessage = "Önce bir filo seçin."; return; }
        if (!Require(NewGroupCode, "Grup kodu") || !Require(NewGroupName, "Grup adı")) return;
        await ExecuteAsync(async () =>
        {
            var request = new FleetGroupSaveDto { FleetId = SelectedFleet.Id, Code = NewGroupCode, Name = NewGroupName, Description = Blank(NewGroupDescription), IsActive = true };
            var item = IsEditingFleetGroup && SelectedFleetGroup is not null ? await commercialService.UpdateFleetGroupAsync(SelectedFleetGroup.Id, request) : await commercialService.CreateFleetGroupAsync(request);
            ReplaceOrAdd(FleetGroups, item);
            if (SelectedFleet is { } fleet)
            {
                fleet.GroupCount = FleetGroups.Count;
                var fleetIndex = Fleets.IndexOf(fleet);
                if (fleetIndex >= 0) Fleets[fleetIndex] = fleet;
            }
            SelectedFleetGroup = item; ResetFleetGroupForm();
        });
    }

    [RelayCommand] private void NewFleetGroup()
    {
        if (SelectedFleet is null) { ErrorMessage = "Önce bir filo seçin."; return; }
        ResetFleetGroupForm();
        IsFleetGroupFormOpen = true;
    }
    [RelayCommand] private void CancelFleetGroupForm() => ResetFleetGroupForm();
    [RelayCommand] private void EditFleetGroup(FleetGroupReadDto? group)
    {
        if (group is null) return;
        SelectedFleetGroup = group; IsEditingFleetGroup = true; IsFleetGroupFormOpen = true; NewGroupCode = group.Code; NewGroupName = group.Name; NewGroupDescription = group.Description ?? string.Empty;
    }

    [RelayCommand] public async Task CreateVehicleAsync()
    {
        if (SelectedFleetGroup is null || !Require(NewPlate, "Plaka")) return;
        await ExecuteAsync(async () =>
        {
            var request = new VehicleSaveDto { FleetGroupId = SelectedFleetGroup.Id, Plate = NewPlate, Brand = Blank(NewVehicleBrand), Model = Blank(NewVehicleModel), VehicleType = Blank(NewVehicleType), Description = Blank(NewVehicleDescription), IsActive = true };
            var item = IsEditingVehicle && SelectedVehicle is not null ? await commercialService.UpdateVehicleAsync(SelectedVehicle.Id, request) : await commercialService.CreateVehicleAsync(request);
            ReplaceOrAdd(Vehicles, item); SelectedVehicle = item; ResetVehicleForm();
        });
    }

    [RelayCommand] private void EditVehicle(VehicleReadDto? vehicle)
    {
        if (vehicle is null) return;
        SelectedVehicle = vehicle; IsEditingVehicle = true; NewPlate = vehicle.Plate; NewVehicleBrand = vehicle.Brand ?? string.Empty;
        NewVehicleModel = vehicle.Model ?? string.Empty; NewVehicleType = vehicle.VehicleType ?? string.Empty; NewVehicleDescription = vehicle.Description ?? string.Empty;
    }

    [RelayCommand] public async Task CreateDriverAsync()
    {
        if (!Require(NewDriverName, "Sürücü adı")) return;
        await ExecuteAsync(async () =>
        {
            var request = new DriverSaveDto { FullName = NewDriverName, Phone = Blank(NewDriverPhone), ReferenceCode = Blank(NewDriverReferenceCode), LicenseNumber = Blank(NewDriverLicenseNumber), IsActive = true };
            var item = IsEditingDriver && SelectedDriver is not null ? await commercialService.UpdateDriverAsync(SelectedDriver.Id, request) : await commercialService.CreateDriverAsync(request);
            ReplaceOrAdd(Drivers, item); SelectedDriver = item; ResetDriverForm();
        });
    }

    [RelayCommand] private void EditDriver(DriverReadDto? driver)
    {
        if (driver is null) return;
        SelectedDriver = driver; IsEditingDriver = true; NewDriverName = driver.FullName; NewDriverPhone = driver.Phone ?? string.Empty; NewDriverReferenceCode = driver.ReferenceCode ?? string.Empty; NewDriverLicenseNumber = driver.LicenseNumber ?? string.Empty;
    }

    [RelayCommand] public async Task AssignSelectedDriverAsync()
    {
        if (SelectedDriver is null || SelectedVehicle is null) { ErrorMessage = "Atama için bir sürücü ve araç seçin."; return; }
        await ExecuteAsync(async () =>
        {
            await commercialService.CreateAssignmentAsync(new DriverVehicleAssignmentSaveDto { DriverId = SelectedDriver.Id, VehicleId = SelectedVehicle.Id, AssignedFrom = DateOnly.FromDateTime(DateTime.Today), Status = "ACTIVE" });
            Replace(Assignments, await commercialService.GetAssignmentsAsync(vehicleId: SelectedVehicle.Id));
        });
    }

    [RelayCommand] public async Task CancelAssignmentAsync(DriverVehicleAssignmentReadDto? assignment)
    {
        if (assignment is null) return;
        await ExecuteAsync(async () => { await commercialService.CancelAssignmentAsync(assignment.Id); await LoadAssignmentsAsync(SelectedVehicle); });
    }

    // Edit commands intentionally reuse the small inline form fields. This keeps a single
    // MVVM editing path while backend rules remain the authority for invalid changes.
    [RelayCommand] public async Task UpdateAuthorizedPersonAsync(CustomerAuthorizedPersonReadDto? person)
    { if (!CanManage(person is not null)) return; await ExecuteAsync(async () => { await commercialService.UpdateAuthorizedPersonAsync(person!.Id, new CustomerAuthorizedPersonSaveDto { FullName = person.FullName, Title = person.Title, Phone = person.Phone, Email = person.Email, IsPrimary = person.IsPrimary, IsActive = person.IsActive }); await LoadCustomerChildrenAsync(SelectedCustomer); }); }
    [RelayCommand] public async Task UpdateFleetAsync(FleetReadDto? fleet)
    { if (!CanManage(fleet is not null)) return; await ExecuteAsync(async () => { await commercialService.UpdateFleetAsync(fleet!.Id, new FleetSaveDto { CustomerId = fleet.CustomerId, Code = fleet.Code, Name = fleet.Name, Description = fleet.Description, RequestStatus = fleet.RequestStatus, IsActive = fleet.IsActive }); await LoadCustomerChildrenAsync(SelectedCustomer); }); }
    [RelayCommand] public async Task DeactivateFleetAsync(FleetReadDto? fleet)
    { if (!CanManage(fleet is not null)) return; await ExecuteAsync(async () => { await commercialService.DeactivateFleetAsync(fleet!.Id); await LoadCustomerChildrenAsync(SelectedCustomer); }); }
    [RelayCommand] private async Task ToggleFleetActiveAsync()
    {
        if (!CanManage(SelectedFleet is not null)) return;
        var fleet = SelectedFleet!;
        await ExecuteAsync(async () =>
        {
            var updated = await commercialService.UpdateFleetAsync(fleet.Id, new FleetSaveDto { CustomerId = fleet.CustomerId, Code = fleet.Code, Name = fleet.Name, Description = fleet.Description, RequestStatus = fleet.RequestStatus, IsActive = !fleet.IsActive });
            await RefreshFleetsAsync(updated.Id);
        });
    }
    [RelayCommand] public async Task UpdateFleetGroupAsync(FleetGroupReadDto? group)
    { if (!CanManage(group is not null)) return; await ExecuteAsync(async () => { await commercialService.UpdateFleetGroupAsync(group!.Id, new FleetGroupSaveDto { FleetId = group.FleetId, Code = group.Code, Name = group.Name, Description = group.Description, IsActive = group.IsActive }); await LoadFleetGroupsAsync(SelectedFleet); }); }
    [RelayCommand] public async Task DeactivateFleetGroupAsync(FleetGroupReadDto? group)
    { if (!CanManage(group is not null)) return; await ExecuteAsync(async () => { await commercialService.DeactivateFleetGroupAsync(group!.Id); await LoadFleetGroupsAsync(SelectedFleet); }); }
    [RelayCommand] private async Task ToggleFleetGroupActiveAsync()
    {
        if (!CanManage(SelectedFleetGroup is not null)) return;
        var group = SelectedFleetGroup!;
        await ExecuteAsync(async () =>
        {
            await commercialService.UpdateFleetGroupAsync(group.Id, new FleetGroupSaveDto { FleetId = group.FleetId, Code = group.Code, Name = group.Name, Description = group.Description, IsActive = !group.IsActive });
            await LoadFleetGroupsAsync(SelectedFleet, group.Id);
        });
    }
    [RelayCommand] public async Task UpdateVehicleAsync(VehicleReadDto? vehicle)
    { if (!CanManage(vehicle is not null)) return; await ExecuteAsync(async () => { await commercialService.UpdateVehicleAsync(vehicle!.Id, new VehicleSaveDto { FleetGroupId = vehicle.FleetGroupId, Plate = vehicle.Plate, Brand = vehicle.Brand, Model = vehicle.Model, VehicleType = vehicle.VehicleType, IsActive = vehicle.IsActive }); await LoadVehiclesAsync(SelectedFleetGroup); }); }
    [RelayCommand] public async Task DeactivateVehicleAsync(VehicleReadDto? vehicle)
    { if (!CanManage(vehicle is not null)) return; await ExecuteAsync(async () => { await commercialService.DeactivateVehicleAsync(vehicle!.Id); await LoadVehiclesAsync(SelectedFleetGroup); }); }
    [RelayCommand] public async Task UpdateDriverAsync(DriverReadDto? driver)
    { if (!CanManage(driver is not null)) return; await ExecuteAsync(async () => { await commercialService.UpdateDriverAsync(driver!.Id, new DriverSaveDto { FullName = driver.FullName, ReferenceCode = driver.ReferenceCode, Phone = driver.Phone, LicenseNumber = driver.LicenseNumber, IsActive = driver.IsActive }); Replace(Drivers, await commercialService.GetDriversAsync()); }); }
    [RelayCommand] public async Task DeactivateDriverAsync(DriverReadDto? driver)
    { if (!CanManage(driver is not null)) return; await ExecuteAsync(async () => { await commercialService.DeactivateDriverAsync(driver!.Id); Replace(Drivers, await commercialService.GetDriversAsync()); }); }
    [RelayCommand] public async Task UpdateAssignmentAsync(DriverVehicleAssignmentReadDto? assignment)
    { if (!CanManage(assignment is not null)) return; await ExecuteAsync(async () => { await commercialService.UpdateAssignmentAsync(assignment!.Id, new DriverVehicleAssignmentSaveDto { DriverId = assignment.DriverId, VehicleId = assignment.VehicleId, AssignedFrom = assignment.AssignedFrom, AssignedUntil = assignment.AssignedUntil, Status = assignment.Status }); await LoadAssignmentsAsync(SelectedVehicle); }); }

    private async Task LoadCustomerChildrenAsync(CustomerReadDto? customer)
    {
        SelectedFleetGroup = null; SelectedFleet = null;
        AuthorizedPersons.Clear(); Fleets.Clear(); FleetGroups.Clear(); Vehicles.Clear(); Assignments.Clear();
        if (customer is null) return;
        try
        {
            Replace(AuthorizedPersons, await commercialService.GetAuthorizedPersonsAsync(customer.Id));
            var fleets = (await commercialService.GetFleetsAsync(customer.Id)).ToList();
            await PopulateFleetGroupCountsAsync(fleets);
            Replace(Fleets, fleets);
            SelectedFleet = Fleets.FirstOrDefault();
        }
        catch (Exception ex) { ErrorMessage = ToMessage(ex); }
    }
    private async Task RefreshFleetsAsync(int? selectedFleetId = null)
    {
        if (SelectedCustomer is null) return;
        var fleets = (await commercialService.GetFleetsAsync(SelectedCustomer.Id)).ToList();
        await PopulateFleetGroupCountsAsync(fleets);
        Replace(Fleets, fleets);
        SelectedFleet = selectedFleetId is int id ? Fleets.FirstOrDefault(item => item.Id == id) : Fleets.FirstOrDefault();
    }
    private async Task PopulateFleetGroupCountsAsync(IEnumerable<FleetReadDto> fleets)
    {
        var fleetList = fleets.ToList();
        var groupLists = await Task.WhenAll(fleetList.Select(fleet => commercialService.GetFleetGroupsAsync(fleet.Id)));
        for (var index = 0; index < fleetList.Count; index++)
            fleetList[index].GroupCount = groupLists[index].Count;
    }
    private async Task LoadFleetGroupsAsync(FleetReadDto? fleet, int? selectedGroupId = null)
    {
        SelectedFleetGroup = null;
        FleetGroups.Clear(); Vehicles.Clear(); Assignments.Clear(); if (fleet is null) return;
        try
        {
            Replace(FleetGroups, await commercialService.GetFleetGroupsAsync(fleet.Id));
            SelectedFleetGroup = selectedGroupId is int id ? FleetGroups.FirstOrDefault(item => item.Id == id) : null;
        }
        catch (Exception ex) { ErrorMessage = ToMessage(ex); }
    }
    private async Task LoadVehiclesAsync(FleetGroupReadDto? group)
    {
        Vehicles.Clear(); Assignments.Clear(); if (group is null) return;
        try { Replace(Vehicles, await commercialService.GetVehiclesAsync(group.Id)); SelectedVehicle = Vehicles.FirstOrDefault(); } catch (Exception ex) { ErrorMessage = ToMessage(ex); }
    }
    private async Task LoadAssignmentsAsync(VehicleReadDto? vehicle)
    {
        Assignments.Clear(); if (vehicle is null) return;
        try { Replace(Assignments, await commercialService.GetAssignmentsAsync(vehicleId: vehicle.Id)); } catch (Exception ex) { ErrorMessage = ToMessage(ex); }
    }
    private async Task LoadAssignmentsForDriverAsync(DriverReadDto? driver)
    {
        if (driver is null || SelectedVehicle is not null) return;
        try { Replace(Assignments, await commercialService.GetAssignmentsAsync(driverId: driver.Id)); } catch (Exception ex) { ErrorMessage = ToMessage(ex); }
    }
    private async Task ExecuteAsync(Func<Task> action) { if (IsLoading) return; IsLoading = true; ErrorMessage = null; try { await action(); } catch (Exception ex) { ErrorMessage = ToMessage(ex); } finally { IsLoading = false; } }
    private bool ValidateCustomer()
    {
        if (!Require(NewCode, "Müşteri kodu") || !Require(NewName, "Müşteri adı")) return false;
        if (NewCustomerDiscountRate is < 0 or > 100) { ErrorMessage = "İskonto oranı 0 ile 100 arasında olmalıdır."; return false; }
        return ValidateEmail(NewCustomerEmail);
    }
    private bool ValidateEmail(string value)
    {
        if (string.IsNullOrWhiteSpace(value) || (value.Contains('@') && value.IndexOf('@') > 0 && value.LastIndexOf('.') > value.IndexOf('@') + 1)) return true;
        ErrorMessage = "Geçerli bir e-posta adresi girin."; return false;
    }
    private CustomerSaveDto CustomerRequest() => new() { Code = NewCode, Name = NewName, CustomerType = NewCustomerType, Sector = Blank(NewCustomerSector), DiscountRate = NewCustomerDiscountRate, RequestStatus = NewCustomerRequestStatus, Phone = Blank(NewCustomerPhone), Email = Blank(NewCustomerEmail), TaxNumber = Blank(NewCustomerTaxNumber), TaxOffice = Blank(NewCustomerTaxOffice), IsActive = true };
    private CustomerAuthorizedPersonSaveDto AuthorizedPersonRequest(int customerId) => new() { CustomerId = customerId, FullName = NewAuthorizedPersonName, Title = Blank(NewAuthorizedPersonTitle), Phone = Blank(NewAuthorizedPersonPhone), Email = Blank(NewAuthorizedPersonEmail), IsPrimary = NewAuthorizedPersonIsPrimary, IsActive = true };
    private void ResetCustomerForm() { IsEditingCustomer = false; NewCode = NewName = NewCustomerSector = NewCustomerPhone = NewCustomerEmail = NewCustomerTaxNumber = NewCustomerTaxOffice = string.Empty; NewCustomerType = "COMPANY"; NewCustomerDiscountRate = 0; NewCustomerRequestStatus = "PENDING"; }
    private void ResetAuthorizedPersonForm() { IsEditingAuthorizedPerson = false; SelectedAuthorizedPersonId = 0; NewAuthorizedPersonName = NewAuthorizedPersonTitle = NewAuthorizedPersonPhone = NewAuthorizedPersonEmail = string.Empty; NewAuthorizedPersonIsPrimary = false; }
    private void ResetFleetForm() { IsEditingFleet = false; IsFleetFormOpen = false; NewFleetCode = NewFleetName = NewFleetDescription = string.Empty; }
    private void ResetFleetGroupForm() { IsEditingFleetGroup = false; IsFleetGroupFormOpen = false; NewGroupCode = NewGroupName = NewGroupDescription = string.Empty; }
    private void ResetVehicleForm() { IsEditingVehicle = false; NewPlate = NewVehicleBrand = NewVehicleModel = NewVehicleType = NewVehicleDescription = string.Empty; }
    private void ResetDriverForm() { IsEditingDriver = false; NewDriverName = NewDriverPhone = NewDriverReferenceCode = NewDriverLicenseNumber = string.Empty; }
    private bool Require(string value, string label) { if (!string.IsNullOrWhiteSpace(value)) return true; ErrorMessage = $"{label} zorunludur."; return false; }
    private bool CanManage(bool hasSelection) { if (!hasSelection) return false; if (IsAdmin) return true; ErrorMessage = "Bu işlem yalnızca ADMIN rolü için kullanılabilir."; return false; }
    private static string? Blank(string value) => string.IsNullOrWhiteSpace(value) ? null : value.Trim();
    private static string ToMessage(Exception ex)
    {
        var api = ex as ApiException;
        var message = api?.Message ?? ex.Message;
        return message switch
        {
            _ when api?.ErrorCode == "VALIDATION_ERROR" || message.Contains("Request validation failed", StringComparison.OrdinalIgnoreCase) => "Girilen bilgiler doğrulanamadı. Zorunlu alanları ve biçimlerini kontrol edin.",
            var text when text.Contains("already exists", StringComparison.OrdinalIgnoreCase) => "Bu kod zaten kullanılıyor.",
            var text when text.Contains("active fuel card", StringComparison.OrdinalIgnoreCase) => "Bu araca zaten aktif bir kart tanımlı.",
            var text when text.Contains("Driver assignment overlaps", StringComparison.OrdinalIgnoreCase) => "Seçili sürücünün bu tarih aralığında başka bir araç ataması bulunuyor.",
            var text when text.Contains("Vehicle already has another driver", StringComparison.OrdinalIgnoreCase) => "Seçili araçta bu tarih aralığında başka bir sürücü ataması bulunuyor.",
            var text when text.Contains("Assignment end date", StringComparison.OrdinalIgnoreCase) => "Atama bitiş tarihi başlangıç tarihinden önce olamaz.",
            var text when text.Contains("Driver is inactive", StringComparison.OrdinalIgnoreCase) => "Pasif bir sürücü araca atanamaz.",
            var text when text.Contains("Vehicle hierarchy is inactive", StringComparison.OrdinalIgnoreCase) => "Araç, bağlı olduğu müşteri hiyerarşisi pasif olduğu için atanamaz.",
            var text when text.Contains("primary", StringComparison.OrdinalIgnoreCase) => "Bu müşteri için birincil yetkili kuralı sağlanamadı.",
            _ => message,
        };
    }
    private static void Replace<T>(ObservableCollection<T> target, IEnumerable<T> source) { target.Clear(); foreach (var item in source) target.Add(item); }
    private static void ReplaceOrAdd<T>(ObservableCollection<T> target, T item) where T : class
    {
        var id = item.GetType().GetProperty("Id")?.GetValue(item);
        var current = target.FirstOrDefault(candidate => Equals(candidate.GetType().GetProperty("Id")?.GetValue(candidate), id));
        if (current is null) target.Add(item); else target[target.IndexOf(current)] = item;
    }
}
