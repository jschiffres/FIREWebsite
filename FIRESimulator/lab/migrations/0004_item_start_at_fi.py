from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lab', '0003_item_priority_item_savings_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='start_at_fi',
            field=models.BooleanField(default=False),
        ),
    ]
