using System.Collections.Specialized;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using FuelMind.Desktop.Collections; using FuelMind.Desktop.Dtos.Live; using FuelMind.Desktop.Services; using FuelMind.Desktop.State; using LiveChartsCore; using LiveChartsCore.Kernel; using LiveChartsCore.SkiaSharpView; using LiveChartsCore.SkiaSharpView.WPF;
namespace FuelMind.Desktop.ViewModels;
public sealed partial class PumpDetailViewModel : ObservableObject
{ readonly LiveDataStore _store;readonly LiveChartDataService _charts;readonly DetailNavigationService _nav;readonly LineSeries<LiveChartPoint> _line;
 public PumpDetailViewModel(LiveDataStore store,LiveChartDataService charts,DetailNavigationService nav){_store=store;_charts=charts;_nav=nav;_store.Pumps.CollectionChanged+=Changed;_line=new(){Name="Flow rate",Values=[],GeometrySize=0,LineSmoothness=0,Fill=null,AnimationsSpeed=TimeSpan.Zero,Mapping=(p,_)=>new Coordinate(p.Timestamp.UtcDateTime.Ticks,p.Value)};Series=[_line];XAxes=[new Axis{Labeler=v=>new DateTime((long)v,DateTimeKind.Utc).ToLocalTime().ToString("HH:mm:ss")}];YAxes=[new Axis{Name="Flow rate",MinLimit=0}];}
 [ObservableProperty]int? _pumpId;[ObservableProperty]string _metric="flow_rate"; public ISeries[] Series{get;}public Axis[] XAxes{get;}public Axis[] YAxes{get;}public PumpLiveDataDto? Pump=>PumpId is int id?_store.Pumps.FirstOrDefault(x=>x.PumpId==id):null;
 public void Select(int id){PumpId=id;Update();} partial void OnMetricChanged(string value)=>Update(); void Update(){if(PumpId is int id)_line.Values=_charts.GetSeries(LiveChartDataService.GetPumpMetricKey(id,Metric));_line.Name=Metric;YAxes[0].Name=Metric;OnPropertyChanged(nameof(Pump));}void Changed(object?s,NotifyCollectionChangedEventArgs e)=>OnPropertyChanged(nameof(Pump));[RelayCommand]void Back()=>_nav.BackToPumps(); }
