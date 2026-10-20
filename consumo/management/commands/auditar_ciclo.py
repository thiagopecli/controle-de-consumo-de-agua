from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from consumo.models import Lote, Leitura, Hidrometro

class Command(BaseCommand):
    help = 'Audita o ciclo de consumo atual, verificando e-mails, PDFs, consumo zero e hidrômetros invertidos.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🔍 Iniciando auditoria completa do ciclo de água..."))

        periodo_str = "2026-10-15"
        pasta_relatorios = Path(settings.MEDIA_ROOT) / 'relatorios_mensais' / periodo_str

        lotes = Lote.objects.all()
        
        total_lotes = 0
        tudo_certo = 0
        sem_email = 0
        sem_consumo = 0
        hidrometros_invertidos = 0
        sem_pdf = 0

        self.stdout.write(f"\n--- RELATÓRIO DE AUDITORIA ({periodo_str}) ---\n")

        for lote in lotes:
            total_lotes += 1
            # Tenta pegar o número ou identificação do lote de forma segura
            lote_id = getattr(lote, 'numero', getattr(lote, 'identificacao', lote.id))
            email = getattr(lote, 'email', None)
            
            # 1. Verificar se tem email
            tem_email = bool(email and email.strip())
            if not tem_email:
                sem_email += 1
                self.stdout.write(self.style.WARNING(f"⚠️ Lote {lote_id}: Sem e-mail cadastrado."))

            # 2. Verificar se o PDF existe na pasta
            pdf_path = pasta_relatorios / f"relatorio_lote_{lote_id}_20260916_20261015.pdf"
            pdf_existe = pdf_path.exists()
            if not pdf_existe:
                sem_pdf += 1

            # 3. Buscar leituras associadas aos hidrômetros deste lote
            hidrometros = Hidrometro.objects.filter(lote=lote)
            consumo_zero = False
            invertido = False
            tem_leitura = False

            for hidrometro in hidrometros:
                leituras = Leitura.objects.filter(hidrometro=hidrometro).order_by('-data_leitura')[:2]
                if leituras.count() >= 2:
                    tem_leitura = True
                    atual = leituras[0].leitura # Ajuste para o campo numérico da leitura se necessário (ex: .valor ou .leitura)
                    anterior = leituras[1].leitura
                    
                    if atual < anterior:
                        invertido = True
                        hidrometros_invertidos += 1
                        self.stdout.write(self.style.ERROR(f"🚨 ALERTA - Lote {lote_id} (Hidrômetro {hidrometro.id}): Possível hidrômetro invertido! (Atual: {atual} < Anterior: {anterior})"))
                    
                    consumo = atual - anterior
                    if consumo == 0 and not invertido:
                        sem_consumo += 1
                        self.stdout.write(self.style.WARNING(f"🟡 Lote {lote_id}: Sem consumo registrado no período."))

            if tem_email and pdf_existe and not invertido and not consumo_zero:
                tudo_certo += 1

        self.stdout.write("\n==========================================")
        self.stdout.write(self.style.SUCCESS(f"📊 RESUMO DA AUDITORIA:"))
        self.stdout.write(f" - Total de Lotes Analisados: {total_lotes}")
        self.stdout.write(f" - Tudo Certo: {tudo_certo}")
        self.stdout.write(f" - Sem E-mail Cadastrado: {sem_email}")
        self.stdout.write(f" - Sem Consumo no Período: {sem_consumo}")
        self.stdout.write(f" - Sem PDF Gerado: {sem_pdf}")
        self.stdout.write(self.style.ERROR(f" - 🚨 Hidrômetros Invertidos Detectados: {hidrometros_invertidos}"))
        self.stdout.write("==========================================")