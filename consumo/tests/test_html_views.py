import io
import os
import tempfile
import zipfile
from datetime import datetime

from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from consumo.models import Lote, Hidrometro, Leitura


class HtmlViewsSmokeTests(TestCase):
    def setUp(self):
        self.agora = timezone.now()
        data_instalacao = self.agora.date()
        self.lote = Lote.objects.create(numero='701', tipo='residencial')
        self.h = Hidrometro.objects.create(numero='H701', lote=self.lote, ativo=True, data_instalacao=data_instalacao)
        base = self.agora.replace(hour=8, minute=0, second=0, microsecond=0, tzinfo=None)
        data_leitura = timezone.make_aware(base, timezone.get_current_timezone())
        Leitura.objects.create(
            hidrometro=self.h,
            leitura=1,
            periodo='manha',
            data_leitura=data_leitura,
        )

    def test_dashboard(self):
        resp = self.client.get(reverse('consumo:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('total_lotes', resp.context)

    def test_listar_hidrometros(self):
        resp = self.client.get(reverse('consumo:listar_hidrometros'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('hidrometros', resp.context)
        # hidrometros é um Page object (paginado), então verificar count
        self.assertGreater(resp.context['hidrometros'].paginator.count, 0)

    def test_listar_leituras(self):
        resp = self.client.get(reverse('consumo:listar_leituras'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('leituras', resp.context)
        # leituras é um Page object (paginado), então verificar count
        self.assertGreater(resp.context['total_leituras'], 0)

    def test_registrar_leitura(self):
        resp = self.client.get(reverse('consumo:registrar_leitura'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('hidrometros', resp.context)

    def test_registrar_leitura_ordena_adm_primeiro_e_residenciais_por_lote(self):
        data_instalacao = self.agora.date()

        lote_adm = Lote.objects.create(numero='ADM-01', tipo='administracao')
        lote_adm_2 = Lote.objects.create(numero='ADM-02', tipo='administracao')
        lote_2 = Lote.objects.create(numero='2', tipo='residencial')
        lote_10 = Lote.objects.create(numero='10', tipo='residencial')

        hidrometro_adm_10 = Hidrometro.objects.create(numero='ADM10', lote=lote_adm, ativo=True, data_instalacao=data_instalacao)
        hidrometro_adm_2 = Hidrometro.objects.create(numero='ADM2', lote=lote_adm_2, ativo=True, data_instalacao=data_instalacao)
        hidrometro_2 = Hidrometro.objects.create(numero='H002', lote=lote_2, ativo=True, data_instalacao=data_instalacao)
        hidrometro_10 = Hidrometro.objects.create(numero='H010', lote=lote_10, ativo=True, data_instalacao=data_instalacao)

        resp = self.client.get(reverse('consumo:registrar_leitura'))
        self.assertEqual(resp.status_code, 200)

        hidrometros = list(resp.context['hidrometros'])
        numeros = [hidrometro.numero for hidrometro in hidrometros]

        self.assertEqual(numeros, [
            hidrometro_adm_2.numero,
            hidrometro_adm_10.numero,
            hidrometro_2.numero,
            hidrometro_10.numero,
            self.h.numero,
        ])

    def test_graficos_consumo_route(self):
        resp = self.client.get(reverse('consumo:graficos_consumo'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('dados_graficos', resp.context)

    def test_graficos_lote_route(self):
        resp = self.client.get(reverse('consumo:graficos_lote', args=[self.lote.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('dados_graficos', resp.context)

    def test_download_zip_relatorios_lotes_com_fotos(self):
        with tempfile.TemporaryDirectory() as base_dir_temp, tempfile.TemporaryDirectory() as media_dir_temp:
            pasta_relatorios = os.path.join(base_dir_temp, 'relatorios_lotes_20260115_20260215')
            os.makedirs(pasta_relatorios, exist_ok=True)

            caminho_relatorio = os.path.join(pasta_relatorios, 'relatorio_lote_701_20260115_20260215.pdf')
            with open(caminho_relatorio, 'wb') as arquivo_relatorio:
                arquivo_relatorio.write(b'%PDF-1.4 arquivo de teste')

            with override_settings(BASE_DIR=base_dir_temp, MEDIA_ROOT=media_dir_temp):
                foto_teste = SimpleUploadedFile(
                    'foto_teste.jpg',
                    b'conteudo-foto-teste',
                    content_type='image/jpeg'
                )
                Leitura.objects.create(
                    hidrometro=self.h,
                    leitura=2,
                    periodo='tarde',
                    data_leitura=timezone.make_aware(datetime(2026, 1, 20, 16, 0, 0)),
                    foto=foto_teste,
                )

                resposta = self.client.get(
                    reverse('consumo:baixar_relatorios_lotes_periodo_zip'),
                    {
                        'periodo': 'personalizado',
                        'data_inicio': '2026-01-15',
                        'data_fim': '2026-02-15',
                    }
                )

            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta['Content-Type'], 'application/zip')

            zip_buffer = io.BytesIO(resposta.content)
            with zipfile.ZipFile(zip_buffer, 'r') as arquivo_zip:
                nomes_arquivos = arquivo_zip.namelist()

            self.assertTrue(any(nome.endswith('relatorio_lote_701_20260115_20260215.pdf') for nome in nomes_arquivos))
            self.assertTrue(any('/fotos/' in nome and nome.endswith('.jpg') for nome in nomes_arquivos))
