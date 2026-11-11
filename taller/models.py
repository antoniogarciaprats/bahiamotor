from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

class Cliente(models.Model):
    nombre = models.CharField(max_length=120)
    telefono = models.CharField(max_length=20, validators=[
        RegexValidator(r'^\+?[0-9 ]{9,19}$', 'Usa entre 9 y 19 dígitos/espacios.')
    ])
    email = models.EmailField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Vehiculo(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT,
                                related_name='vehiculos')
    matricula = models.CharField(max_length=15, unique=True,
        validators=[RegexValidator(r'^[A-Z0-9-]{4,15}$',
                   'Usa 4-15 letras mayúsculas, números o guiones.')])
    marca = models.CharField(max_length=50)
    modelo = models.CharField(max_length=60)

    class Meta:
        ordering = ['matricula']

    def __str__(self):
        return f'{self.matricula} · {self.marca} {self.modelo} · {self.cliente}'

class Agenda(models.Model):
    # Una fila compartida para serializar las operaciones de agenda
    # en motores con bloqueo de filas. SQLite no ofrece ese bloqueo.
    nombre = models.CharField(max_length=50, default='Recepción')

class Cita(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        RECIBIDA = 'recibida', 'Recibida'
        CANCELADA = 'cancelada', 'Cancelada'

    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.PROTECT,
                                 related_name='citas')
    fecha = models.DateTimeField()
    motivo = models.CharField(max_length=250)
    estado = models.CharField(max_length=12, choices=Estado.choices,
                              default=Estado.PENDIENTE)

    class Meta:
        ordering = ['fecha']
        constraints = [models.UniqueConstraint(
            fields=['fecha'], condition=Q(estado='pendiente'),
            name='una_cita_pendiente_por_inicio')]

    def __str__(self):
        return f'Cita {self.pk} · {self.vehiculo.matricula}'

class Orden(models.Model):
    class Estado(models.TextChoices):
        RECIBIDO = 'recibido', 'Recibido'
        REPARACION = 'reparacion', 'En reparación'
        LISTO = 'listo', 'Listo para entregar'
        ENTREGADO = 'entregado', 'Entregado'

    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.PROTECT,
                                 related_name='ordenes')
    cita = models.OneToOneField(Cita, on_delete=models.PROTECT,
                                blank=True, null=True, related_name='orden')
    entrada = models.DateTimeField(default=timezone.now)
    salida = models.DateTimeField(blank=True, null=True)
    km_entrada = models.PositiveIntegerField('Kilómetros de entrada')
    km_salida = models.PositiveIntegerField('Kilómetros de salida',
                                           blank=True, null=True)
    motivo = models.TextField('Motivo y observaciones de recepción')
    diagnostico = models.TextField('Diagnóstico', blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices,
                              default=Estado.RECIBIDO)
    recogido_por = models.CharField(max_length=120, blank=True)
    observaciones_salida = models.TextField(blank=True)

    class Meta:
        ordering = ['-entrada']
        constraints = [
            models.UniqueConstraint(fields=['vehiculo'],
                condition=~Q(estado='entregado'), name='una_orden_abierta_por_vehiculo'),
            models.CheckConstraint(condition=Q(salida__isnull=True) |
                Q(salida__gte=F('entrada')), name='salida_posterior_entrada'),
            models.CheckConstraint(condition=Q(km_salida__isnull=True) |
                Q(km_salida__gte=F('km_entrada')), name='kilometros_no_retroceden'),
            models.CheckConstraint(condition=(
                Q(estado='entregado', salida__isnull=False, km_salida__isnull=False)
                & ~Q(recogido_por='')) | (
                ~Q(estado='entregado') & Q(salida__isnull=True, km_salida__isnull=True)),
                name='entrega_coherente'),
        ]

    @property
    def referencia(self):
        return f'OT-{self.pk:05d}'

    @property
    def total(self):
        return sum((linea.subtotal for linea in self.lineas.all()), Decimal('0.00'))

    def __str__(self):
        return f'{self.referencia} · {self.vehiculo.matricula}'

class LineaTrabajo(models.Model):
    orden = models.ForeignKey(Orden, on_delete=models.CASCADE,
                              related_name='lineas')
    descripcion = models.CharField(max_length=150)
    cantidad = models.DecimalField(max_digits=7, decimal_places=2,
                default=1, validators=[MinValueValidator(Decimal('0.01'))])
    precio = models.DecimalField('Precio unitario (€)', max_digits=9,
                decimal_places=2, validators=[MinValueValidator(Decimal('0'))])

    class Meta:
        ordering = ['pk']
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gt=0), name='cantidad_positiva'),
            models.CheckConstraint(condition=Q(precio__gte=0), name='precio_no_negativo'),
        ]

    @property
    def subtotal(self):
        return (self.cantidad * self.precio).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)

class Nota(models.Model):
    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name='notas')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    texto = models.TextField()
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada', '-pk']
