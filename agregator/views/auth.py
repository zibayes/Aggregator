from django.contrib.auth import login, authenticate
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from agregator.forms import UserRegisterForm
from agregator.models import User
from agregator.views.utils import validate_email
from agregator.kodexplorer_users_sync import update_kod_user


def user_register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('profile')
        else:
            return render(request, 'register.html', {'form': form, 'error': 'Неверные учетные данные'})
    else:
        form = UserRegisterForm()
    return render(request, 'register.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if not username or not password:
            return render(request, 'login.html', {'error': 'Указаны не все учетные данные'})
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('profile')
        else:
            return render(request, 'login.html', {'error': 'Неверные учетные данные'})
    return render(request, 'login.html')


@login_required
def custom_logout(request):
    logout(request)
    return redirect('index')


@login_required
def profile(request):
    return render(request, 'profile.html', {'user_to_show': request.user})


@login_required
def settings(request):
    if request.method == 'POST':
        user = request.user
        if 'avatar' in request.FILES.keys():
            user.avatar = request.FILES['avatar']
        fields = ['first_name', 'last_name', 'username', 'email']
        for field in fields:
            value = request.POST.get(field)
            if value is not None and value != '':
                if field == 'username' and User.objects.filter(username=value).exclude(id=user.id).exists():
                    return render(request, 'settings.html', {'error': f'Такое имя пользователя уже занято: {value}'})
                elif field == 'email':
                    if not validate_email(value):
                        return render(request, 'settings.html',
                                      {'error': f'Некорректный email'})
                    elif User.objects.filter(email=value).exclude(id=user.id).exists():
                        return render(request, 'settings.html',
                                      {'error': f'Такой email уже занят: {value}'})
                setattr(user, field, value)

        password = request.POST.get('password')
        if password:
            user.set_password(password)  # Хешируйте новый пароль
            update_session_auth_hash(request, user)  # Убедитесь, что сеанс остается активным
            update_kod_user(
                request.user.username,
                password
            )
        user.save()
        messages.success(request, 'Профиль успешно обновлен.')
        return redirect('profile')  # Перенаправление на страницу профиля

    return render(request, 'settings.html')


def index(request):
    return render(request, 'index.html')


def users(request, pk):
    user = get_object_or_404(User, id=pk)
    return render(request, 'profile.html', {'user_to_show': user})
