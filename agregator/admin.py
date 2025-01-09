from django.contrib import admin
from .models import User, Act, ScientificReport, TechReport
from django.contrib.auth.admin import UserAdmin

admin.site.register(User, UserAdmin)
admin.site.register(Act)
admin.site.register(ScientificReport)
admin.site.register(TechReport)
