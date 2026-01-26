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

        # Criar leituras de exemplo (últimos 90 dias, 2x por dia para todos os hidrômetros)
        self.stdout.write('Criando leituras de exemplo (últimos 90 dias com consumo realista)...')
        total_leituras = 0
        
        # Usar todos os 20 primeiros hidrômetros para ter dados mais ricos
        hidrometros_exemplo = hidrometros[:20]
        
        # Para cada hidrômetro, gerar consumo mensal aleatório entre 5mil e 25mil litros
        consumo_mensal_por_hidrometro = {}
        for hidrometro in hidrometros_exemplo:
            # Gerar consumo mensal entre 5.000 e 25.000 litros
            consumo_mensal_m3 = random.uniform(5, 25)  # em m³
            consumo_mensal_por_hidrometro[hidrometro.id] = consumo_mensal_m3
        
        # Começar 90 dias atrás
        for dia in range(90, -1, -1):
            data = timezone.now() - timedelta(days=dia)
            dia_do_mes = data.day
            
            # Leitura da manhã (proporção 40% do consumo diário)
            for hidrometro in hidrometros_exemplo:
                leitura_anterior = Leitura.objects.filter(
                    hidrometro=hidrometro
                ).order_by('-data_leitura').first()
                
                # Consumo mensal do hidrômetro distribuído em 30 dias
                consumo_mensal_m3 = consumo_mensal_por_hidrometro[hidrometro.id]
                consumo_diario_medio = consumo_mensal_m3 / 30  # Consumo médio por dia em m³
                
                # Adicionar variação aleatória (-30% a +50%) ao consumo diário
                fator_variacao = random.uniform(0.7, 1.5)
                consumo_diario = consumo_diario_medio * fator_variacao
                
                # Proporção da manhã (40% do consumo diário)
                consumo_manha = consumo_diario * 0.4
                
                if leitura_anterior:
                    leitura_base = float(leitura_anterior.leitura) + consumo_manha
                else:
                    # Leitura inicial aleatória entre 1000 e 5000 m³
                    leitura_base = random.uniform(1000, 5000)
                
                data_leitura = data.replace(hour=8, minute=random.randint(0, 59))
                leitura, created = Leitura.objects.get_or_create(
                    hidrometro=hidrometro,
                    data_leitura=data_leitura,
                    periodo='manha',
                    defaults={
                        'leitura': Decimal(str(round(leitura_base, 3))),
                        'responsavel': random.choice(['João Silva', 'Maria Santos', 'Carlos Oliveira', 'Ana Costa'])
                    }
                )
                if created:
                    total_leituras += 1
            
            # Leitura da tarde (proporção 60% do consumo diário)
            for hidrometro in hidrometros_exemplo:
                leitura_anterior = Leitura.objects.filter(
                    hidrometro=hidrometro
                ).order_by('-data_leitura').first()
                
                # Reutilizar o mesmo consumo diário da manhã
                consumo_mensal_m3 = consumo_mensal_por_hidrometro[hidrometro.id]
                consumo_diario_medio = consumo_mensal_m3 / 30
                fator_variacao = random.uniform(0.7, 1.5)
                consumo_diario = consumo_diario_medio * fator_variacao
                
                # Proporção da tarde (60% do consumo diário)
                consumo_tarde = consumo_diario * 0.6
                
                if leitura_anterior:
                    leitura_base = float(leitura_anterior.leitura) + consumo_tarde
                else:
                    leitura_base = random.uniform(1000, 5000)
                
                data_leitura = data.replace(hour=17, minute=random.randint(0, 59))
                leitura, created = Leitura.objects.get_or_create(
                    hidrometro=hidrometro,
                    data_leitura=data_leitura,
                    periodo='tarde',
                    defaults={
                        'leitura': Decimal(str(round(leitura_base, 3))),
                        'responsavel': random.choice(['João Silva', 'Maria Santos', 'Carlos Oliveira', 'Ana Costa'])
                    }
                )
                if created:
                    total_leituras += 1
            
            # Mostrar progresso a cada 10 dias
            if dia % 10 == 0:
                self.stdout.write(f'  Processando dia {90-dia+1}/91...')

        self.stdout.write(self.style.SUCCESS(f'\n✅ Dados de exemplo criados com sucesso!'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(lotes_residenciais)} lotes residenciais'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(lotes_admin)} lotes administrativos'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(hidrometros)} hidrômetros'))
        self.stdout.write(self.style.SUCCESS(f'  - {total_leituras} leituras criadas'))
        self.stdout.write(self.style.SUCCESS(f'  - 20 hidrômetros com dados dos últimos 90 dias'))
        self.stdout.write(self.style.SUCCESS(f'  - Consumo mensal entre 5.000 e 25.000 litros por hidrômetro (realista)'))
        self.stdout.write(self.style.SUCCESS(f'  - Proporção: 40% manhã, 60% tarde'))
        self.stdout.write(self.style.SUCCESS(f'\n💡 Acesse /graficos/ para visualizar os dados!'))
