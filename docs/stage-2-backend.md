# Aşama 2 — Backend

## Aşama 2 özeti

Bu aşama; PostgreSQL veri modeli, Alembic migration’ları, JWT kimlik doğrulaması, rol tabanlı yetkilendirme, temel CRUD API’leri ve stok hareketi transaction’larını tamamlar.

## Kullanılan teknolojiler

- Python 3.13, FastAPI, Pydantic v2
- PostgreSQL, SQLAlchemy 2.x, Alembic, psycopg
- python-jose ile JWT; passlib ve bcrypt ile parola özeti
- pytest, Ruff ve Black

## Klasör yapısı

- `backend/app/models/`: SQLAlchemy tabloları
- `backend/app/schemas/`: Pydantic istek/cevap şemaları
- `backend/app/repositories/`: veri erişimi
- `backend/app/services/`: iş kuralları ve transaction’lar
- `backend/app/api/`: FastAPI routerları ve bağımlılıklar
- `backend/migrations/`: Alembic ortamı ve revision’lar
- `backend/tests/`: izole API, auth, güvenlik ve iş kuralı testleri

## Veritabanı tabloları

`users`, `stations`, `fuel_types`, `tanks`, `pumps`, `sales`, `sensor_readings`, `deliveries`, `alarms`, `forecasts`, `order_recommendations`, `model_versions`, `simulation_scenarios`.

## Temel ilişkiler

İstasyonların tankları ve pompaları vardır. Tank bir yakıt türüne bağlıdır. Pompa bir tanka bağlıdır. Satış; istasyon, tank, pompa ve yakıt türünü bağlar. Dolum tanka bağlıdır. Alarm, sensör kaydı, tahmin ve sipariş önerileri ilgili operasyonel varlıklara bağlanır.

## Enumlar

`UserRole`, `PumpStatus`, `SensorStatus`, `AnomalyType`, `AlarmSeverity`, `AlarmStatus`, `RecommendationPriority`, `RecommendationStatus`, `SimulationTargetType` ve `SimulationStatus` PostgreSQL enum tipleri olarak tekil biçimde oluşturulur.

## Migration kullanımı

```powershell
cd backend
alembic upgrade head
alembic current
alembic history
alembic revision --autogenerate -m "schema_change"
alembic downgrade -1
```

## Backend çalıştırma

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

`DATABASE_URL` ve `SECRET_KEY` değerleri `.env` dosyasından alınır.

## Swagger kullanımı

Swagger UI `http://127.0.0.1:8000/docs` adresindedir. JSON login için `/api/auth/login`, Swagger Authorize akışı için form-data kabul eden `/api/auth/token` kullanılır.

## Demo kullanıcı oluşturma

Yalnızca geliştirme ortamında `ENABLE_DEMO_USERS=true` iken aşağıdaki komut `admin` ve `operator` kullanıcılarını oluşturur. Parolalar `.env` üzerinden alınır ve yalnızca bcrypt özeti saklanır.

```powershell
python -m app.seed
```

## API endpointleri

- `/api/auth`: login, token ve mevcut kullanıcı
- `/api/fuel-types`, `/api/stations`, `/api/tanks`, `/api/pumps`, `/api/users`: temel yönetim endpointleri
- `/api/sales`, `/api/deliveries`: listeleme, detay ve kayıt oluşturma
- `/api/health`: servis sağlık kontrolü

## İş kuralları

ADMIN ana tanımları ve kullanıcıları yönetir. OPERATOR tanımları görüntüler, satış ve dolum oluşturur. Satış ve dolum, tank satırını kilitleyerek stok seviyesini tek transaction içinde değiştirir; hata halinde rollback uygulanır. Geçmişi korumak için silme işlemleri pasifleştirme olarak uygulanır.

## Test komutları

```powershell
python -m pytest
ruff check .
black --check .
```

## Bilinen sınırlamalar

Integration testleri gerçek üretim veritabanına bağlanmaz; fake repository/session kullanır. PostgreSQL migration testi ise yalnızca yapılandırılmış yerel geliştirme veritabanında çalıştırılmalıdır. Pagination şu aşamada bellek içi filtreleme uygular; veri hacmi büyüdüğünde repository sorgularına taşınmalıdır.

## Aşama 3’e geçiş notları

Sensör veri alımı, anomali tespiti, tahminleme, sipariş önerileri, masaüstü istemcisi ve üretim gözlemlenebilirliği sonraki aşamada genişletilecektir.
