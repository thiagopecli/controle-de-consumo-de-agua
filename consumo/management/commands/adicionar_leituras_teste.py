from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from consumo.models import Hidrometro, Leitura
import random


class Command(BaseCommand):
    help = 'Adiciona 40 leituras de teste em 20 hidrômetros com consumo entre 7 mil e 22 mil litros'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Iniciando criação de leituras de teste...'))

        # Pegar os primeiros 20 hidrômetros
        hidrometros = list(Hidrometro.objects.filter(ativo=True).order_by('id')[:20])
        
        if len(hidrometros) < 20:
            self.stdout.write(self.style.WARNING(f'⚠️  Apenas {len(hidrometros)} hidrômetros encontrados'))
        
        hoje = timezone.now()
        data_inicio = hoje - timedelta(days=30)
        
        total_leituras = 0
        
        for hidrometro in hidrometros:
            # Consumo total entre 7.000 e 22.000 litros (convertido para m3)
            consumo_total_litros = random.uniform(7000, 22000)
            consumo_total_m3 = consumo_total_litros / 1000
            
            # Leitura inicial aleatória entre 100 e 500 m³
            leitura_inicial = Decimal(str(random.uniform(100, 500)))
            
            # Criar 40 leituras ao longo de 30 dias (manhã e tarde)
            # 2 leituras por dia durante 20 dias
            for dia in range(20):
                data_base = data_inicio + timedelta(days=dia)
                
                # Calcular incremento proporcional
                incremento_dia = consumo_total_m3 / 20  # Distribuir consumo em 20 dias
                
                # Leitura da manhã (40% do consumo diário)
                data_manha = data_base.replace(hour=8, minute=random.randint(0, 59))
                consumo_manha = Decimal(str(incremento_dia * 0.4))
                leitura_manha = leitura_inicial + consumo_manha
                
                Leitura.objects.create(
                    hidrometro=hidrometro,
                    leitura=leitura_manha,
                    data_leitura=data_manha,
                    periodo='manha',
                    responsavel='Sistema Teste'
                )
                total_leituras += 1
                
                # Leitura da tarde (60% do consumo diário)
                data_tarde = data_base.replace(hour=16, minute=random.randint(0, 59))
                consumo_tarde = Decimal(str(incremento_dia * 0.6))
                leitura_tarde = leitura_manha + consumo_tarde
                
                Leitura.objects.create(
                    hidrometro=hidrometro,
                    leitura=leitura_tarde,
                    data_leitura=data_tarde,
                    periodo='tarde',
                    responsavel='Sistema Teste'
                )
                total_leituras += 1
                
                # Atualizar leitura inicial para o próximo dia
                leitura_inicial = leitura_tarde
            
            self.stdout.write(f'  ✅ Hidrômetro {hidrometro.numero}: {consumo_total_litros:.0f}L em 40 leituras')
        
        self.stdout.write(self.style.SUCCESS(f'\n📊 Total: {total_leituras} leituras criadas em {len(hidrometros)} hidrômetros'))
        self.stdout.write(self.style.SUCCESS('✅ Leituras de teste criadas com sucesso!'))
