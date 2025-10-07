import os
import json
import hashlib
import time
import fcntl
import subprocess
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.conf import settings

# Путь к данным KodExplorer
User = settings.AUTH_USER_MODEL
KOD_DATA_DIR = '/kodexplorer_data/data'
SYSTEM_MEMBER_FILE = os.path.join(KOD_DATA_DIR, 'system', 'system_member.php')

# Шаблон для нового пользователя
USER_TEMPLATE = {
    "config": {
        "sizeMax": "2",
        "sizeUse": 1048576
    },
    "groupInfo": {"1": "write"},
    "status": 1,
    "lastLogin": "",
    "createTime": str(int(time.time()))
}

# Русские названия папок
FOLDER_MAPPING = {
    'document': 'Документы',
    'desktop': 'Рабочий стол',
    'pictures': 'Изображения',
    'music': 'Музыка'
}


def ensure_system_member_file():
    """Создает файл system_member.php, если его нет"""
    if not os.path.exists(SYSTEM_MEMBER_FILE):
        os.makedirs(os.path.dirname(SYSTEM_MEMBER_FILE), exist_ok=True)
        with open(SYSTEM_MEMBER_FILE, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(
                '<?php exit;?>{"1": {"name": "admin", "password": "21232f297a57a5a743894a0e4a801fc3", "role": "1", "path": "admin", "status": 1}}')
        print(f"✅ Создан файл {SYSTEM_MEMBER_FILE}")


def get_next_user_id():
    """Генерирует новый уникальный userID"""
    ensure_system_member_file()
    try:
        with open(SYSTEM_MEMBER_FILE, 'r') as f:
            content = f.read()
            json_str = content[content.find('{'):]
            data = json.loads(json_str)

        # Находим максимальный ID
        ids = [int(k) for k in data.keys()]
        next_id = max(ids) + 1
        print(f"ℹ️ Следующий ID пользователя: {next_id}")
        return next_id
    except Exception as e:
        print(f"❌ Ошибка чтения system_member.php: {str(e)}")
        return 1000  # Резервный ID


def reload_kodexplorer():
    """Принудительно перезапускает kodexplorer для обновления кэша"""
    try:
        # Проверяем, существует ли контейнер
        container_exists = subprocess.run(
            ["docker", "inspect", "kodexplorer"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        ).returncode == 0

        if container_exists:
            print("🔄 Перезапуск kodexplorer для обновления кэша пользователей...")
            subprocess.run(["docker", "restart", "kodexplorer"], check=True)
            print("✅ kodexplorer перезапущен")
        else:
            print("ℹ️ Контейнер kodexplorer не найден, пропускаем перезапуск")
    except Exception as e:
        print(f"⚠️ Ошибка перезапуска kodexplorer: {str(e)}")


def update_kod_user(user, password=None):
    """
    Создает/обновляет пользователя в KodExplorer с учетом прав Django
    """
    ensure_system_member_file()
    username = user.username
    is_admin = user.is_staff or user.is_superuser
    print(f"\n🔄 Обновление пользователя: {username}")
    print(f" - Админские права: {'ДА' if is_admin else 'НЕТ'}")

    # Читаем текущие данные
    try:
        with open(SYSTEM_MEMBER_FILE, 'r') as f:
            content = f.read()
            json_str = content[content.find('{'):]
            data = json.loads(json_str)
    except Exception as e:
        print(f"❌ Ошибка чтения system_member.php: {str(e)}")
        return False

    # Проверяем существование пользователя
    user_id = None
    for uid, user_data in data.items():
        if user_data.get('name') == username:
            user_id = uid
            print(f" - Найден пользователь с ID: {uid}")
            break

    # Обрабатываем создание/обновление
    if user_id:
        # Обновление существующего пользователя
        current_role = data[user_id].get("role", "2")
        target_role = "1" if is_admin else "2"
        is_role_changed = current_role != target_role
        print(f" - Текущая роль: {current_role}")
        print(f" - Целевая роль: {target_role}")
        print(f" - Изменение роли: {'ДА' if is_role_changed else 'НЕТ'}")

        # Обновляем данные
        data[user_id]["role"] = target_role
        if password:
            data[user_id]["password"] = hashlib.md5(password.encode()).hexdigest()
            print(" - Пароль обновлен")
        data[user_id]["status"] = 1  # Активен
    else:
        # Создание нового пользователя
        new_id = str(get_next_user_id())
        user_path = username.lower()
        new_user = {
            "userID": new_id,
            "name": username,
            "path": user_path,
            "role": "1" if is_admin else "2",
            **USER_TEMPLATE
        }
        if password:
            new_user["password"] = hashlib.md5(password.encode()).hexdigest()
        data[new_id] = new_user
        print(f" - Создан новый пользователь с ID: {new_id}")
        user_id = new_id

    # Записываем обновленные данные
    try:
        with open(SYSTEM_MEMBER_FILE, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write('<?php exit;?>' + json.dumps(data, indent=4))
        print("✅ system_member.php успешно обновлен")
    except Exception as e:
        print(f"❌ Ошибка записи system_member.php: {str(e)}")
        return False

    # Обрабатываем папки пользователя
    user_dir = os.path.join(KOD_DATA_DIR, 'User', username)
    print(f" - Папка пользователя: {user_dir}")

    try:
        # Создаем структуру папок
        os.makedirs(user_dir, exist_ok=True)
        print(" - Базовая папка создана")

        # Создаем русскоязычные папки
        for eng_name, rus_name in FOLDER_MAPPING.items():
            folder_path = os.path.join(user_dir, rus_name)
            os.makedirs(folder_path, exist_ok=True)
            print(f"   - Создана папка: {rus_name}")

        # Устанавливаем права
        for root, dirs, files in os.walk(user_dir):
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    os.chmod(dir_path, 0o775)
                    os.chown(dir_path, 100, 101)  # nginx
                    print(f"   - Права установлены для: {dir_path}")
                except Exception as e:
                    print(f"   ⚠️ Ошибка установки прав для {dir_path}: {str(e)}")

        # Конфигурация
        config_dir = os.path.join(user_dir, 'home', 'config')
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, 'setting.json'), 'w') as f:
            f.write(
                '''{"listType": "icon","listSortField": "name","listSortOrder": "up","fileIconSize": "80","animateOpen": "1","soundOpen": "0","theme": "win10","wall": "8","fileRepeat": "replace","recycleOpen": "1","resizeConfig": "{\"filename\":250,\"filetype\":80,\"filesize\":80,\"filetime\":215,\"editorTreeWidth\":200,\"explorerTreeWidth\":200}"}''')

        print("✅ Структура папок пользователя создана")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания структуры папок: {str(e)}")
        return False


def delete_kod_user(username):
    """Полностью удаляет пользователя из KodExplorer"""
    print(f"\n🗑️ Удаление пользователя: {username}")

    if not os.path.exists(SYSTEM_MEMBER_FILE):
        print(f"❌ system_member.php не существует: {SYSTEM_MEMBER_FILE}")
        return False

    try:
        # Читаем текущие данные
        with open(SYSTEM_MEMBER_FILE, 'r') as f:
            content = f.read()
            json_str = content[content.find('{'):]
            data = json.loads(json_str)

        # Ищем пользователя
        user_id = None
        for uid, user_data in data.items():
            if user_data.get('name') == username:
                user_id = uid
                print(f" - Найден пользователь с ID: {uid}")
                break

        if not user_id:
            print(f"ℹ️ Пользователь {username} не найден в system_member.php")
            return False

        # Удаляем пользователя из данных
        deleted_user = data.pop(user_id)
        print(f" - Пользователь удален из данных: {deleted_user}")

        # Записываем обновленные данные
        with open(SYSTEM_MEMBER_FILE, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write('<?php exit;?>' + json.dumps(data, indent=4))
        print("✅ system_member.php обновлен")

        # Удаляем папку пользователя
        user_dir = os.path.join(KOD_DATA_DIR, 'User', username)
        if os.path.exists(user_dir):
            import shutil
            shutil.rmtree(user_dir)
            print(f"✅ Папка пользователя удалена: {user_dir}")
        else:
            print(f"ℹ️ Папка пользователя не существует: {user_dir}")

        return True
    except Exception as e:
        print(f"❌ Ошибка удаления пользователя: {str(e)}")
        return False


# === Сигналы Django ===

# Хранение пароля при регистрации
@receiver(pre_save, sender=User)
def store_raw_password(sender, instance, **kwargs):
    if not instance.pk:  # Новый пользователь
        instance._raw_password = instance.password
        print(f"ℹ️ Сохранен raw пароль для нового пользователя: {instance.username}")


# Синхронизация при создании пользователя
@receiver(post_save, sender=User)
def sync_kod_user(sender, instance, created, **kwargs):
    print(f"🔄 Обработка пользователя: {instance.username}, created={created}")

    if created:
        # Создание нового пользователя
        print(f"✅ Создан новый пользователь: {instance.username}")
        raw_password = getattr(instance, '_raw_password', 'password')
        if update_kod_user(instance, raw_password):
            reload_kodexplorer()
    else:
        # Обновление существующего пользователя
        print(f"📝 Обновление пользователя: {instance.username}")
        if hasattr(instance, '_password_changed') and instance._password_changed:
            print(f"🔑 Обновление пароля для: {instance.username}")
            if update_kod_user(instance, instance.password):
                del instance._password_changed
                reload_kodexplorer()
        else:
            # Обновление других данных (is_staff, is_superuser)
            print(f"⚙️ Обновление прав для: {instance.username}")
            if update_kod_user(instance):
                reload_kodexplorer()


# Обработка смены пароля
@receiver(user_logged_in)
def handle_password_change(sender, user, request, **kwargs):
    # Проверяем, если пароль только что изменен
    if request.session.get('password_changed'):
        user._password_changed = True
        user.save()
        del request.session['password_changed']


print("✅ Сигналы Django ЗАГРУЖЕНЫ!")


@receiver(post_delete, sender=User)
def handle_user_deletion(sender, instance, **kwargs):
    print(f"\n❌ Удаление пользователя: {instance.username}")
    if delete_kod_user(instance.username):
        reload_kodexplorer()  # Принудительно перезапускаем KodExplorer
        print(f"✅ Пользователь {instance.username} удален из KodExplorer")
    else:
        print(f"❌ Пользователь {instance.username} НЕ удален из KodExplorer")
