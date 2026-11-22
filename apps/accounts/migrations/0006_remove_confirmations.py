from django.db import migrations


def everyone_confirmed(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(email_verified=False).update(email_verified=True)


class Migration(migrations.Migration):
    """La confirmation par e-mail et par SMS est retirée : tous les comptes sont actifs."""

    dependencies = [
        ('accounts', '0005_phone_sms_code'),
    ]

    operations = [
        migrations.RunPython(everyone_confirmed, migrations.RunPython.noop),
        migrations.DeleteModel(name='PhoneCode'),
        migrations.RemoveField(model_name='user', name='phone_verified'),
    ]
