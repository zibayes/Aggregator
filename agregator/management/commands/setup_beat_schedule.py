import json
from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule


class Command(BaseCommand):
    help = 'Идемпотентно создаёт/обновляет расписание Celery Beat в БД'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Настройка расписания Celery Beat...'))

        # Скачивание актов
        # --- 1. Создаём crontab: каждый час с 8 до 17, минута 0 ---
        crontab_schedule, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='8-17/2',
            day_of_week='1-6',
            day_of_month='*',
            month_of_year='*',
            timezone='Asia/Krasnoyarsk',  # поменяй на свой, если нужно
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✅ Создан crontab: {crontab_schedule}'))
        else:
            self.stdout.write(f'  ↻ Crontab уже существует: {crontab_schedule}')

        # --- 2. Создаём/обновляем задачу ---
        task_name = 'monitor-ookn-acts-hourly'
        task_args = [
            None,  # start_date
            None,  # end_date
            1,  # start_page
            2,  # end_page
            True,  # select_text
            False,  # select_enrich
            False,  # select_image
            False,  # select_coord
        ]
        task_kwargs = {'scheduled': True}

        periodic_task, created = PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                'task': 'agregator.processing.external_sources.external_sources_processing',
                'crontab': crontab_schedule,
                'args': json.dumps(task_args),
                'kwargs': json.dumps(task_kwargs),
                'enabled': True,
                'description': 'Автоматический мониторинг новых актов ГИКЭ на ООКН',
                # Если хочешь ограничить время выполнения (например, 55 минут):
                # 'expires': None,  # можно задать через поле expires в PeriodicTask, если оно есть
                'one_off': False,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✅ Создана задача: {task_name}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  ↻ Задача обновлена: {task_name}'))

        self.stdout.write(
            self.style.SUCCESS('\nГотово! Задача появится в админке /admin/django_celery_beat/periodictask/'))

        # Скачивание перечня ОАН
        # --- 1. Создаём crontab: каждый час с 8 до 17, минута 0 ---
        crontab_schedule, created = CrontabSchedule.objects.get_or_create(
            minute='20',
            hour='9',
            day_of_week='1-6',
            day_of_month='*',
            month_of_year='*',
            timezone='Asia/Krasnoyarsk',  # поменяй на свой, если нужно
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✅ Создан crontab: {crontab_schedule}'))
        else:
            self.stdout.write(f'  ↻ Crontab уже существует: {crontab_schedule}')

        # --- 2. Создаём/обновляем задачу ---
        task_name = 'monitor-ookn-oan-list-hourly'
        task_args = [
            False,  # orders_download
            False,  # use_local_register
            False,  # search_account_cards
        ]
        task_kwargs = {'scheduled': True}

        periodic_task, created = PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                'task': 'agregator.processing.external_sources.process_oan_list',
                'crontab': crontab_schedule,
                'args': json.dumps(task_args),
                'kwargs': json.dumps(task_kwargs),
                'enabled': True,
                'description': 'Автоматический мониторинг новых перечней ОАН на ООКН',
                # Если хочешь ограничить время выполнения (например, 55 минут):
                # 'expires': None,  # можно задать через поле expires в PeriodicTask, если оно есть
                'one_off': False,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✅ Создана задача: {task_name}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  ↻ Задача обновлена: {task_name}'))

        self.stdout.write(
            self.style.SUCCESS('\nГотово! Задача появится в админке /admin/django_celery_beat/periodictask/'))

        # Скачивание перечня ВОАН
        # --- 1. Создаём crontab: каждый час с 8 до 17, минута 0 ---
        crontab_schedule, created = CrontabSchedule.objects.get_or_create(
            minute='40',
            hour='9',
            day_of_week='1-6',
            day_of_month='*',
            month_of_year='*',
            timezone='Asia/Krasnoyarsk',  # поменяй на свой, если нужно
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✅ Создан crontab: {crontab_schedule}'))
        else:
            self.stdout.write(f'  ↻ Crontab уже существует: {crontab_schedule}')

        # --- 2. Создаём/обновляем задачу ---
        task_name = 'monitor-ookn-voan-list-hourly'
        task_args = [
            False,  # orders_download
            False,  # use_local_register
            False,  # search_account_cards
        ]
        task_kwargs = {'scheduled': True}

        periodic_task, created = PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                'task': 'agregator.processing.external_sources.process_voan_list',
                'crontab': crontab_schedule,
                'args': json.dumps(task_args),
                'kwargs': json.dumps(task_kwargs),
                'enabled': True,
                'description': 'Автоматический мониторинг новых перечней ВОАН на ООКН',
                # Если хочешь ограничить время выполнения (например, 55 минут):
                # 'expires': None,  # можно задать через поле expires в PeriodicTask, если оно есть
                'one_off': False,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✅ Создана задача: {task_name}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  ↻ Задача обновлена: {task_name}'))

        self.stdout.write(
            self.style.SUCCESS('\nГотово! Задача появится в админке /admin/django_celery_beat/periodictask/'))
