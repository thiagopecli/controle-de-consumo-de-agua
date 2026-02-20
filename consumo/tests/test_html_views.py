from django.test import TestCase
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
