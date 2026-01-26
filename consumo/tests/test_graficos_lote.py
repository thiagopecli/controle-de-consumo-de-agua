from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from consumo.models import Lote, Hidrometro, Leitura


class GraficosLoteSemHidrometroTests(TestCase):
    def setUp(self):
        self.lote = Lote.objects.create(numero='999', tipo='residencial')

    def test_view_sem_hidrometro_retorna_flag_sem_dados(self):
        url = reverse('consumo:graficos_lote', args=[self.lote.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get('sem_dados', False))
        self.assertEqual(response.context['lote'], self.lote)


class GraficosLoteComConsumoTests(TestCase):
    def setUp(self):
        self.agora = timezone.now()
        self.lote = Lote.objects.create(numero='303', tipo='residencial')
        data_instalacao = self.agora.date()
        self.h = Hidrometro.objects.create(
            numero='H303', lote=self.lote, ativo=True, data_instalacao=data_instalacao
        )

        # Leituras: garantem consumo no dia 2 e períodos manha/tarde
        self._add_leitura(10, day=1, periodo='manha')
        self._add_leitura(12, day=2, periodo='manha')
        self._add_leitura(12.5, day=2, periodo='tarde')
        self._add_leitura(13, day=3, periodo='tarde')

    def _add_leitura(self, valor, day, periodo):
        base = self.agora.replace(day=day, hour=8 if periodo == 'manha' else 16, minute=0, second=0, microsecond=0, tzinfo=None)
        data = timezone.make_aware(base, timezone.get_current_timezone())
        return Leitura.objects.create(
            hidrometro=self.h,
            leitura=valor,
            periodo=periodo,
            data_leitura=data,
        )

    def test_view_retorna_consumos_lote(self):
        url = reverse('consumo:graficos_lote', args=[self.lote.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        dados = response.context['dados_graficos']

        # Consumo diário: deve haver entrada para dia 2 com consumo >= 0
        dia2 = [d for d in dados['consumo_por_dia'] if d['dia'] == 2][0]
        self.assertGreaterEqual(dia2['consumo_litros'], 0)

        # Consumo mensal do mês atual deve ser não negativo
        mes_atual = [m for m in dados['consumo_mes'] if m['mes'] == self.agora.month][0]
        self.assertGreaterEqual(mes_atual['consumo_litros'], 0)

        # Consumo por período deve existir
        self.assertGreaterEqual(dados['consumo_periodo']['manha'], 0)
        self.assertGreaterEqual(dados['consumo_periodo']['tarde'], 0)

        # Flag sem_dados não deve estar presente
        self.assertFalse(response.context.get('sem_dados', False))
