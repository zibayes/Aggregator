from django import forms
from django.core.validators import FileExtensionValidator 

'''
class UploadFileForm(forms.Form):
    file = forms.FileField(label='Выберите PDF файл', validators=[FileExtensionValidator(['pdf'])])
'''
    
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        kwargs.setdefault("label", 'Выберите PDF файлы')
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class UploadFileForm(forms.Form):
    files = MultipleFileField()