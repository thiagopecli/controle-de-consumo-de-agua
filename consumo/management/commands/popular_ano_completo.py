from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from consumo.models import Hidrometro, Leitura
import random


class Command(BaseCommand):
    help = 'Popula o sistema com um ano completo de leituras (2024-2025) em todos os hidrômetros'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Iniciando população do sistema com 1 ano de dados...'))
        
        # Limpar leituras existentes
        Leitura.objects.all().delete()
        self.stdout.write(self.style.WARNING('Leituras anteriores removidas'))

        # Pegar todos os hidrômetros
        hidrometros = list(Hidrometro.objects.filter(ativo=True).order_by('id'))
        
        if not hidrometros:
            self.stdout.write(self.style.ERROR('Nenhum hidrômetro encontrado!'))
            return
        
        self.stdout.write(f'📊 {len(hidrometros)} hidrômetros encontrados')
        
        # Período: 1 ano (01/01/2024 a 31/12/2024)
        data_inicio = timezone.make_aware(datetime(2024, 1, 1, 0, 0, 0))
        data_fim = timezone.make_aware(datetime(2024, 12, 31, 23, 59, 59))
        
        total_dias = (data_fim - data_inicio).days + 1
        self.stdout.write(f'📅 Período: {data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")} ({total_dias} dias)')
        
        total_leituras = 0
        leituras_batch = []
        batch_size = 1000
        
        for idx, hidrometro in enumerate(hidrometros, 1):
            # Consumo mensal aleatório entre 5.000 e 25.000 litros (em m³)
            consumo_mensal_m3 = random.uniform(5, 25)
            consumo_diario_base = consumo_mensal_m3 / 30  # Média diária
            
            # Leitura inicial aleatória entre 100 e 500 m³
            leitura_inicial = Decimal(str(random.uniform(100, 500)))
            
            # Criar leituras para cada dia do ano
            for dia in range(total_dias):
                data_base = data_inicio + timedelta(days=dia)
                
                # Variação diária (±30% da média)
                variacao = random.uniform(0.7, 1.3)
                consumo_dia = consumo_diario_base * variacao
                
                # Leitura da manhã (40% do consumo diário)
                data_manha = data_base.replace(hour=8, minute=random.randint(0, 59))
                consumo_manha = Decimal(str(consumo_dia * 0.4))
                leitura_manha = leitura_inicial + consumo_manha
                
                leituras_batch.append(Leitura(
                    hidrometro=hidrometro,
                    leitura=leitura_manha,
                    data_leitura=data_manha,
                    periodo='manha',
                    responsavel='Sistema Auto'
                ))
                total_leituras += 1
                
                # Leitura da tarde (60% do consumo diário)
                data_tarde = data_base.replace(hour=16, minute=random.randint(0, 59))
                consumo_tarde = Decimal(str(consumo_dia * 0.6))
                leitura_tarde = leitura_manha + consumo_tarde
                
                leituras_batch.append(Leitura(
                    hidrometro=hidrometro,
                    leitura=leitura_tarde,
                    data_leitura=data_tarde,
                    periodo='tarde',
                    responsavel='Sistema Auto'
                ))
                total_leituras += 1
                
                # Atualizar leitura inicial para o próximo dia
                leitura_inicial = leitura_tarde
                
                # Inserir em lote a cada 1000 registros
                if len(leituras_batch) >= batch_size:
                    Leitura.objects.bulk_create(leituras_batch)
                    leituras_batch = []
            
            # Calcular consumo total do hidrômetro
            consumo_total_litros = float(leitura_inicial - Decimal(str(random.uniform(100, 500)))) * 1000
            
            if idx % 20 == 0:
                self.stdout.write(f'  ✅ {idx}/{len(hidrometros)} hidrômetros processados ({total_leituras:,} leituras)')
        
        # Inserir leituras restantes
        if leituras_batch:
            Leitura.objects.bulk_create(leituras_batch)
        
        self.stdout.write(self.style.SUCCESS(f'\n📊 Resumo Final:'))
        self.stdout.write(self.style.SUCCESS(f'   Hidrômetros: {len(hidrometros)}'))
        self.stdout.write(self.style.SUCCESS(f'   Período: {total_dias} dias'))
        self.stdout.write(self.style.SUCCESS(f'   Leituras/dia: 2 (manhã e tarde)'))
        self.stdout.write(self.style.SUCCESS(f'   Total de leituras: {total_leituras:,}'))
        self.stdout.write(self.style.SUCCESS(f'\n✅ Sistema populado com 1 ano completo de dados!'))
        self.stdout.write(self.style.WARNING(f'💡 Agora você pode visualizar:'))
        self.stdout.write(self.style.WARNING(f'   - Gráficos mensais e anuais completos'))
        self.stdout.write(self.style.WARNING(f'   - Consumo detalhado por hidrômetro'))
        self.stdout.write(self.style.WARNING(f'   - Relatórios PDF/Excel com dados reais'))
