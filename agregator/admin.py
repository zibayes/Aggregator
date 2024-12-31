from django.contrib import admin
from .models import User, Role, UserRole, Supplement, Act, ScientificReport, TechReport
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

admin.site.register(User, UserAdmin)
admin.site.register(Role)
admin.site.register(UserRole)
admin.site.register(Supplement)
admin.site.register(Act)
admin.site.register(ScientificReport)
admin.site.register(TechReport)
