from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from consumo.models import Lote, Hidrometro, Leitura
import random


class Command(BaseCommand):
    help = 'Popula o banco de dados com dados de exemplo'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Iniciando criação de dados de exemplo...'))

        # Criar lotes residenciais
        self.stdout.write('Criando lotes residenciais...')
        lotes_residenciais = []
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
                self.stdout.write(f'  Lote {i} criado')

        # Criar lotes administrativos
        self.stdout.write('Criando lotes administrativos...')
        lotes_admin = []
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
                self.stdout.write(f'  Lote ADM-{i} criado')

        # Criar hidrômetros para lotes residenciais
        self.stdout.write('Criando hidrômetros residenciais...')
        hidrometros = []
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
            hidrometros.append(hidrometro)
            if created and i <= 10:
                self.stdout.write(f'  Hidrômetro H{i:04d} criado')

        # Criar hidrômetros administrativos
        self.stdout.write('Criando hidrômetros administrativos...')
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
            hidrometros.append(hidrometro)
            if created:
                self.stdout.write(f'  Hidrômetro HADM{i:02d} criado')

        # Criar leituras de exemplo (últimos 7 dias, 2x por dia)
        self.stdout.write('Criando leituras de exemplo...')
        total_leituras = 0
        
        for dia in range(7, 0, -1):
            data = timezone.now() - timedelta(days=dia)
            
            # Leitura da manhã
            for hidrometro in hidrometros[:10]:  # Apenas primeiros 10 para exemplo
                leitura_base = random.uniform(100, 500)
                leitura_anterior = Leitura.objects.filter(
                    hidrometro=hidrometro
                ).order_by('-data_leitura').first()
                
                if leitura_anterior:
                    leitura_base = float(leitura_anterior.leitura) + random.uniform(0.5, 3.0)
                
                data_leitura = data.replace(hour=8, minute=0)
                Leitura.objects.get_or_create(
                    hidrometro=hidrometro,
                    data_leitura=data_leitura,
                    periodo='manha',
                    defaults={
                        'leitura': Decimal(str(round(leitura_base, 3))),
                        'responsavel': 'Sistema'
                    }
                )
                total_leituras += 1
            
            # Leitura da tarde
            for hidrometro in hidrometros[:10]:
                leitura_anterior = Leitura.objects.filter(
                    hidrometro=hidrometro
                ).order_by('-data_leitura').first()
                
                leitura_base = float(leitura_anterior.leitura) + random.uniform(0.3, 2.0)
                
                data_leitura = data.replace(hour=17, minute=0)
                Leitura.objects.get_or_create(
                    hidrometro=hidrometro,
                    data_leitura=data_leitura,
                    periodo='tarde',
                    defaults={
                        'leitura': Decimal(str(round(leitura_base, 3))),
                        'responsavel': 'Sistema'
                    }
                )
                total_leituras += 1

        self.stdout.write(self.style.SUCCESS(f'\n✅ Dados de exemplo criados com sucesso!'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(lotes_residenciais)} lotes residenciais'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(lotes_admin)} lotes administrativos'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(hidrometros)} hidrômetros'))
        self.stdout.write(self.style.SUCCESS(f'  - {total_leituras} leituras de exemplo'))
