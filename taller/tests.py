from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import Cliente, Vehiculo, Cita, Orden, LineaTrabajo
from .forms import VehiculoForm, CheckinForm, CheckoutForm
from . import services

class FlujoTallerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            'recepcion', password='Clave-de-pruebas-938!', is_staff=True)
        cls.externo = get_user_model().objects.create_user('externo')
        cls.cliente = Cliente.objects.create(nombre='Cliente de prueba', telefono='600000000')
        cls.v = Vehiculo.objects.create(cliente=cls.cliente,
            matricula='TEST-01', marca='Seat', modelo='León')
        cls.v2 = Vehiculo.objects.create(cliente=cls.cliente,
            matricula='TEST-02', marca='Ford', modelo='Focus')

    def setUp(self):
        self.client.force_login(self.usuario)

    def cita(self, **cambios):
        datos = {'vehiculo': self.v, 'fecha': timezone.now()+timedelta(days=2),
                 'motivo': 'Revisión'}
        datos.update(cambios)
        return services.reservar(**datos)

    def recibir(self, **cambios):
        datos = {'vehiculo': self.v, 'km_entrada': 50000,
                 'motivo': 'Ruido al frenar', 'autor': self.usuario}
        datos.update(cambios)
        return services.recibir(**datos)

    def lista(self):
        orden = self.recibir()
        services.diagnosticar(orden.pk, 'Pastillas gastadas', self.usuario)
        services.agregar_linea(orden.pk, {'descripcion': 'Mano de obra',
            'cantidad': Decimal('1.50'), 'precio': Decimal('40.00')}, self.usuario)
        services.cambiar_estado(orden.pk, 'reparacion', self.usuario)
        services.cambiar_estado(orden.pk, 'listo', self.usuario)
        orden.refresh_from_db()
        return orden

    def entregar(self, orden, **cambios):
        datos = {'pk': orden.pk, 'km_salida': 50005, 'recogido_por': 'Cliente de prueba',
                 'observaciones_salida': 'Prueba de circulación realizada.', 'autor': self.usuario}
        datos.update(cambios)
        return services.entregar(**datos)

    def test_anonimo_redirige_a_acceso(self):
        self.client.logout()
        for nombre in ['inicio','clientes','vehiculos','reservas','checkin','ordenes','checkout']:
            with self.subTest(nombre=nombre):
                self.assertEqual(self.client.get(reverse('taller:'+nombre)).status_code, 302)

    def test_cuenta_externa_no_ve_clientes(self):
        self.client.force_login(self.externo)
        self.assertEqual(self.client.get(reverse('taller:clientes')).status_code, 403)

    def test_rutas_principales_responden(self):
        for nombre in ['inicio','clientes','vehiculos','reservas','reserva_nueva',
                       'checkin','ordenes','checkout','cliente_nuevo','vehiculo_nuevo']:
            with self.subTest(nombre=nombre):
                self.assertEqual(self.client.get(reverse('taller:'+nombre)).status_code, 200)

    def test_normaliza_matricula(self):
        form = VehiculoForm(data={'cliente':self.cliente.pk,'matricula':'1234 abc',
                                  'marca':'Seat','modelo':'Ibiza'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().matricula, '1234ABC')

    def test_matricula_duplicada_no_valida(self):
        form = VehiculoForm(data={'cliente':self.cliente.pk,'matricula':'test-01',
                                  'marca':'Seat','modelo':'Ibiza'})
        self.assertFalse(form.is_valid())

    def test_cita_pasada_rechazada(self):
        with self.assertRaises(ValidationError):
            self.cita(fecha=timezone.now()-timedelta(hours=1))

    def test_citas_solapadas_rechazadas(self):
        cita = self.cita()
        with self.assertRaises(ValidationError):
            self.cita(vehiculo=self.v2, fecha=cita.fecha+timedelta(minutes=30))

    def test_citas_adyacentes_admitidas(self):
        cita = self.cita()
        self.cita(vehiculo=self.v2, fecha=cita.fecha+timedelta(hours=1))
        self.assertEqual(Cita.objects.count(), 2)

    def test_cancelacion_libera_franja(self):
        cita = self.cita()
        services.cancelar_cita(cita.pk)
        self.cita(fecha=cita.fecha)
        self.assertEqual(Cita.objects.filter(estado='pendiente').count(), 1)

    def test_get_no_cancela(self):
        cita = self.cita()
        respuesta = self.client.get(reverse('taller:reserva_cancelar', args=[cita.pk]))
        self.assertEqual(respuesta.status_code, 405)
        cita.refresh_from_db()
        self.assertEqual(cita.estado, 'pendiente')

    def test_csrf_exigido(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        cita = self.cita()
        self.assertEqual(cliente.post(reverse('taller:reserva_cancelar',
            args=[cita.pk])).status_code, 403)

    def test_recepcion_con_cita(self):
        cita = self.cita()
        orden = self.recibir(cita_id=cita.pk)
        cita.refresh_from_db()
        self.assertEqual(cita.estado, 'recibida')
        self.assertEqual(orden.cita_id, cita.pk)
        self.assertEqual(orden.notas.count(), 1)

    def test_recepcion_cita_repetida_es_idempotente(self):
        cita = self.cita()
        primera = self.recibir(cita_id=cita.pk)
        segunda = self.recibir(cita_id=cita.pk)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(Orden.objects.count(), 1)

    def test_doble_entrada_sin_cita_rechazada(self):
        self.recibir()
        with self.assertRaises(ValidationError):
            self.recibir()

    def test_indice_impide_segunda_orden_abierta(self):
        self.recibir()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Orden.objects.create(vehiculo=self.v, km_entrada=50000, motivo='Duplicada')

    def test_cita_cancelada_no_se_recibe(self):
        cita = self.cita()
        services.cancelar_cita(cita.pk)
        with self.assertRaises(ValidationError):
            self.recibir(cita_id=cita.pk)

    def test_cita_de_otro_vehiculo_rechazada(self):
        cita = self.cita(vehiculo=self.v2)
        with self.assertRaises(ValidationError):
            self.recibir(cita_id=cita.pk)

    def test_cita_recibida_no_se_cancela(self):
        cita = self.cita()
        self.recibir(cita_id=cita.pk)
        with self.assertRaises(ValidationError):
            services.cancelar_cita(cita.pk)

    def test_kilometros_negativos_formulario(self):
        form = CheckinForm(data={'vehiculo':self.v.pk,'km_entrada':-1,'motivo':'Ruido'})
        self.assertFalse(form.is_valid())

    def test_parametro_cita_invalido_devuelve_404(self):
        self.assertEqual(self.client.get('/checkin/?cita=abc').status_code, 404)

    def test_no_saltar_directo_a_listo(self):
        orden = self.recibir()
        with self.assertRaises(ValidationError):
            services.cambiar_estado(orden.pk, 'listo', self.usuario)

    def test_no_finalizar_sin_trabajos(self):
        orden = self.recibir()
        services.cambiar_estado(orden.pk, 'reparacion', self.usuario)
        with self.assertRaises(ValidationError):
            services.cambiar_estado(orden.pk, 'listo', self.usuario)

    def test_no_finalizar_sin_diagnostico(self):
        orden = self.recibir()
        services.agregar_linea(orden.pk, {'descripcion':'Inspección',
            'cantidad':Decimal('1'),'precio':Decimal('0')}, self.usuario)
        services.cambiar_estado(orden.pk, 'reparacion', self.usuario)
        with self.assertRaises(ValidationError):
            services.cambiar_estado(orden.pk, 'listo', self.usuario)

    def test_cantidades_invalidas_no_se_guardan(self):
        orden = self.recibir()
        for cantidad, precio in [(Decimal('0'), Decimal('20')), (Decimal('1'), Decimal('-1'))]:
            with self.subTest(cantidad=cantidad, precio=precio), self.assertRaises(ValidationError):
                services.agregar_linea(orden.pk, {'descripcion':'Error',
                    'cantidad':cantidad,'precio':precio}, self.usuario)
        self.assertEqual(orden.lineas.count(), 0)

    def test_totales_decimales_redondeados_por_linea(self):
        orden = self.recibir()
        services.agregar_linea(orden.pk, {'descripcion':'Medición',
            'cantidad':Decimal('0.33'),'precio':Decimal('10.05')}, self.usuario)
        services.agregar_linea(orden.pk, {'descripcion':'Material',
            'cantidad':Decimal('1'),'precio':Decimal('0.10')}, self.usuario)
        self.assertEqual(orden.total, Decimal('3.42'))

    def test_listo_bloquea_nuevos_trabajos(self):
        orden = self.lista()
        with self.assertRaises(ValidationError):
            services.agregar_linea(orden.pk, {'descripcion':'Fuera de plazo',
                'cantidad':Decimal('1'),'precio':Decimal('1')}, self.usuario)

    def test_nota_guarda_autor_y_escapa_html(self):
        orden = self.recibir()
        services.anotar(orden.pk, '<script>alert(1)</script>', self.usuario)
        respuesta = self.client.get(reverse('taller:orden_detalle', args=[orden.pk]))
        self.assertContains(respuesta, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertEqual(orden.notas.first().autor, self.usuario)

    def test_entrega_completa(self):
        orden = self.entregar(self.lista())
        self.assertEqual(orden.estado, 'entregado')
        self.assertIsNotNone(orden.salida)
        self.assertEqual(orden.total, Decimal('60.00'))

    def test_no_entregar_antes_de_listo(self):
        with self.assertRaises(ValidationError):
            self.entregar(self.recibir())

    def test_entrega_no_retrocede_kilometros(self):
        orden = self.lista()
        with self.assertRaises(ValidationError):
            self.entregar(orden, km_salida=49999)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'listo')
        self.assertIsNone(orden.salida)

    def test_no_entregar_dos_veces(self):
        orden = self.entregar(self.lista())
        with self.assertRaises(ValidationError):
            self.entregar(orden)

    def test_entregado_bloquea_notas(self):
        orden = self.entregar(self.lista())
        with self.assertRaises(ValidationError):
            services.anotar(orden.pk, 'No debe entrar', self.usuario)

    def test_nueva_visita_mantiene_historial(self):
        orden = self.entregar(self.lista())
        nueva = self.recibir(km_entrada=50010)
        self.assertNotEqual(orden.pk, nueva.pk)
        self.assertEqual(self.v.ordenes.count(), 2)

    def test_nueva_visita_no_retrocede_km(self):
        self.entregar(self.lista())
        with self.assertRaises(ValidationError):
            self.recibir(km_entrada=49999)

    def test_entrega_requiere_confirmacion(self):
        form = CheckoutForm(data={'km_salida':50005,'recogido_por':'Cliente'})
        self.assertFalse(form.is_valid())

    def test_post_checkin_redirige_y_crea_orden(self):
        respuesta = self.client.post('/checkin/', {'vehiculo':self.v.pk,
            'km_entrada':50000,'motivo':'Mantenimiento'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Orden.objects.count(), 1)

    def test_post_checkout_y_resumen(self):
        orden = self.lista()
        respuesta = self.client.post(reverse('taller:entregar',args=[orden.pk]),
            {'km_salida':50005,'recogido_por':'Cliente','confirmar':'on',
             'observaciones_salida':'Todo revisado.'}, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'entregado')
        self.assertContains(respuesta, 'No es una factura')

    def test_detalle_historial_y_checkout_se_renderizan(self):
        orden = self.lista()
        for url in [reverse('taller:orden_detalle',args=[orden.pk]),
                    reverse('taller:vehiculo_detalle',args=[self.v.pk]),
                    reverse('taller:entregar',args=[orden.pk]),
                    reverse('taller:resumen',args=[orden.pk]), '/checkout/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
