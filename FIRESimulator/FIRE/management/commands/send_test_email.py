import socket

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Send a test email to verify the email configuration: manage.py send_test_email you@example.com"

    def add_arguments(self, parser):
        parser.add_argument('recipient')

    def handle(self, *args, **options):
        backend = settings.EMAIL_BACKEND.rsplit('.', 2)[-2]
        self.stdout.write(f"Backend: {backend}; from: {settings.DEFAULT_FROM_EMAIL}; host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        if backend == 'console':
            self.stdout.write(self.style.WARNING(
                "EMAIL_HOST_PASSWORD is not set, so the message will only print below instead of being sent."))
        try:
            sent = send_mail('FI Planner test email', 'Your FI Planner email settings are working.',
                             settings.DEFAULT_FROM_EMAIL, [options['recipient']])
        except socket.gaierror as exc:
            raise CommandError(
                f"Could not resolve SMTP host '{settings.EMAIL_HOST}:{settings.EMAIL_PORT}' ({exc}). "
                "Check that EMAIL_HOST is unset or 'smtp.gmail.com' (not your email address) and that this "
                "machine/VPN/proxy can reach smtp.gmail.com on port 587.")
        except Exception as exc:
            raise CommandError(f"Sending failed: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} message(s) to {options['recipient']}."))
