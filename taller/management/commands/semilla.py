from django.core.management.base import BaseCommand
from taller.models import Cliente, Vehiculo

class Command(BaseCommand):
    help = 'Crea clientes y vehículos ficticios; se puede repetir.'
    def handle(self, *args, **options):
        datos = [
            ('Cliente Demo Mar', '600000001', 'DEMO-001', 'Seat', 'León'),
            ('Cliente Demo Sal', '600000002', 'DEMO-002', 'Renault', 'Clio'),
            ('Cliente Demo Luz', '600000003', 'DEMO-003', 'Toyota', 'Yaris'),
            ('Cliente Demo Sol', '600000004', 'DEMO-004', 'Ford', 'Focus'),
        ]
        for nombre, telefono, matricula, marca, modelo in datos:
            cliente, _ = Cliente.objects.get_or_create(
                nombre=nombre, defaults={'telefono': telefono,
                'email': 'demo@example.invalid'})
            Vehiculo.objects.get_or_create(matricula=matricula,
                defaults={'cliente': cliente, 'marca': marca, 'modelo': modelo})
        self.stdout.write(self.style.SUCCESS('Datos ficticios preparados.'))
