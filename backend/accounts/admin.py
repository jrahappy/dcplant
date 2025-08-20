from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Organization, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_organization', 'get_role')
    
    def get_organization(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.organization.name
        return '-'
    get_organization.short_description = 'Organization'
    
    def get_role(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.get_role_display()
        return '-'
    get_role.short_description = 'Role'


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'org_type', 'email', 'phone', 'is_active', 'created_at')
    list_filter = ('org_type', 'is_active', 'created_at')
    search_fields = ('name', 'email')
    ordering = ('name',)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
