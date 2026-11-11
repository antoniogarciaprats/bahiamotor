from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Agenda, Cita, Vehiculo, Orden, LineaTrabajo, Nota

def bloquear_agenda():
    Agenda.objects.get_or_create(pk=1)
    return Agenda.objects.select_for_update().get(pk=1)

@transaction.atomic
def reservar(*, vehiculo, fecha, motivo):
    bloquear_agenda()
    if fecha <= timezone.now():
        raise ValidationError('La cita debe ser futura.')
    # Regla de este taller ficticio: una recepción por hora, sin horario fijo.
    if Cita.objects.filter(estado=Cita.Estado.PENDIENTE,
        fecha__gt=fecha - timedelta(hours=1),
        fecha__lt=fecha + timedelta(hours=1)).exists():
        raise ValidationError('La recepción ya está ocupada en esa franja de una hora.')
    cita = Cita(vehiculo=vehiculo, fecha=fecha, motivo=motivo)
    cita.full_clean()
    cita.save()
    return cita

@transaction.atomic
def cancelar_cita(pk):
    bloquear_agenda()
    cita = Cita.objects.select_for_update().get(pk=pk)
    if cita.estado != Cita.Estado.PENDIENTE:
        raise ValidationError('Solo se pueden cancelar citas pendientes.')
    cita.estado = Cita.Estado.CANCELADA
    cita.save(update_fields=['estado'])

def registrar_nota(orden, autor, texto):
    Nota.objects.create(orden=orden, autor=autor, texto=texto)

@transaction.atomic
def recibir(*, vehiculo, km_entrada, motivo, autor, cita_id=None):
    bloquear_agenda()
    # Se bloquea también el vehículo para coordinar recepciones concurrentes.
    vehiculo = Vehiculo.objects.select_for_update().get(pk=vehiculo.pk)
    cita = None
    if cita_id:
        cita = Cita.objects.select_for_update().get(pk=cita_id)
        if cita.vehiculo_id != vehiculo.pk:
            raise ValidationError('La cita corresponde a otro vehículo.')
        # Repetir la misma recepción devuelve la orden que ya se creó.
        if cita.estado == Cita.Estado.RECIBIDA:
            return Orden.objects.get(cita=cita)
        if cita.estado != Cita.Estado.PENDIENTE:
            raise ValidationError('La cita no está pendiente.')
    if Orden.objects.filter(vehiculo=vehiculo).exclude(estado='entregado').exists():
        raise ValidationError('Este vehículo ya tiene una orden abierta.')
    ultima = Orden.objects.filter(vehiculo=vehiculo, estado='entregado').order_by('-salida').first()
    if ultima and km_entrada < ultima.km_salida:
        raise ValidationError('Los kilómetros son menores que en la última entrega.')
    orden = Orden(vehiculo=vehiculo, cita=cita,
                  km_entrada=km_entrada, motivo=motivo)
    orden.full_clean()
    orden.save()
    if cita:
        cita.estado = Cita.Estado.RECIBIDA
        cita.save(update_fields=['estado'])
    registrar_nota(orden, autor, 'Vehículo recibido en el taller.')
    return orden

def orden_editable(pk):
    orden = Orden.objects.select_for_update().get(pk=pk)
    if orden.estado in (Orden.Estado.LISTO, Orden.Estado.ENTREGADO):
        raise ValidationError('Los trabajos y el diagnóstico ya están cerrados.')
    return orden

@transaction.atomic
def diagnosticar(pk, texto, autor):
    orden = orden_editable(pk)
    texto = texto.strip()
    if not texto:
        raise ValidationError('Escribe el diagnóstico.')
    orden.diagnostico = texto
    orden.full_clean()
    orden.save(update_fields=['diagnostico'])
    registrar_nota(orden, autor, 'Diagnóstico actualizado: ' + texto)

@transaction.atomic
def anotar(pk, texto, autor):
    orden = Orden.objects.select_for_update().get(pk=pk)
    if orden.estado == Orden.Estado.ENTREGADO:
        raise ValidationError('La orden está entregada; su historial queda cerrado.')
    texto = texto.strip()
    if not texto:
        raise ValidationError('Escribe una nota.')
    registrar_nota(orden, autor, texto)

@transaction.atomic
def agregar_linea(pk, datos, autor):
    orden = orden_editable(pk)
    linea = LineaTrabajo(orden=orden, **datos)
    linea.full_clean()
    linea.save()
    registrar_nota(orden, autor, f'Trabajo añadido: {linea.descripcion}.')
    return linea

@transaction.atomic
def cambiar_estado(pk, destino, autor):
    orden = Orden.objects.select_for_update().get(pk=pk)
    siguientes = {Orden.Estado.RECIBIDO: Orden.Estado.REPARACION,
                  Orden.Estado.REPARACION: Orden.Estado.LISTO}
    if siguientes.get(orden.estado) != destino:
        raise ValidationError('El cambio de estado no sigue el flujo permitido.')
    if destino == Orden.Estado.LISTO and (
        not orden.diagnostico.strip() or not orden.lineas.exists()):
        raise ValidationError('Añade el diagnóstico y al menos un trabajo antes de terminar.')
    orden.estado = destino
    orden.full_clean()
    orden.save(update_fields=['estado'])
    registrar_nota(orden, autor, 'Estado: ' + orden.get_estado_display())

@transaction.atomic
def entregar(*, pk, km_salida, recogido_por, observaciones_salida, autor):
    orden = Orden.objects.select_for_update().get(pk=pk)
    if orden.estado != Orden.Estado.LISTO:
        raise ValidationError('Solo se puede entregar una orden lista.')
    orden.km_salida = km_salida
    orden.recogido_por = recogido_por.strip()
    orden.observaciones_salida = observaciones_salida.strip()
    orden.salida = timezone.now()
    orden.estado = Orden.Estado.ENTREGADO
    orden.full_clean()
    orden.save(update_fields=['km_salida', 'recogido_por',
        'observaciones_salida', 'salida', 'estado'])
    registrar_nota(orden, autor, 'Vehículo y llaves entregados a ' + orden.recogido_por + '.')
    return orden
