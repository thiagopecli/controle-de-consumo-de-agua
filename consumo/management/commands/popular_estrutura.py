from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from consumo.models import Lote, Hidrometro
import random


class Command(BaseCommand):
    help = 'Popula o banco de dados apenas com lotes e hidrômetros (sem leituras)'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Iniciando criação de lotes e hidrômetros...'))

        # Criar lotes residenciais
        self.stdout.write('Criando lotes residenciais...')
        lotes_residenciais = []
        criados_res = 0
        for i in range(1, 311):
            lote, created = Lote.objects.get_or_create(
                numero=str(i),
                defaults={
                    'tipo': 'residencial',
                    'endereco': f'Rua {(i-1)//10 + 1}, Casa {i}',
                    'ativo': True
                }
            )
            lotes_residenciais.append(lote)
            if created:
                criados_res += 1

        self.stdout.write(self.style.SUCCESS(f'  ✅ {criados_res} lotes residenciais criados'))

        # Criar lotes administrativos
        self.stdout.write('Criando lotes administrativos...')
        lotes_admin = []
        criados_adm = 0
        for i in range(1, 11):
            lote, created = Lote.objects.get_or_create(
                numero=f'ADM-{i}',
                defaults={
                    'tipo': 'administracao',
                    'endereco': f'Área Administrativa {i}',
                    'ativo': True
                }
            )
            lotes_admin.append(lote)
            if created:
                criados_adm += 1

        self.stdout.write(self.style.SUCCESS(f'  ✅ {criados_adm} lotes administrativos criados'))

        # Criar hidrômetros para lotes residenciais
        self.stdout.write('Criando hidrômetros residenciais...')
        hidrometros_criados = 0
        for i, lote in enumerate(lotes_residenciais, 1):
            hidrometro, created = Hidrometro.objects.get_or_create(
                numero=f'H{i:04d}',
                defaults={
                    'lote': lote,
                    'localizacao': f'Entrada principal',
                    'data_instalacao': timezone.now().date() - timedelta(days=random.randint(30, 365)),
                    'ativo': True
                }
            )
            if created:
                hidrometros_criados += 1

        self.stdout.write(self.style.SUCCESS(f'  ✅ {hidrometros_criados} hidrômetros residenciais criados'))

        # Criar hidrômetros administrativos
        self.stdout.write('Criando hidrômetros administrativos...')
        hidrometros_adm_criados = 0
        for i, lote in enumerate(lotes_admin, 1):
            hidrometro, created = Hidrometro.objects.get_or_create(
                numero=f'HADM{i:02d}',
                defaults={
                    'lote': lote,
                    'localizacao': f'Ponto {i}',
                    'data_instalacao': timezone.now().date() - timedelta(days=random.randint(30, 365)),
                    'ativo': True
                }
            )
            if created:
                hidrometros_adm_criados += 1

        self.stdout.write(self.style.SUCCESS(f'  ✅ {hidrometros_adm_criados} hidrômetros administrativos criados'))

        # Resumo final
        total_lotes = Lote.objects.count()
        total_hidrometros = Hidrometro.objects.count()
        
        self.stdout.write(self.style.SUCCESS('\n📊 Resumo:'))
        self.stdout.write(self.style.SUCCESS(f'  Total de lotes: {total_lotes}'))
        self.stdout.write(self.style.SUCCESS(f'  Total de hidrômetros: {total_hidrometros}'))
        self.stdout.write(self.style.SUCCESS('\n✅ Lotes e hidrômetros criados com sucesso!'))
        self.stdout.write(self.style.WARNING('⚠️  Nenhuma leitura foi criada - sistema pronto para produção'))
