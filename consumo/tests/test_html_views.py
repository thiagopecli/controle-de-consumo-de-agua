import io
import os
import tempfile
import zipfile
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

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

    @override_settings(TIME_ZONE='America/Sao_Paulo', USE_TZ=True)
    def test_dashboard_leituras_hoje_respeita_fuso_local(self):
        # Simula 21:30 do dia local (UTC já virou para o dia seguinte).
        agora_utc = datetime(2026, 3, 19, 0, 30, tzinfo=dt_timezone.utc)
        data_leitura_local = timezone.make_aware(
            datetime(2026, 3, 18, 8, 0),
            timezone.get_current_timezone(),
        )

        Leitura.objects.create(
            hidrometro=self.h,
            leitura=2,
            periodo='tarde',
            data_leitura=data_leitura_local,
        )

        with patch('consumo.views.timezone.now', return_value=agora_utc):
            resp = self.client.get(reverse('consumo:dashboard'))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['leituras_hoje'], 2)

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

    def test_download_zip_relatorios_lotes_pdf(self):
        """Testa download ZIP com geração automática de PDFs no período"""
        from datetime import timedelta
        
        # Criar vários lotes com leituras para testar paginação
        data_ref = timezone.now() - timedelta(days=15)
        lotes_teste = []
        
        for num_lote in [10, 55, 120]:  # Lotes em diferentes faixas
            lote = Lote.objects.create(numero=str(num_lote), tipo='residencial')
            h = Hidrometro.objects.create(
                numero=f'H{num_lote}', 
                lote=lote, 
                ativo=True, 
                data_instalacao=data_ref.date()
            )
            
            # Criar duas leituras para calcular consumo
            Leitura.objects.create(
                hidrometro=h,
                leitura=10.0,
                periodo='manha',
                data_leitura=data_ref,
            )
            Leitura.objects.create(
                hidrometro=h,
                leitura=15.0,
                periodo='tarde',
                data_leitura=data_ref + timedelta(days=1),
            )
            lotes_teste.append(num_lote)
        
        # Testar download de faixa específica (1-50)
        resposta = self.client.get(
            reverse('consumo:baixar_relatorios_lotes_periodo_zip'),
            {
                'periodo': 'personalizado',
                'data_inicio': (data_ref - timedelta(days=1)).strftime('%Y-%m-%d'),
                'data_fim': (data_ref + timedelta(days=10)).strftime('%Y-%m-%d'),
                'lote_inicio': '1',
                'lote_fim': '50',
            }
        )

        # Verificar resposta
        self.assertEqual(resposta.status_code, 200, f"Erro: {resposta.content.decode() if resposta.status_code != 200 else 'OK'}")
        self.assertEqual(resposta['Content-Type'], 'application/zip')
        self.assertIn('lotes_1_a_50', resposta['Content-Disposition'])

        # Verificar conteúdo do ZIP
        zip_buffer = io.BytesIO(resposta.content)
        with zipfile.ZipFile(zip_buffer, 'r') as arquivo_zip:
            nomes_arquivos = arquivo_zip.namelist()
            # Deve ter PDF do lote 10 (dentro da faixa 1-50)
            self.assertTrue(
                any('relatorio_lote_10' in nome for nome in nomes_arquivos),
                f"Esperado PDF do lote 10, encontrado: {nomes_arquivos}"
            )
            # NÃO deve ter PDF do lote 55 (fora da faixa 1-50)
            self.assertFalse(
                any('relatorio_lote_55' in nome for nome in nomes_arquivos),
                f"Lote 55 NÃO deveria estar na faixa 1-50"
            )
        
        # Testar download de outra faixa (51-150)
        resposta2 = self.client.get(
            reverse('consumo:baixar_relatorios_lotes_periodo_zip'),
            {
                'periodo': 'personalizado',
                'data_inicio': (data_ref - timedelta(days=1)).strftime('%Y-%m-%d'),
                'data_fim': (data_ref + timedelta(days=10)).strftime('%Y-%m-%d'),
                'lote_inicio': '51',
                'lote_fim': '150',
            }
        )
        
        self.assertEqual(resposta2.status_code, 200)
        self.assertIn('lotes_51_a_150', resposta2['Content-Disposition'])
        
        zip_buffer2 = io.BytesIO(resposta2.content)
        with zipfile.ZipFile(zip_buffer2, 'r') as arquivo_zip:
            nomes_arquivos2 = arquivo_zip.namelist()
            # Deve ter PDFs dos lotes 55 e 120 (dentro da faixa 51-150)
            self.assertTrue(any('relatorio_lote_55' in nome for nome in nomes_arquivos2))
            self.assertTrue(any('relatorio_lote_120' in nome for nome in nomes_arquivos2))
            # NÃO deve ter PDF do lote 10 (fora da faixa)
            self.assertFalse(any('relatorio_lote_10' in nome for nome in nomes_arquivos2))
