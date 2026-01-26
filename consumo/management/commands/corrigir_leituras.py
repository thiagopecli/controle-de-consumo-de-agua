from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from consumo.models import Hidrometro, Leitura
import random


class Command(BaseCommand):
    help = 'Remove leituras futuras e popula com leituras de 01/01 até hoje'

    def handle(self, *args, **options):
        hoje = timezone.now()
        
        # Deletar todas as leituras futuras (após hoje)
        leituras_futuras = Leitura.objects.filter(data_leitura__gt=hoje)
        count_futuras = leituras_futuras.count()
        if count_futuras > 0:
            self.stdout.write(f"Removendo {count_futuras} leituras com datas futuras...")
            leituras_futuras.delete()
            self.stdout.write(self.style.SUCCESS(f"✓ {count_futuras} leituras futuras removidas"))
        
        # Deletar TODAS as leituras para recomeçar do zero
        self.stdout.write("\nRemovendo todas as leituras existentes...")
        Leitura.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("✓ Todas as leituras removidas"))
        
        # Data de início: 01/01/2026
        data_inicio = timezone.datetime(2026, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
        
        self.stdout.write(f"\nCriando leituras de {data_inicio.date()} até {hoje.date()}...")
        
        # Buscar alguns hidrômetros para popular (vamos usar os primeiros 20 residenciais + 2 admin)
        hidrometros_residenciais = list(Hidrometro.objects.filter(
            ativo=True, 
            lote__tipo='residencial'
        ).order_by('numero')[:20])
        
        hidrometros_admin = list(Hidrometro.objects.filter(
            ativo=True, 
            lote__tipo='administracao'
        ).order_by('numero')[:2])
        
        hidrometros = hidrometros_residenciais + hidrometros_admin
        
        self.stdout.write(f"Populando leituras para {len(hidrometros)} hidrômetros:")
        for h in hidrometros:
            self.stdout.write(f"  - {h.numero} (Lote {h.lote.numero})")
        
        total_leituras = 0
        
        # Para cada hidrômetro, criar leituras diárias (manhã e tarde)
        for hidrometro in hidrometros:
            # Leitura inicial base (entre 5000 e 15000 m³)
            leitura_base = random.uniform(5000, 15000)
            leitura_atual = leitura_base
            
            # Iterar por cada dia desde 01/01 até hoje
            data_cursor = data_inicio
            
            while data_cursor <= hoje:
                # Leitura da manhã (8h às 12h)
                hora_manha = random.randint(8, 12)
                minuto_manha = random.randint(0, 59)
                data_leitura_manha = data_cursor.replace(hour=hora_manha, minute=minuto_manha)
                
                # Só criar se não for futura
                if data_leitura_manha <= hoje:
                    Leitura.objects.create(
                        hidrometro=hidrometro,
                        leitura=round(leitura_atual, 3),
                        data_leitura=data_leitura_manha,
                        periodo='manha',
                        responsavel='Sistema'
                    )
                    total_leituras += 1
                
                # Consumo entre manhã e tarde (50 a 300 litros = 0.05 a 0.3 m³)
                consumo_manha_tarde = random.uniform(0.05, 0.3)
                leitura_atual += consumo_manha_tarde
                
                # Leitura da tarde (14h às 18h)
                hora_tarde = random.randint(14, 18)
                minuto_tarde = random.randint(0, 59)
                data_leitura_tarde = data_cursor.replace(hour=hora_tarde, minute=minuto_tarde)
                
                # Só criar se não for futura
                if data_leitura_tarde <= hoje:
                    Leitura.objects.create(
                        hidrometro=hidrometro,
                        leitura=round(leitura_atual, 3),
                        data_leitura=data_leitura_tarde,
                        periodo='tarde',
                        responsavel='Sistema'
                    )
                    total_leituras += 1
                
                # Consumo noturno até próxima manhã (100 a 500 litros = 0.1 a 0.5 m³)
                consumo_noite = random.uniform(0.1, 0.5)
                leitura_atual += consumo_noite
                
                # Próximo dia
                data_cursor += timedelta(days=1)
        
        self.stdout.write(self.style.SUCCESS(f"\n✓ Sucesso! {total_leituras} leituras criadas"))
        self.stdout.write(f"Período: {data_inicio.date()} até {hoje.date()}")
        self.stdout.write(f"Hidrômetros: {len(hidrometros)}")
        self.stdout.write(f"Média: {total_leituras / len(hidrometros):.1f} leituras por hidrômetro")
