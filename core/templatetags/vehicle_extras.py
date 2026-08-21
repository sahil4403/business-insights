from django import template

register = template.Library()

VEHICLE_ICONS = {
    'HYVA': '🚛',
    'TRACTOR': '🚜',
    'HALFTON': '🚚',
    'JCB': '🏗️',
}

DEFAULT_ICON = '🚚'

VEHICLE_KEYS = {
    'HYVA': 'hyva',
    'TRACTOR': 'tractor',
    'HALFTON': 'halfton',
    'JCB': 'jcb',
}


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


@register.filter
def vehicle_icon_key(vehicle):
    """Return a lowercase icon key (hyva/tractor/halfton/jcb/truck) for SVG sprites."""
    if not vehicle:
        return 'truck'
    vehicle_type = getattr(vehicle, 'vehicle_type', None)
    key = (
        getattr(vehicle_type, 'code', '') or ''
        or getattr(vehicle_type, 'name', '') or ''
    ).strip().upper()
    return VEHICLE_KEYS.get(key, 'truck')
