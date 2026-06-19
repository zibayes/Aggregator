from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404

import cProfile
import functools
import os
from datetime import datetime
from pathlib import Path
import pstats

PROFILE_DIR = Path("profile_output")
PROFILE_DIR.mkdir(exist_ok=True)


def profiled(sort_by="cumulative", lines=80, enabled=True):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not enabled:
                return func(*args, **kwargs)

            profile = cProfile.Profile()
            result = profile.runcall(func, *args, **kwargs)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{func.__name__}_{ts}.prof"
            path = PROFILE_DIR / filename
            profile.dump_stats(str(path))

            txt_path = PROFILE_DIR / f"{func.__name__}_{ts}.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                stats = pstats.Stats(profile, stream=f)
                stats.strip_dirs().sort_stats(sort_by).print_stats(lines)

            return result

        return wrapper

    return decorator


def owner_or_admin_required(model, error_message="Вы не можете редактировать этот ресурс."):
    """
    Декоратор для проверки, является ли пользователь владельцем объекта или администратором.
    :param model: модель, к которой применяется декоратор.
    :param error_message: сообщение об ошибке, если доступ запрещен.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            obj = get_object_or_404(model,
                                    pk=kwargs['pk'])  # Здесь предполагается, что ID объекта передается как аргумент

            if hasattr(obj,
                       'user') and request.user == obj.user or request.user.is_superuser:  # Проверка на владельца или администратора
                return func(request, *args, **kwargs)
            return HttpResponseForbidden(error_message)

        return wrapper

    return decorator
