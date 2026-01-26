from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from consumo.models import Lote, Hidrometro, Leitura


class ApiLeiturasTests(APITestCase):
    def setUp(self):
        self.agora = timezone.now()
        data_instalacao = self.agora.date()
        self.lote = Lote.objects.create(numero='401', tipo='residencial')
        self.h = Hidrometro.objects.create(numero='H401', lote=self.lote, ativo=True, data_instalacao=data_instalacao)

    def _leitura_payload(self, valor, day=1, periodo='manha'):
        base = self.agora.replace(day=day, hour=8 if periodo == 'manha' else 16, minute=0, second=0, microsecond=0, tzinfo=None)
        data = timezone.make_aware(base, timezone.get_current_timezone())
        return {
            'hidrometro': self.h.id,
            'leitura': valor,
            'data_leitura': data.isoformat(),
            'periodo': periodo,
            'responsavel': 'tester',
        }

    def test_leitura_create_validation_blocks_lower_value(self):
        # primeiro cria leitura
        payload1 = self._leitura_payload(10, day=1)
        url_create = reverse('consumo:leitura-list')
        resp1 = self.client.post(url_create, payload1, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # tentativa com valor menor deve falhar
        payload2 = self._leitura_payload(9, day=2)
        resp2 = self.client.post(url_create, payload2, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('leitura', str(resp2.data))

    def test_leitura_em_lote_bulk_partial(self):
        payload = {
            'leituras': [
                self._leitura_payload(5, day=1),  # ok
                self._leitura_payload(4, day=2),  # menor -> erro
            ]
        }
        url_bulk = reverse('consumo:leitura-leitura-em-lote')
        resp = self.client.post(url_bulk, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['criadas'], 1)
        self.assertEqual(resp.data['erros'], 1)

    def test_ultimas_leituras_endpoint(self):
        # cria duas leituras para garantir retorno
        url_create = reverse('consumo:leitura-list')
        self.client.post(url_create, self._leitura_payload(1, day=1), format='json')
        self.client.post(url_create, self._leitura_payload(2, day=2), format='json')

        url_ultimas = reverse('consumo:leitura-ultimas-leituras')
        resp = self.client.get(url_ultimas)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(len(resp.data) >= 1)
        self.assertEqual(resp.data[0]['hidrometro'], self.h.numero)


class ApiHidrometroFiltersTests(APITestCase):
    def setUp(self):
        data_instalacao = timezone.now().date()
        self.lote_a = Lote.objects.create(numero='501', tipo='residencial')
        self.lote_b = Lote.objects.create(numero='502', tipo='residencial')
        Hidrometro.objects.create(numero='HA', lote=self.lote_a, ativo=True, data_instalacao=data_instalacao)
        Hidrometro.objects.create(numero='HB', lote=self.lote_b, ativo=False, data_instalacao=data_instalacao)

    def test_filter_by_lote_and_ativo(self):
        # filtro lote
        url = reverse('consumo:hidrometro-list')
        resp = self.client.get(f"{url}?lote={self.lote_a.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['numero'], 'HA')

        # filtro ativo=false
        resp2 = self.client.get(f"{url}?ativo=false")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['results'][0]['numero'], 'HB')


class ApiLeiturasPeriodoTests(APITestCase):
    def setUp(self):
        self.agora = timezone.now()
        data_instalacao = self.agora.date()
        self.lote = Lote.objects.create(numero='601', tipo='residencial')
        self.h = Hidrometro.objects.create(numero='H601', lote=self.lote, ativo=True, data_instalacao=data_instalacao)
        # leituras
        self._add_leitura(1, day=1)
        self._add_leitura(3, day=2)

    def _add_leitura(self, valor, day=1):
        base = self.agora.replace(day=day, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
        data = timezone.make_aware(base, timezone.get_current_timezone())
        return Leitura.objects.create(
            hidrometro=self.h,
            leitura=valor,
            periodo='manha',
            data_leitura=data,
        )

    def test_leituras_periodo_action(self):
        inicio = self.agora.replace(day=1).date().isoformat()
        fim = self.agora.replace(day=3).date().isoformat()
        url_lp = reverse('consumo:hidrometro-leituras-periodo', args=[self.h.id])
        resp = self.client.get(f"{url_lp}?data_inicio={inicio}&data_fim={fim}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)

    def test_estatisticas_action(self):
        url_est = reverse('consumo:hidrometro-estatisticas', args=[self.h.id])
        resp = self.client.get(f"{url_est}?dias=5")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        if 'message' in resp.data:
            # Caso sem leituras no intervalo, garantir mensagem amigável
            self.assertIn('Sem leituras', resp.data['message'])
        else:
            self.assertEqual(resp.data['hidrometro'], self.h.numero)
            self.assertGreaterEqual(resp.data['consumo_total_m3'], 0)
