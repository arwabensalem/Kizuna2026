from django.db import migrations


class Migration(migrations.Migration):
    """La partie Entreprise est retirée : plus de relevés de consommation d'entreprise."""

    dependencies = [
        ('resources', '0001_initial'),
    ]

    operations = [
        migrations.DeleteModel(name='ResourceConsumption'),
    ]
