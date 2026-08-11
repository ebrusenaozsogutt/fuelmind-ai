using System.Collections.Specialized;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Collections;
using FuelMind.Desktop.Dtos.Live;
using FuelMind.Desktop.Services;
using FuelMind.Desktop.State;
using LiveChartsCore;
using LiveChartsCore.Kernel;
using LiveChartsCore.SkiaSharpView;
using LiveChartsCore.SkiaSharpView.WPF;
namespace FuelMind.Desktop.ViewModels;
public sealed partial class TankDetailViewModel : ObservableObject
{
 readonly LiveDataStore _store; readonly LiveChartDataService _charts; readonly DetailNavigationService _nav; readonly LineSeries<LiveChartPoint> _line;
 public TankDetailViewModel(LiveDataStore store, LiveChartDataService charts, DetailNavigationService nav) { _store=store;_charts=charts;_nav=nav;_store.Tanks.CollectionChanged+=Changed; _line=new(){Name="Measured level",Values=[],GeometrySize=0,LineSmoothness=0,Fill=null,AnimationsSpeed=TimeSpan.Zero,Mapping=(p,_)=>new Coordinate(p.ChartTimestamp,p.ChartValue)}; Series=[_line]; XAxes=[new Axis{Labeler=v=>DateTime.FromOADate(v).ToString("HH:mm:ss"),MinStep=TimeSpan.FromSeconds(1).TotalDays}];YAxes=[new Axis{Name="Liters",Labeler=v=>$"{v:N0} L"}];}
 [ObservableProperty] int? _tankId; public ISeries[] Series{get;} public Axis[] XAxes{get;} public Axis[] YAxes{get;} public TankLiveDataDto? Tank=>TankId is int id?_store.Tanks.FirstOrDefault(x=>x.TankId==id):null; public double? Fill=>Tank is {CapacityLiters:>0} x?(double)(x.MeasuredLevelLiters/x.CapacityLiters*100m):null;
 public void Select(int id){TankId=id;_line.Values=_charts.GetSeries(LiveChartDataService.GetMeasuredTankLevelMetricKey(id));Notify();} void Changed(object? s,NotifyCollectionChangedEventArgs e)=>Notify(); void Notify(){OnPropertyChanged(nameof(Tank));OnPropertyChanged(nameof(Fill));}
 [RelayCommand] void Back()=>_nav.BackToTanks();
}
