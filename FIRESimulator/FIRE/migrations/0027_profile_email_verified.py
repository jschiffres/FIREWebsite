from django.conf import settings
from django.db import migrations, models


def grandfather_existing_users(apps, schema_editor):
    """Accounts that predate email verification are treated as verified."""
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    Profile = apps.get_model('FIRE', 'Profile')
    Profile.objects.update(email_verified=True)
    existing = set(Profile.objects.values_list('user_id', flat=True))
    Profile.objects.bulk_create([
        Profile(user_id=pk, email_verified=True)
        for pk in User.objects.exclude(pk__in=existing).values_list('pk', flat=True)
    ])


class Migration(migrations.Migration):

    dependencies = [
        ('FIRE', '0026_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(grandfather_existing_users, migrations.RunPython.noop),
    ]
