# Prode Mundial 2026

Aplicación Django monolítica para torneos privados de pronósticos del Mundial FIFA 2026.

## Setup local

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_worldcup_structure
python manage.py runserver
```

Si no activás el entorno, podés ejecutar todo con el Python del venv:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py seed_worldcup_structure
.\.venv\Scripts\python.exe manage.py runserver
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_worldcup_structure
python manage.py runserver
```

Si no activás el entorno, podés ejecutar todo con el Python del venv:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py seed_worldcup_structure
.venv/bin/python manage.py runserver
```

La app queda disponible en `http://127.0.0.1:8000/`.

## Flujo MVP

1. Entrar a `/admin/` con un usuario staff.
2. Crear un `FriendTournament`. El `invite_code` se genera automáticamente.
   El máximo de participantes por torneo es 15.
3. Crear una cuenta desde `/accounts/register/`.
4. Ir a `/tournaments/join/` e ingresar el código de invitación.
5. Opcional: configurar tu zona horaria desde `/accounts/timezone/`.
6. Abrir el torneo, revisar el fixture y guardar pronósticos antes del inicio del partido.
7. Cargar resultados desde Django Admin en `Match` y marcar el partido como `finished`.
8. Ejecutar:

```powershell
python manage.py recalculate_points
```

9. Revisar la tabla de posiciones del torneo.

## Comandos

```powershell
python manage.py seed_worldcup_structure
python manage.py recalculate_points
python manage.py recalculate_points --tournament slug-del-torneo
python manage.py recalculate_points --match 1
python manage.py sync_api_football_stub
python manage.py sync_thesportsdb_results --dry-run
```

`seed_worldcup_structure` carga los 12 grupos sorteados, 48 equipos y los 104 partidos desde `apps/matches/data/world_cup_2026_schedule.csv`. Los horarios se guardan en UTC y cada partido conserva `venue_timezone` para mostrar horario de sede y horario del usuario.

## Verificación local

### Windows PowerShell

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_worldcup_structure
.\.venv\Scripts\python.exe manage.py shell -c "from apps.teams.models import WorldCupGroup, Team; from apps.matches.models import Match; print(WorldCupGroup.objects.count(), Team.objects.count(), Match.objects.count())"
.\.venv\Scripts\python.exe manage.py test apps.tournaments
```

### Linux / macOS

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_worldcup_structure
.venv/bin/python manage.py shell -c 'from apps.teams.models import WorldCupGroup, Team; from apps.matches.models import Match; print(WorldCupGroup.objects.count(), Team.objects.count(), Match.objects.count())'
.venv/bin/python manage.py test apps.tournaments
```

El conteo esperado después del seed es:

```text
12 48 104
```

## Actualizar fixture en servidor

Cuando cambie el fixture versionado o se corrijan horarios, ejecutar en Railway/servidor:

```bash
python manage.py migrate
python manage.py seed_worldcup_structure
```

Para verificar el conteo:

```bash
python manage.py shell -c "from apps.teams.models import WorldCupGroup, Team; from apps.matches.models import Match; print(WorldCupGroup.objects.count(), Team.objects.count(), Match.objects.count())"
```

El resultado esperado es:

```text
12 48 104
```

Si ya había resultados cargados o sincronizados, recalcular puntos después:

```bash
python manage.py recalculate_points
```

## Railway

Variables recomendadas:

```text
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=tu-dominio.up.railway.app
CSRF_TRUSTED_ORIGINS=https://tu-dominio.up.railway.app
DATABASE_PATH=/data/db.sqlite3
API_FOOTBALL_KEY=
API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io
```

Para persistir SQLite en Railway, montar un volumen y usar `DATABASE_PATH=/data/db.sqlite3`.

### Base de datos en producción

Por defecto la app usa SQLite:

```text
DATABASE_ENGINE=sqlite
DATABASE_PATH=/data/db.sqlite3
```

Para Railway PostgreSQL, agregar una base PostgreSQL al proyecto y configurar:

```text
DATABASE_ENGINE=postgres
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

Si `DATABASE_URL` empieza con `postgres://` o `postgresql://`, la app usa PostgreSQL aunque `DATABASE_ENGINE` no esté definido. En producción se recomienda PostgreSQL para evitar problemas de persistencia/concurrencia con SQLite.

## API-Football

La app siempre lee fixtures y resultados desde SQLite. La integración externa queda preparada en `apps.matches.services.api_football` y por ahora el comando `sync_api_football_stub` solo crea un `ApiSyncLog`.

## TheSportsDB

TheSportsDB se puede usar como fuente gratuita para resultados finales. La app sigue leyendo desde SQLite; el comando solo actualiza partidos locales cuando encuentra marcadores.

```powershell
python manage.py sync_thesportsdb_results --date 2026-06-11 --days-back 0 --days-forward 0 --dry-run
python manage.py sync_thesportsdb_results
```

Para Railway Cron cada 2 horas:

```bash
python manage.py sync_thesportsdb_results --days-back 1 --days-forward 1
python manage.py recalculate_points
```

## Futuro Google Login

El MVP usa autenticación estándar de Django con usuario, email y contraseña. El modelo queda compatible con agregar Google Login más adelante sin instalar `django-allauth` todavía.
