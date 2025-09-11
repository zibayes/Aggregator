from django.core.management.base import BaseCommand
from agregator.models import (Act, ScientificReport, TechReport, OpenLists,
                              ObjectAccountCard, ArchaeologicalHeritageSite,
                              IdentifiedArchaeologicalHeritageSite, CommercialOffers, GeoObject)
from agregator.processing.links import create_link_for_instance


class Command(BaseCommand):
    help = 'Create .url links for existing objects in KodExplorer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            help='Specific model to process (e.g., Act, ScientificReport)'
        )

    def handle(self, *args, **options):
        models = [Act, ScientificReport, TechReport, OpenLists,
                  ObjectAccountCard, ArchaeologicalHeritageSite,
                  IdentifiedArchaeologicalHeritageSite, CommercialOffers, GeoObject]

        # Если указана конкретная модель
        if options['model']:
            model_name = options['model']
            models = [model for model in models if model.__name__ == model_name]
            if not models:
                self.stderr.write(f"Model {model_name} not found!")
                return

        total_created = 0
        for model in models:
            self.stdout.write(f"Processing {model.__name__}...")
            model_count = 0

            for obj in model.objects.all():
                result = create_link_for_instance(obj)
                if result:
                    model_count += 1
                    total_created += 1
                    if model_count % 10 == 0:  # Вывод каждые 10 объектов
                        self.stdout.write(f"  Created {model_count} links...")

            self.stdout.write(
                self.style.SUCCESS(f"✓ {model.__name__}: {model_count} links created")
            )

        self.stdout.write(
            self.style.SUCCESS(f"\n🎉 Total: {total_created} links created successfully!")
        )
