from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from taller.models import Vehiculo, Orden, Cita
from taller import services

class Command(BaseCommand):
    help = 'Añade casos ficticios de recepción, reparación, entrega y agenda.'
    @transaction.atomic
    def handle(self, *args, **options):
        autor = get_user_model().objects.filter(is_staff=True, is_active=True).first()
        if not autor:
            raise CommandError('Crea antes un usuario con createsuperuser.')
        call_command('semilla')
        if Orden.objects.exists() or Cita.objects.exists():
            self.stdout.write('Ya hay actividad. No se ha duplicado la demostración.')
            return
        for i, v in enumerate(Vehiculo.objects.filter(matricula__startswith='DEMO-')):
            orden = services.recibir(vehiculo=v, km_entrada=60000+i*1000,
                motivo='Revisión de mantenimiento. Datos ficticios.', autor=autor)
            if i >= 1:
                services.diagnosticar(orden.pk, 'Sustitución de aceite y filtro.', autor)
                services.agregar_linea(orden.pk, {'descripcion': 'Aceite y filtro',
                    'cantidad': Decimal('1.00'), 'precio': Decimal('65.00')}, autor)
                services.cambiar_estado(orden.pk, 'reparacion', autor)
            if i >= 2:
                services.cambiar_estado(orden.pk, 'listo', autor)
            if i >= 3:
                services.entregar(pk=orden.pk, km_salida=orden.km_entrada+2,
                    recogido_por=v.cliente.nombre, observaciones_salida='Entrega de ejemplo.',
                    autor=autor)
            fecha = timezone.now().replace(minute=0, second=0, microsecond=0)
            services.reservar(vehiculo=v, fecha=fecha+timedelta(days=1,hours=i),
                motivo='Cita de demostración')
        self.stdout.write(self.style.SUCCESS('Demostración completa preparada.'))
