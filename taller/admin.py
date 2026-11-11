from django.contrib import admin
from .models import Cliente, Vehiculo, Cita, Orden, LineaTrabajo, Nota

admin.site.site_header = 'Bahía Motor | Administración'
admin.site.site_title = 'Bahía Motor'

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'telefono', 'email']
    search_fields = ['nombre', 'telefono']

@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ['matricula', 'marca', 'modelo', 'cliente']
    search_fields = ['matricula', 'cliente__nombre']
    # El titular se fija al crear el vehículo para conservar el historial.
    def get_readonly_fields(self, request, obj=None):
        return ['cliente'] if obj else []

class ConsultaAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    def has_change_permission(self, request, obj=None):
        return False

admin.site.register([Cita, Orden, LineaTrabajo, Nota], ConsultaAdmin)
