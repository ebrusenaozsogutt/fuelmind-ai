# FuelMind AI Backend

FastAPI tabanlı FuelMind AI backend uygulaması.

## Windows PowerShell ile çalıştırma

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Uygulama varsayılan olarak `http://127.0.0.1:8000` adresinde başlar.

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI şeması: `http://127.0.0.1:8000/openapi.json`
- Sağlık kontrolü: `http://127.0.0.1:8000/api/health`

## PostgreSQL ve Alembic migrations

Önce PostgreSQL içinde uygulama kullanıcısını ve veritabanını oluşturun:

```sql
CREATE USER fuelmind_user WITH PASSWORD 'change-this-password';
CREATE DATABASE fuelmind_db OWNER fuelmind_user;
```

Ardından `.env` içindeki `DATABASE_URL` değerini kullanıcı adı, parola, sunucu ve veritabanı adınıza göre güncelleyin. `backend` klasöründe aşağıdaki Alembic komutlarını kullanın:

```powershell
alembic revision --autogenerate -m "add_new_schema_change"
alembic upgrade head
alembic current
alembic history
alembic downgrade -1
```

İlk şemayı oluşturmak için doğrudan `alembic upgrade head` komutunu çalıştırın. Yeni migration üretmeden önce model importlarının `app.models` altında güncel olduğundan emin olun.

## Geliştirme demo kullanıcıları

Demo kullanıcıları yalnızca `ENVIRONMENT=development` ve `ENABLE_DEMO_USERS=true` iken oluşturulur. `.env` içinde `DEMO_ADMIN_PASSWORD` ve `DEMO_OPERATOR_PASSWORD` değerlerini ayarladıktan sonra aşağıdaki komutu kullanın. Parolalar veritabanına yalnızca bcrypt özeti olarak kaydedilir.

```powershell
python -m app.seed
```
