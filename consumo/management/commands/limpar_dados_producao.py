from django.core.management.base import BaseCommand
from consumo.models import Leitura, Hidrometro, Lote
import os
import shutil
from pathlib import Path


class Command(BaseCommand):
    help = 'Remove TODOS os dados do banco de dados (leituras, hidrômetros e lotes) e arquivos de mídia para preparar para produção'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma a deleção sem perguntar',
        )

    def handle(self, *args, **options):
        # Contar registros
        total_leituras = Leitura.objects.count()
        total_hidrometros = Hidrometro.objects.count()
        total_lotes = Lote.objects.count()
        
        total_registros = total_leituras + total_hidrometros + total_lotes
        
        if total_registros == 0:
            self.stdout.write(self.style.WARNING('Nenhum registro encontrado no banco de dados.'))
        else:
            self.stdout.write(self.style.WARNING(f'📊 Registros encontrados:'))
            self.stdout.write(self.style.WARNING(f'   - Leituras: {total_leituras}'))
            self.stdout.write(self.style.WARNING(f'   - Hidrômetros: {total_hidrometros}'))
            self.stdout.write(self.style.WARNING(f'   - Lotes: {total_lotes}'))
            self.stdout.write(self.style.WARNING(f'   - TOTAL: {total_registros}'))
        
        # Verificar arquivos de mídia
        media_path = Path('media/leituras')
        arquivos_encontrados = []
        if media_path.exists():
            for root, dirs, files in os.walk(media_path):
                arquivos_encontrados.extend(files)
        
        if arquivos_encontrados:
            self.stdout.write(self.style.WARNING(f'📁 Arquivos de mídia: {len(arquivos_encontrados)}'))
        
        if options['confirmar']:
            # Deletar registros do banco de dados
            if total_registros > 0:
                self.stdout.write(self.style.WARNING('\n🗑️  Deletando registros...'))
                Leitura.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✅ {total_leituras} leituras deletadas'))
                
                Hidrometro.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✅ {total_hidrometros} hidrômetros deletados'))
                
                Lote.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✅ {total_lotes} lotes deletados'))
            
            # Deletar arquivos de mídia
            if media_path.exists() and arquivos_encontrados:
                self.stdout.write(self.style.WARNING('\n🗑️  Deletando arquivos de mídia...'))
                shutil.rmtree(media_path)
                media_path.mkdir(parents=True, exist_ok=True)
                # Criar arquivo .gitkeep para manter a pasta no git
                gitkeep_file = media_path / '.gitkeep'
                gitkeep_file.touch()
                self.stdout.write(self.style.SUCCESS(f'   ✅ {len(arquivos_encontrados)} arquivos de mídia deletados'))
            
            self.stdout.write(self.style.SUCCESS('\n✅ Banco de dados limpo com sucesso!'))
            self.stdout.write(self.style.SUCCESS('✅ Sistema pronto para produção (sem dados)!'))
        else:
            self.stdout.write(self.style.ERROR('\n⚠️  ATENÇÃO: Esta operação é IRREVERSÍVEL!'))
            self.stdout.write(self.style.ERROR('⚠️  Todos os dados serão permanentemente deletados.'))
            self.stdout.write(self.style.WARNING('\n💡 Execute novamente com --confirmar para deletar:'))
            self.stdout.write(self.style.WARNING('   python manage.py limpar_dados_producao --confirmar'))
