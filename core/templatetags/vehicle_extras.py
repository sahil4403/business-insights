from django import template

register = template.Library()

VEHICLE_ICONS = {
    'HYVA': '🚛',
    'TRACTOR': '🚜',
    'HALFTON': '🚚',
    'JCB': '🏗️',
}

DEFAULT_ICON = '🚚'


@register.filter
def vehicle_icon(vehicle):
    if not vehicle:
        return DEFAULT_ICON
    vehicle_type = getattr(vehicle, 'vehicle_type', None)
    key = (
        getattr(vehicle_type, 'code', '') or ''
        or getattr(vehicle_type, 'name', '') or ''
    ).strip().upper()
    return VEHICLE_ICONS.get(key, DEFAULT_ICON)
