from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import template
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

register = template.Library()


def _zoneinfo(tz_name):
    try:
        return ZoneInfo(tz_name or settings.TIME_ZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(settings.TIME_ZONE)


@register.filter
def in_timezone(value, tz_name):
    if not value:
        return ''
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone=ZoneInfo('UTC'))
    return timezone.localtime(value, _zoneinfo(tz_name))


@register.filter
def match_datetime(value, tz_name):
    converted = in_timezone(value, tz_name)
    if not converted:
        return ''
    return converted.strftime('%d/%m/%Y %H:%M')


@register.simple_tag(takes_context=True)
def user_timezone(context):
    user = context.get('request').user if context.get('request') else None
    if user and user.is_authenticated:
        try:
            profile = user.profile
            return profile.timezone
        except ObjectDoesNotExist:
            return settings.TIME_ZONE
    return settings.TIME_ZONE
