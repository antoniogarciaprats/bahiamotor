from django.urls import path
from . import views
app_name = 'taller'
urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('clientes/', views.clientes, name='clientes'),
    path('clientes/nuevo/', views.cliente_form, name='cliente_nuevo'),
    path('clientes/<int:pk>/editar/', views.cliente_form, name='cliente_editar'),
    path('vehiculos/', views.vehiculos, name='vehiculos'),
    path('vehiculos/nuevo/', views.vehiculo_nuevo, name='vehiculo_nuevo'),
    path('vehiculos/<int:pk>/', views.vehiculo_detalle, name='vehiculo_detalle'),
    path('reservas/', views.reservas, name='reservas'),
    path('reservas/nueva/', views.reserva_nueva, name='reserva_nueva'),
    path('reservas/<int:pk>/cancelar/', views.reserva_cancelar, name='reserva_cancelar'),
    path('checkin/', views.checkin, name='checkin'),
    path('ordenes/', views.ordenes, name='ordenes'),
    path('ordenes/<int:pk>/', views.orden_detalle, name='orden_detalle'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/<int:pk>/', views.entregar, name='entregar'),
    path('ordenes/<int:pk>/resumen/', views.resumen, name='resumen'),
]
