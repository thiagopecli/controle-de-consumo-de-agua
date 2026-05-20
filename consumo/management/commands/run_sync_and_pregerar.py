from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone


class Command(BaseCommand):
    help = 'Executa sincronizar_fotos_leituras e pregerar_relatorios_mensais em sequência'

    def add_arguments(self, parser):
        parser.add_argument('--data-coleta', type=str, help='Data de coleta no formato YYYY-MM-DD')
        parser.add_argument('--base-url', type=str, help='URL base do app (ex: https://meu-app.onrender.com)')
        parser.add_argument('--sobrescrever', action='store_true', help='Força sobrescrever arquivos existentes')
        parser.add_argument('--timeout', type=int, default=30, help='Timeout (segundos) para downloads de imagem')

    def handle(self, *args, **options):
        data_coleta = options.get('data_coleta')
        base_url = options.get('base_url')
        sobrescrever = options.get('sobrescrever')
        timeout = options.get('timeout')

        now = timezone.localtime()
        self.stdout.write(self.style.MIGRATE_HEADING(f'Início: {now.isoformat()}'))

        sync_opts = []
        if data_coleta:
            sync_opts += ['--data-coleta', data_coleta]
        if base_url:
            sync_opts += ['--base-url', base_url]
        if sobrescrever:
            sync_opts.append('--sobrescrever')
        if timeout:
            sync_opts += ['--timeout', str(timeout)]

        self.stdout.write('Executando: sincronizar_fotos_leituras')
        call_command('sincronizar_fotos_leituras', *sync_opts)

        pre_opts = []
        if data_coleta:
            pre_opts += ['--data-coleta', data_coleta]
        if sobrescrever:
            pre_opts.append('--sobrescrever')

        self.stdout.write('Executando: pregerar_relatorios_mensais')
        call_command('pregerar_relatorios_mensais', *pre_opts)

        now_end = timezone.localtime()
        self.stdout.write(self.style.SUCCESS(f'Concluído: {now_end.isoformat()}'))
