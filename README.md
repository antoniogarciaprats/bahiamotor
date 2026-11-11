# Bahía Motor · Taller mecánico

Aplicación didáctica original para un taller ficticio de El Puerto de Santa María.
Python + Django 5.2 LTS + SQLite + HTML5/CSS3. Sin Node, CDN ni servicios externos.

## Arranque en PyCharm
Abre esta carpeta (la que contiene manage.py), crea/selecciona un entorno .venv
con Python 3.12, 3.13 o 3.14 y abre la terminal integrada.

```text
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py demo_taller
python manage.py runserver
```

Entra en http://127.0.0.1:8000/ e inicia sesión con tu propio superusuario.
No se incluye ninguna contraseña. demo_taller es opcional y solo crea casos ficticios;
si ya existen citas u órdenes no vuelve a crear actividad.
Para empezar solo con clientes y vehículos: python manage.py semilla.
No contactes con los teléfonos de demostración.

## Rutas
/ inicio; /reservas/ agenda; /checkin/ recepción; /ordenes/ seguimiento;
/checkout/ entregas; /clientes/ fichas; /vehiculos/ historial; /admin/ administración.

## Pruebas y copia de datos
python manage.py check
python manage.py test taller
python manage.py makemigrations --check --dry-run
python manage.py copia_bd

requirements.txt mantiene la serie 5.2 y permite correcciones posteriores.
requirements-tested.txt fija las dependencias del entorno verificado.
El tutorial incluye los límites de esa verificación (Python 3.12 y SQLite).

## Reglas del ejercicio
Una recepción por hora (sin calendario de apertura). Una orden abierta por coche.
Estados: recibido -> reparación -> listo -> entregado.
Para terminar: diagnóstico y al menos una línea de trabajo. Para entregar:
confirmar, identificar quién recoge y no reducir los kilómetros.
Los costes usan Decimal y redondeo por línea. No se calculan impuestos ni pagos.
Una orden lista congela trabajos y diagnóstico; una entregada congela también notas.
Los trabajos se añaden, pero esta versión no ofrece edición ni borrado de líneas.
La ficha del titular del vehículo queda fijada; no se implementan cambios de titularidad.

## Alcance
Interfaz profesional destinada a prácticas locales. Acceso interno de personal
(is_staff), sin portal de cliente, mensajería, facturación, firma, inventario,
pagos ni asignación de mecánicos. El resumen se imprime con Ctrl+P.
No es una aplicación certificada para producción ni un sistema fiscal.
SQLite es adecuado para estas prácticas, pero no garantiza la misma coordinación
de concurrencia que PostgreSQL. select_for_update no bloquea filas en SQLite.
No se ha ensayado la migración a PostgreSQL ni el acceso concurrente de varios puestos.
Antes de uso real: revisar permisos por rol, protección de datos, despliegue,
copias externas, recuperación y pruebas con carga y base de datos definitiva.

## Configuración
Variables de entorno: DJANGO_DEBUG (1 local / 0 fuera de desarrollo),
DJANGO_SECRET_KEY y DJANGO_ALLOWED_HOSTS (hosts separados por comas).
No se lee automáticamente un archivo .env. Configúralas en Run Configuration
o en el sistema. Con DEBUG=0 la clave es obligatoria y las cookies exigen HTTPS.
runserver es solo de desarrollo; el PDF explica el siguiente paso hacia despliegue.

Código y texto propios. Las referencias oficiales usadas como documentación
están en FUENTES.md y en el PDF. No se distribuye código de terceros copiado.
