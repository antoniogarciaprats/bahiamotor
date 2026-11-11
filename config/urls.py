from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('acceso/', LoginView.as_view(
        template_name='registration/login.html'), name='login'),
    path('salir/', LogoutView.as_view(), name='logout'),
    path('', include('taller.urls')),
]
