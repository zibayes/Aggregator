from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User
from django.core.exceptions import ValidationError

'''
class UploadFileForm(forms.Form):
    file = forms.FileField(label='Выберите PDF файл', validators=[FileExtensionValidator(['pdf'])])
'''


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def __init__(self, *args, **kwargs):
        self.allowed_extensions = kwargs.pop('allowed_extensions', ['.pdf'])
        self.accepted_extensions = ','.join(self.allowed_extensions)
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        attrs['accept'] = self.accepted_extensions
        return super().get_context(name, value, attrs)


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        self.allowed_extensions = kwargs.pop('allowed_extensions', ['.pdf'])
        kwargs.setdefault("widget", MultipleFileInput(allowed_extensions=self.allowed_extensions))
        kwargs.setdefault("label", 'Выберите файлы для загрузки')
        self.max_file_size = kwargs.pop('max_file_size', 5 * 1024 * 1024)  # 5 MB по умолчанию
        kwargs.setdefault("help_text",
                          f"Допустимые расширения: {', '.join(self.allowed_extensions)}.")  # Максимальный размер файла: {self.max_file_size // (1024 * 1024)} МБ.")
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = []
            for d in data:
                if d:
                    self.validate_file_extension(d)
                result.append(single_file_clean(d, initial))
        else:
            if data:
                self.validate_file_extension(data)
            result = single_file_clean(data, initial)
        return result

    def validate_file_extension(self, file):
        # Получаем расширение файла
        extension = file.name[file.name.rfind('.'):].lower()
        if not any(extension.endswith(ext) for ext in self.allowed_extensions):
            raise ValidationError(
                f"Недопустимое расширение файла: {file.name}. Допустимые расширения: {', '.join(self.allowed_extensions)}.")

    def validate_file_size(self, file):
        if file.size > self.max_file_size:
            raise ValidationError(
                f"Размер файла {file.name} превышает максимальный размер {self.max_file_size // (1024 * 1024)} МБ.")


class UploadReportsForm(forms.Form):
    files = MultipleFileField(allowed_extensions=['.doc', '.docx', '.pdf'])


class UploadOpenListsForm(forms.Form):
    files = MultipleFileField(allowed_extensions=['.pdf', '.jpg', '.png', '.bmp', '.tiff'])


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['avatar']
