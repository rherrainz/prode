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
7. Actualizar fixture y resultados desde `/tournaments/admin/`.
   `Actualizar fixture` toma cruces confirmados desde FIFA y conserva lo ya cargado en la base.
   `Traer resultados API` usa TheSportsDB como fuente principal y FIFA como fallback para resultados, ganadores y penales.
   Al editar resultado o estado desde Django Admin en `Match`, los pronósticos del partido se recalculan automáticamente.
8. Si se necesita recalcular manualmente, ejecutar:

```powershell
python manage.py recalculate_points
```

9. Revisar la tabla de posiciones del torneo. La tabla muestra puntos totales y cambio de posición desde la última actualización de resultados.

## Comandos

```powershell
python manage.py seed_worldcup_structure
python manage.py recalculate_points
python manage.py recalculate_points --tournament slug-del-torneo
python manage.py recalculate_points --match 1
python manage.py sync_api_football_stub
python manage.py sync_thesportsdb_results --dry-run
python manage.py sync_results_and_recalculate --days-back 1 --days-forward 1
```

`seed_worldcup_structure` carga los 12 grupos sorteados, 48 equipos y los 104 partidos desde `apps/matches/data/world_cup_2026_schedule.csv`. Es un comando de bootstrap inicial/desarrollo: en producción, el fixture actualizado se toma desde FIFA. Si se ejecuta luego de tener cruces confirmados, conserva equipos ya cargados cuando el CSV todavía dice `TBD`.

`sync_results_and_recalculate` primero actualiza el fixture confirmado desde FIFA, luego sincroniza resultados desde TheSportsDB con fallback FIFA y recalcula puntos. Cuando cambian puntajes, también actualiza el snapshot de posiciones para mostrar subidas y bajadas en el leaderboard.

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

Para actualizar cruces confirmados, horarios y sedes desde FIFA, usar el panel staff en `/tournaments/admin/` con `Actualizar fixture` o ejecutar:

```bash
python manage.py sync_results_and_recalculate --days-back 1 --days-forward 1 --fixture-days-forward 14
```

El CSV queda reservado para bootstrap inicial o recuperación local. Si se necesita reconstruir estructura base:

```bash
python manage.py migrate
python manage.py seed_worldcup_structure
```

Para verificar el conteo:

```bash
python manage.py shell -c "from apps.teams.models import WorldCupGroup, Team; from apps.matches.models import Match; print(WorldCupGroup.objects.count(), Team.objects.count(), Match.objects.count())"
```

El resultado esperado es `12 48 104`. Si se cargaron resultados manuales o se corrigieron puntajes, recalcular puntos después:

```bash
python manage.py recalculate_points
```

También se puede hacer desde `/tournaments/admin/` con un usuario staff usando:

- `Actualizar fixture`: consulta FIFA y actualiza cruces confirmados sin volver a `TBD`.
- `Traer resultados API`: actualiza fixture, trae resultados desde TheSportsDB con fallback FIFA y recalcula puntos.

## Railway

Variables recomendadas:

```text
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=tu-dominio.up.railway.app
CSRF_TRUSTED_ORIGINS=https://tu-dominio.up.railway.app
DATABASE_ENGINE=postgres
DATABASE_URL=${{Postgres.DATABASE_URL}}
API_FOOTBALL_KEY=
API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io
THESPORTSDB_API_KEY=123
THESPORTSDB_BASE_URL=https://www.thesportsdb.com/api/v1/json
THESPORTSDB_WORLD_CUP_LEAGUE_ID=4429
THESPORTSDB_WORLD_CUP_SEASON=2026
FIFA_API_BASE_URL=https://api.fifa.com/api/v3
FIFA_API_LANGUAGE=en
FIFA_API_MATCH_COUNT=200
FIFA_WORLD_CUP_COMPETITION_ID=17
FIFA_WORLD_CUP_SEASON_ID=285023
```

Para persistir SQLite en Railway, montar un volumen y usar `DATABASE_PATH=/data/db.sqlite3`.

Las variables `FIFA_*` tienen defaults en `settings.py` y no requieren API key. Se pueden omitir en Railway salvo que se quiera cambiar el endpoint o los IDs sin modificar código.

### Servicios en Railway

Usar dos servicios separados con el mismo repo:

- `web`: servicio principal con dominio público. No debe tener `Cron Schedule` ni `RUN_MODE=cron`.
- `results-cron`: servicio sin dominio público, con `RUN_MODE=cron` y `Cron Schedule` configurado.

El `startCommand` de `railway.json` detecta `RUN_MODE=cron`:

- En `web`, ejecuta migraciones, `collectstatic`, intenta sincronizar resultados y luego levanta Gunicorn.
- En `results-cron`, ejecuta solo `sync_results_and_recalculate`.

Cron recomendado:

```text
0 */2 * * *
```

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
python manage.py sync_results_and_recalculate --date 2026-06-15 --days-back 1 --days-forward 1
```

La sincronización consulta `eventsday.php` y usa `eventsseason.php` como fallback para partidos que TheSportsDB omite en la consulta diaria. También contempla partidos cuyo día UTC difiere del día ET, por ejemplo partidos de madrugada.

Para Railway Cron cada 2 horas:

```bash
python manage.py sync_results_and_recalculate --days-back 1 --days-forward 1
```

## Leaderboard

La tabla de posiciones está limitada a un ancho cómodo en desktop y muestra el cambio de posición desde la última actualización de resultados. El snapshot de posiciones se actualiza cuando `recalculate_predictions()` detecta cambios reales de puntos; si un cron corre sin resultados nuevos, no pisa el último movimiento visible.

## Futuro Google Login

El MVP usa autenticación estándar de Django con usuario, email y contraseña. El modelo queda compatible con agregar Google Login más adelante sin instalar `django-allauth` todavía.
