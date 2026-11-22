from django.db import migrations


class Migration(migrations.Migration):
    """La partie Entreprise est retirée du site. L'application ne garde que
    ses migrations, pour que les bases existantes se mettent à jour proprement."""

    dependencies = [
        ('businesses', '0002_business_twin'),
        ('resources', '0002_remove_business_consumption'),
    ]

    operations = [
        migrations.DeleteModel(name='HarvestSource'),
        migrations.DeleteModel(name='Equipment'),
        migrations.DeleteModel(name='Business'),
    ]
