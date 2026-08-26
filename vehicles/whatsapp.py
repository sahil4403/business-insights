"""
WhatsApp notification sender — UltraMsg style API (configurable via .env).
urllib use hota hai (koi extra package nahi chahiye).

.env me ye add karo (na ho toh WhatsApp skip ho jaata hai, in-app alerts phir bhi chalte hain):

    WHATSAPP_ENABLED=True
    WHATSAPP_API_URL=https://api.ultramsg.com/XXXXX/messages/chat
    WHATSAPP_TOKEN=your_ultramsg_token
    WHATSAPP_TO=919999999999   (country code ke saath, bina +)
"""

import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger('trips')


def send_whatsapp_message(message, to_number=None):
    """
    WhatsApp message bhejo. Return: True bheja, False nahi bheja/skipped/failed.
    Config .env se aata hai — na ho toh gracefully skip.
    """
    if os.getenv('WHATSAPP_ENABLED', 'False').lower() != 'true':
        return False

    api_url = os.getenv('WHATSAPP_API_URL', '')
    token = os.getenv('WHATSAPP_TOKEN', '')
    to = to_number or os.getenv('WHATSAPP_TO', '')

    if not api_url or not token or not to:
        logger.warning('WhatsApp SKIPPED | config missing (API_URL/TOKEN/TO)')
        return False

    try:
        data = urllib.parse.urlencode({
            'token': token,
            'to': to,
            'body': message,
        }).encode('utf-8')

        req = urllib.request.Request(api_url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode('utf-8', errors='replace')[:200]
            ok = resp.status == 200

        if ok:
            logger.info('WhatsApp SENT | to=%s', to)
        else:
            logger.warning('WhatsApp FAILED | resp=%s', body)
        return ok
    except Exception as e:
        logger.warning('WhatsApp ERROR | %s', e)
        return False
