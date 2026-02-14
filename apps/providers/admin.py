from django.contrib import admin

from .models import Provider


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    """Admin configuration for Provider model."""
    
    list_display = [
        'name', 'priority', 'is_active', 'adapter_path', 'created_at'
    ]
    list_filter = ['is_active']
    search_fields = ['name', 'adapter_path']
    ordering = ['priority', 'name']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['priority', 'is_active']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'adapter_path')
        }),
        ('Configuration', {
            'fields': ('priority', 'is_active', 'config'),
            'description': 'Configure provider priority and activation status.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make adapter_path readonly after creation."""
        if obj:
            return self.readonly_fields + ['adapter_path']
        return self.readonly_fields
