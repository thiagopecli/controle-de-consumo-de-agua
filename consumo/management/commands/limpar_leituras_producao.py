"""
Comando para limpar dados de consumo (leituras) do banco de dados
Útil para testes e limpeza de dados de produção
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from consumo.models import Leitura
from datetime import timedelta


class Command(BaseCommand):
    help = 'Limpa dados de consumo (leituras) do banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Limpa TODAS as leituras do banco de dados (não recomendado)',
        )
        parser.add_argument(
            '--dias',
            type=int,
            default=None,
            help='Limpa leituras mais antigas que N dias',
        )
        parser.add_argument(
            '--meses',
            type=int,
            default=None,
            help='Limpa leituras mais antigas que N meses',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirma a operação sem pedir confirmação',
        )

    def handle(self, *args, **options):
        todas_leituras = Leitura.objects.all()
        total_leituras_antes = todas_leituras.count()

        if not total_leituras_antes:
            self.stdout.write(
                self.style.WARNING('Não há leituras para limpar no banco de dados.')
            )
            return

        # Definir filtro de deleção
        if options['all']:
            leituras_para_deletar = todas_leituras
            descricao = 'TODAS as leituras'
        elif options['dias']:
            data_limite = timezone.now() - timedelta(days=options['dias'])
            leituras_para_deletar = todas_leituras.filter(data_leitura__lt=data_limite)
            descricao = f'leituras com mais de {options["dias"]} dias'
        elif options['meses']:
            data_limite = timezone.now() - timedelta(days=options['meses'] * 30)
            leituras_para_deletar = todas_leituras.filter(data_leitura__lt=data_limite)
            descricao = f'leituras com mais de {options["meses"]} meses'
        else:
            self.stdout.write(
                self.style.ERROR('Especifique --all, --dias ou --meses')
            )
            return

        quantidade_para_deletar = leituras_para_deletar.count()

        if not quantidade_para_deletar:
            self.stdout.write(
                self.style.SUCCESS('Nenhuma leitura corresponde aos critérios de limpeza.')
            )
            return

        # Pedir confirmação
        self.stdout.write(
            self.style.WARNING(
                f'\n⚠️  AVISO: Você está prestes a DELETAR {quantidade_para_deletar} leituras ({descricao})!\n'
            )
        )

        if not options['confirm']:
            confirmacao = input('Tem certeza que deseja continuar? (sim/nao): ').lower().strip()
            if confirmacao not in ['sim', 's', 'yes', 'y']:
                self.stdout.write(self.style.ERROR('Operação cancelada.'))
                return

        # Deletar leituras
        leituras_para_deletar.delete()
        total_leituras_depois = Leitura.objects.all().count()
        deletadas = total_leituras_antes - total_leituras_depois

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Sucesso! {deletadas} leituras foram deletadas.\n'
                f'Total de leituras antes: {total_leituras_antes}\n'
                f'Total de leituras depois: {total_leituras_depois}\n'
            )
        )
