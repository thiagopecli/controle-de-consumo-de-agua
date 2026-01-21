from django.core.management.base import BaseCommand
from consumo.models import Leitura


class Command(BaseCommand):
    help = 'Remove todas as leituras do banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma a deleção sem perguntar',
        )

    def handle(self, *args, **options):
        total = Leitura.objects.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING('Nenhuma leitura encontrada no banco de dados.'))
            return
        
        if options['confirmar']:
            Leitura.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'✅ {total} leituras foram deletadas com sucesso!'))
            self.stdout.write(self.style.SUCCESS('✅ Os lotes e hidrômetros foram mantidos.'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️  {total} leituras serão deletadas.'))
            self.stdout.write(self.style.WARNING('Execute novamente com --confirmar para deletar.'))
            self.stdout.write(self.style.WARNING('Exemplo: python manage.py limpar_leituras --confirmar'))
