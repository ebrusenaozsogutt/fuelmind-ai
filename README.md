# FuelMind AI

## Yapay Zekâ Destekli Akaryakıt İstasyonu İzleme, Anomali Tespiti ve Akıllı Stok Planlama Sistemi

FuelMind AI; tank, USC, port, pompa, nozzle ve probe topolojisini izleyen; simülasyon, ticari satış, alarm/arıza, anomali tespiti, talep tahmini, stok planlama ve raporlama akışlarını birleştiren simülasyon tabanlı endüstriyel prototiptir.

## Ana özellikler

- Canlı istasyon izleme, REST API ve WebSocket yayını.
- Tank / pump / nozzle / probe / USC / communication-port topolojisi ve stateful, tick-based, seed-reproducible simülasyon.
- Customer, vehicle, fuel card, yetkilendirme, fiyat snapshot'ı, totalizer sürekliliği, tank-sale reconciliation, attendant/shift, audit log, alarm ve field-fault yönetimi.
- Isolation Forest ile etiketli arıza verisine ihtiyaç duymadan normal davranıştan sapma analizi; XGBoost ve baseline ile 7 günlük tahmin, kritik stok ve sipariş önerisi.
- Gün sonu, satış, pompacı/vardiya, dolum, tank ölçüm, fiyat değişim, arıza ve müşteri satış raporları; PDF ve CSV dışa aktarma.

Risk skoru bir arıza olasılığı değildir; gözlenen davranışın referans normal davranıştan sapma derecesidir.

## Mimari

```text
C# WPF Desktop → REST + WebSocket → FastAPI Backend → PostgreSQL
                                              └────→ AI Layer
                                                     Isolation Forest
                                                     XGBoost / baseline
Tank → Probe
USC → Port → Pump → Nozzle
```

## Teknolojiler

- C# / .NET 8 / WPF, MVVM, LiveCharts2
- Python, FastAPI, Uvicorn, WebSocket
- PostgreSQL, SQLAlchemy, Alembic
- Isolation Forest, XGBoost, ReportLab ve CSV dışa aktarma

## Proje yapısı

```text
backend/         FastAPI, migrations, seed ve testler
desktop/         WPF uygulaması ve test çözümü
docs/            Tasarım ve teknik dokümantasyon
data/            Kontrollü veri girdileri
trained_models/  Yerel model artifact kökü
reports/         Yerel üretilen rapor çıktıları
```

## Kurulum ve final demo (Windows / PowerShell)

Ön koşullar: PostgreSQL, Python 3 ve .NET 8 SDK.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\alembic.exe upgrade head
python -m scripts.seed_demo
.\.venv\Scripts\uvicorn.exe app.main:app --reload --workers 1
```

`.env` içindeki PostgreSQL bağlantısını yerel veritabanınıza göre düzenleyin. Yerel demo için `ENABLE_DEMO_USERS=true` bırakın. Aktif simülasyon durumu süreç belleğinde olduğundan `--workers 1` kullanılmalıdır. Swagger: <http://127.0.0.1:8000/docs>.

`seed_demo.py` idempotenttir: istasyonu, saha topolojisini, kullanıcıları, müşteri/kart ilişkilerini, fiyat geçmişini, satışları, dolumları ve üç yakıt için forecast kayıtlarını aynı demo işaretleriyle yeniden kullanır. 90 günlük dataset üretimi demo seed’den ayrı bir geliştirme/dataset işlemidir.

### Yerel demo girişleri

| Kullanıcı | Rol | Varsayılan yerel parola |
| --- | --- | --- |
| `admin` | ADMIN | `fuelmind-demo-admin` |
| `operator` | OPERATOR | `fuelmind-demo-operator` |

Bu bilgiler yalnızca local/demo kullanımı içindir. Demo ortamı dışında değiştirin.

### Kısa demo akışı

`Login → Dashboard → Live Monitoring → Simulation → Sales → Alarm / Fault → Forecast → Reports`

## Desktop istemcisi

```powershell
cd desktop
dotnet restore FuelMind.sln
dotnet build FuelMind.sln -c Release
dotnet run --project .\FuelMind.Desktop\FuelMind.Desktop.csproj -c Release
```

Varsayılan API ve WebSocket adresleri `desktop/FuelMind.Desktop/appsettings.json` içindedir.

## Publish

```powershell
cd desktop
dotnet publish .\FuelMind.Desktop\FuelMind.Desktop.csproj -c Release -r win-x64 --self-contained false -o .\artifacts\publish\win-x64
```

Çıktıdaki çalıştırılabilir dosya `desktop/artifacts/publish/win-x64/FuelMind.Desktop.exe` olur. Publish çıktıları Git tarafından ignore edilir.

## Doğrulama

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\alembic.exe heads
cd ..\desktop
dotnet test FuelMind.sln --no-restore
dotnet build FuelMind.sln -c Release --no-restore
```

## Sınırlar

FuelMind AI bu sürümde gerçek RS-485/USC saha cihazına bağlanan bir ürün değildir. Gerçek cihaz entegrasyonuna uygun veri modeli ve arayüzleri bulunan, simülasyonla doğrulanmış bir endüstriyel karar destek prototipidir.
