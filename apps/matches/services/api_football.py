from django.conf import settings

from apps.matches.models import ApiSyncLog


def sync_fixtures_stub():
    message = 'Stub ejecutado. La integración real con API-Football se agregará más adelante.'
    log = ApiSyncLog.objects.create(
        provider='api-football',
        endpoint=settings.API_FOOTBALL_BASE_URL,
        status='stub',
        request_count=0,
        response_code=None,
        message=message,
    )
    return log
