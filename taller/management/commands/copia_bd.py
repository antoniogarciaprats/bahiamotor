import sqlite3
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Crea una copia consistente de la base SQLite local.'
    def handle(self, *args, **options):
        origen = Path(settings.DATABASES['default']['NAME'])
        if not origen.exists():
            raise CommandError('No existe la base. Ejecuta migrate primero.')
        carpeta = settings.BASE_DIR / 'backups'
        carpeta.mkdir(exist_ok=True)
        sello = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        destino = carpeta / f'bahia_{sello}.sqlite3'
        with sqlite3.connect(str(origen)) as lectura:
            with sqlite3.connect(str(destino)) as escritura:
                lectura.backup(escritura)
        self.stdout.write(self.style.SUCCESS(f'Copia creada: {destino}'))
