from django.core.management.base import BaseCommand
from agregator.models import Act, ScientificReport, TechReport
from agregator.processing.hash_utils import migrate_existing_hashes


class Command(BaseCommand):
    help = 'Миграция: добавляет хеши файлов к существующим записям'

    def handle(self, *args, **options):
        self.stdout.write('Начало миграции хешей файлов...')

        models = [Act, ScientificReport, TechReport]

        for model in models:
            self.stdout.write(f'Обработка {model.__name__}...')
            count = model.objects.count()
            self.stdout.write(f'Всего записей: {count}')

            migrate_existing_hashes(model)

            self.stdout.write(
                self.style.SUCCESS(f'Хеши для {model.__name__} успешно добавлены')
            )

        self.stdout.write(
            self.style.SUCCESS('Миграция хешей файлов завершена!')
        )
