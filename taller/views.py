from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Cliente, Vehiculo, Cita, Orden
from .permissions import personal_required
from . import forms

def errores_operacion(form, error):
    if isinstance(error, ValidationError):
        for mensaje in error.messages:
            form.add_error(None, mensaje)
    else:
        form.add_error(None, 'No se pudo guardar. Recarga y revisa si la operación ya existe.')

@personal_required
def pendiente(request, **kwargs):
    return render(request, 'taller/pendiente.html')

@personal_required
def inicio(request):
    abiertas = Orden.objects.exclude(estado=Orden.Estado.ENTREGADO)
    hoy = timezone.localdate()
    return render(request, 'taller/inicio.html', {
        'abiertas': abiertas.count(),
        'en_reparacion': abiertas.filter(estado=Orden.Estado.REPARACION).count(),
        'listos': abiertas.filter(estado=Orden.Estado.LISTO).count(),
        'citas_hoy': Cita.objects.filter(fecha__date=hoy, estado='pendiente').count(),
        'ordenes': abiertas.select_related('vehiculo__cliente')[:6],
        'proximas': Cita.objects.filter(estado='pendiente', fecha__gte=timezone.now()
                    ).select_related('vehiculo__cliente')[:5],
        'hoy': hoy,
    })

@personal_required
def clientes(request):
    q = request.GET.get('q', '').strip()
    lista = Cliente.objects.filter(Q(nombre__icontains=q) | Q(telefono__icontains=q))
    return render(request, 'taller/clientes.html', {'clientes': lista, 'q': q})

@personal_required
def cliente_form(request, pk=None):
    cliente = get_object_or_404(Cliente, pk=pk) if pk else None
    form = forms.ClienteForm(request.POST or None, instance=cliente)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Ficha del cliente guardada.')
        return redirect('taller:clientes')
    return render(request, 'taller/formulario.html', {
        'form': form, 'titulo': 'Editar cliente' if cliente else 'Nuevo cliente',
        'ayuda': 'Datos de contacto para la atención del vehículo.',
        'volver': reverse('taller:clientes'),
    })

@personal_required
def vehiculos(request):
    q = request.GET.get('q', '').strip()
    lista = Vehiculo.objects.select_related('cliente').filter(
        Q(matricula__icontains=q) | Q(cliente__nombre__icontains=q))
    return render(request, 'taller/vehiculos.html', {'vehiculos': lista, 'q': q})

@personal_required
def vehiculo_nuevo(request):
    form = forms.VehiculoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
        except IntegrityError as error:
            errores_operacion(form, error)
        else:
            messages.success(request, 'Vehículo registrado.')
            return redirect('taller:vehiculos')
    return render(request, 'taller/formulario.html', {
        'form': form, 'titulo': 'Nuevo vehículo',
        'ayuda': 'Primero crea el cliente. La matrícula se guardará en mayúsculas.',
        'volver': reverse('taller:vehiculos'),
    })

@personal_required
def vehiculo_detalle(request, pk):
    vehiculo = get_object_or_404(Vehiculo.objects.select_related('cliente'), pk=pk)
    return render(request, 'taller/vehiculo_detalle.html', {
        'vehiculo': vehiculo, 'ordenes': vehiculo.ordenes.all(),
    })

from . import services

@personal_required
def reservas(request):
    estado = request.GET.get('estado', 'pendiente')
    lista = Cita.objects.select_related('vehiculo__cliente')
    if estado in Cita.Estado.values:
        lista = lista.filter(estado=estado)
    return render(request, 'taller/reservas.html', {
        'citas': lista, 'estados': Cita.Estado.choices, 'estado': estado,
    })

@personal_required
def reserva_nueva(request):
    form = forms.CitaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            services.reservar(**form.cleaned_data)
        except (ValidationError, IntegrityError, OperationalError) as error:
            errores_operacion(form, error)
        else:
            messages.success(request, 'Reserva creada. La recepción dispone de una hora.')
            return redirect('taller:reservas')
    return render(request, 'taller/formulario.html', {
        'form': form, 'titulo': 'Nueva reserva',
        'ayuda': 'Una recepción por franja de una hora. Primero registra el vehículo.',
        'volver': reverse('taller:reservas'),
    })

@personal_required
@require_POST
def reserva_cancelar(request, pk):
    get_object_or_404(Cita, pk=pk)
    try:
        services.cancelar_cita(pk)
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    except (IntegrityError, OperationalError):
        messages.error(request, 'No se pudo cancelar. Recarga la agenda e inténtalo de nuevo.')
    else:
        messages.success(request, 'Cita cancelada. La franja queda disponible.')
    return redirect('taller:reservas')

@personal_required
def checkin(request):
    cita_id = request.GET.get('cita')
    # El convertidor de ruta valida los pk; aquí validamos el parámetro de consulta.
    if cita_id and not cita_id.isdecimal():
        from django.http import Http404
        raise Http404('Cita no válida.')
    cita = get_object_or_404(Cita, pk=cita_id) if cita_id else None
    form = forms.CheckinForm(request.POST or None, cita=cita)
    if request.method == 'POST' and form.is_valid():
        try:
            orden = services.recibir(**form.cleaned_data,
                autor=request.user, cita_id=cita.pk if cita else None)
        except (ValidationError, IntegrityError, OperationalError) as error:
            errores_operacion(form, error)
        else:
            messages.success(request, f'Entrada registrada: {orden.referencia}.')
            return redirect('taller:orden_detalle', pk=orden.pk)
    return render(request, 'taller/formulario.html', {
        'form': form, 'titulo': 'Recepción · check-in',
        'ayuda': f'Cita {cita.pk}. Comprueba los datos de entrada.' if cita else
            'Entrada sin cita. Anota la avería y el estado visible del vehículo.',
        'volver': reverse('taller:reservas'),
    })

@personal_required
def ordenes(request):
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', 'abiertas')
    lista = Orden.objects.select_related('vehiculo__cliente').filter(
        Q(vehiculo__matricula__icontains=q) | Q(vehiculo__cliente__nombre__icontains=q))
    if estado == 'abiertas':
        lista = lista.exclude(estado='entregado')
    elif estado in Orden.Estado.values:
        lista = lista.filter(estado=estado)
    return render(request, 'taller/ordenes.html', {
        'ordenes': lista, 'q': q, 'estado': estado, 'estados': Orden.Estado.choices,
    })

@personal_required
def orden_detalle(request, pk):
    orden = get_object_or_404(Orden.objects.select_related('vehiculo__cliente'), pk=pk)
    diagnostico_form = forms.DiagnosticoForm(initial={'diagnostico': orden.diagnostico})
    nota_form = forms.NotaForm()
    linea_form = forms.LineaForm()
    accion = request.POST.get('accion') if request.method == 'POST' else None
    form = None
    if accion == 'diagnostico':
        form = diagnostico_form = forms.DiagnosticoForm(request.POST)
    elif accion == 'nota':
        form = nota_form = forms.NotaForm(request.POST)
    elif accion == 'linea':
        form = linea_form = forms.LineaForm(request.POST)
    if request.method == 'POST' and (accion == 'estado' or (form and form.is_valid())):
        try:
            if accion == 'diagnostico':
                services.diagnosticar(pk, form.cleaned_data['diagnostico'], request.user)
            elif accion == 'nota':
                services.anotar(pk, form.cleaned_data['texto'], request.user)
            elif accion == 'linea':
                services.agregar_linea(pk, form.cleaned_data, request.user)
            else:
                services.cambiar_estado(pk, request.POST.get('destino'), request.user)
        except (ValidationError, IntegrityError, OperationalError) as error:
            if form:
                errores_operacion(form, error)
            else:
                messages.error(request, ' '.join(error.messages) if isinstance(
                    error, ValidationError) else 'No se pudo guardar. Recarga la orden.')
        else:
            messages.success(request, 'Orden actualizada.')
            return redirect('taller:orden_detalle', pk=pk)
    elif request.method == 'POST' and accion not in {'diagnostico', 'nota', 'linea'}:
        messages.error(request, 'Acción no válida.')
    return render(request, 'taller/orden_detalle.html', {
        'orden': orden, 'diagnostico_form': diagnostico_form,
        'nota_form': nota_form, 'linea_form': linea_form,
    })

@personal_required
def checkout(request):
    lista = Orden.objects.filter(estado=Orden.Estado.LISTO).select_related('vehiculo__cliente')
    return render(request, 'taller/checkout.html', {'ordenes': lista})

@personal_required
def entregar(request, pk):
    orden = get_object_or_404(Orden.objects.select_related('vehiculo__cliente'), pk=pk)
    form = forms.CheckoutForm(request.POST or None, initial={'km_salida': orden.km_entrada})
    if request.method == 'POST' and form.is_valid():
        datos = form.cleaned_data.copy()
        datos.pop('confirmar')
        try:
            services.entregar(pk=pk, autor=request.user, **datos)
        except (ValidationError, IntegrityError, OperationalError) as error:
            errores_operacion(form, error)
        else:
            messages.success(request, 'Vehículo entregado. La orden queda cerrada.')
            return redirect('taller:resumen', pk=pk)
    return render(request, 'taller/entregar.html', {'orden': orden, 'form': form})

@personal_required
def resumen(request, pk):
    orden = get_object_or_404(Orden.objects.select_related('vehiculo__cliente')
                             .prefetch_related('lineas'), pk=pk)
    return render(request, 'taller/resumen.html', {'orden': orden})
