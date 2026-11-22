from django.core.management.base import BaseCommand

from apps.ai_engine.training import train_all


class Command(BaseCommand):
    help = (
        'Train the water, energy, farm water, crop stress, and anomaly '
        'models on the synthetic demo datasets and save them under media/models/.'
    )

    def handle(self, *args, **options):
        report = train_all()
        self.stdout.write(report['label'])
        self.stdout.write(f"seed {report['seed']}, rows {report['rows']}")
        for name, task in report['tasks'].items():
            self.stdout.write(f"{name} ({task['model']}): {task['validation']}")
        self.stdout.write(self.style.SUCCESS('Saved demo models.'))
