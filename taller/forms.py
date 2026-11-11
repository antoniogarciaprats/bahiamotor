from django import forms
from django.utils import timezone
from .models import Cliente, Vehiculo, Cita, Orden, LineaTrabajo

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'telefono', 'email']

class VehiculoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        fields = ['cliente', 'matricula', 'marca', 'modelo']

    def clean_matricula(self):
        return self.cleaned_data['matricula'].replace(' ', '').upper()

class CitaForm(forms.ModelForm):
    class Meta:
        model = Cita
        fields = ['vehiculo', 'fecha', 'motivo']
        widgets = {'fecha': forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'})}

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        if fecha <= timezone.now():
            raise forms.ValidationError('Elige una fecha futura.')
        return fecha

class CheckinForm(forms.Form):
    vehiculo = forms.ModelChoiceField(queryset=Vehiculo.objects.select_related('cliente'))
    km_entrada = forms.IntegerField(label='Kilómetros de entrada', min_value=0)
    motivo = forms.CharField(label='Motivo y estado del vehículo',
                             widget=forms.Textarea, max_length=3000)

    def __init__(self, *args, cita=None, **kwargs):
        super().__init__(*args, **kwargs)
        if cita:
            self.fields['vehiculo'].initial = cita.vehiculo
            self.fields['vehiculo'].disabled = True
            self.fields['motivo'].initial = cita.motivo

class DiagnosticoForm(forms.Form):
    diagnostico = forms.CharField(label='Diagnóstico', widget=forms.Textarea, max_length=5000)

class NotaForm(forms.Form):
    texto = forms.CharField(label='Nueva nota de atención', widget=forms.Textarea,
                           max_length=3000)

class LineaForm(forms.ModelForm):
    class Meta:
        model = LineaTrabajo
        fields = ['descripcion', 'cantidad', 'precio']

class CheckoutForm(forms.Form):
    km_salida = forms.IntegerField(label='Kilómetros de salida', min_value=0)
    recogido_por = forms.CharField(label='Persona que recoge el vehículo', max_length=120)
    observaciones_salida = forms.CharField(label='Observaciones de entrega',
        required=False, widget=forms.Textarea, max_length=3000)
    confirmar = forms.BooleanField(label='Confirmo la entrega del vehículo y las llaves')
