from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from .models import Act, ScientificReport, TechReport, OpenLists  # Импортируйте вашу модель


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

            if request.user == obj.user or request.user.is_superuser:  # Проверка на владельца или администратора
                return func(request, *args, **kwargs)
            return HttpResponseForbidden(error_message)

        return wrapper

    return decorator
