import logging
import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

SUPPORT_EMAIL = 'hello@fiplanner.app'


def _site_url():
    return getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')


def _to_text(html):
    html = re.sub(r'(?is)<(head|style).*?</\1>', '', html)
    html = re.sub(r'(?is)<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', lambda m: f'{strip_tags(m.group(2)).strip()} ({m.group(1)})' if not m.group(1).startswith('mailto:') else strip_tags(m.group(2)), html)
    html = re.sub(r'(?i)<br\s*/?>|</p>|</li>|</h1>', '\n', html)
    text = strip_tags(html)
    return re.sub(r'\n\s*\n+', '\n\n', re.sub(r'[ \t]+', ' ', text)).strip() + '\n'


def send_templated_email(subject, template, user, extra=None):
    """Send an HTML email with a plain-text alternative. Never raises; returns success."""
    if not getattr(user, 'email', ''):
        return False
    context = {
        'user': user,
        'site_url': _site_url(),
        'support_email': SUPPORT_EMAIL,
        'landing_url': _site_url() + reverse('userplans'),
        'account_url': _site_url() + reverse('myaccount'),
    }
    context.update(extra or {})
    try:
        html = render_to_string(template, context)
        message = EmailMultiAlternatives(subject, _to_text(html), settings.DEFAULT_FROM_EMAIL, [user.email])
        message.attach_alternative(html, 'text/html')
        message.send()
    except Exception:
        logger.exception('Failed to send %s email', template)
        return False
    return True


def welcome_email(user):
    return send_templated_email('Welcome to FI Planner', 'emails/welcome_email.html', user)


def premium_welcome_email(user):
    return send_templated_email('Welcome to FI Planner Premium', 'emails/premium_welcome.html', user)


def premium_ended_email(user):
    return send_templated_email('Your FI Planner Premium subscription has ended', 'emails/premium_ended.html', user)


def payment_failed_email(user):
    return send_templated_email('Action needed: payment failed for FI Planner Premium', 'emails/payment_failed.html', user)
