from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from consumo.models import Lote, Hidrometro, Leitura


class GraficosConsumoViewTests(TestCase):
    def setUp(self):
        # Tempo base para montar leituras no ano corrente
        self.agora = timezone.now()
        self.ano = self.agora.year
        self.mes = self.agora.month

        # Criar lotes e hidrômetros ativos
        self.lote1 = Lote.objects.create(numero=101, tipo='residencial')
        self.lote2 = Lote.objects.create(numero=202, tipo='residencial')

        data_instalacao = self.agora.date()
        self.h1 = Hidrometro.objects.create(
            numero='H1', lote=self.lote1, ativo=True, data_instalacao=data_instalacao
        )
        self.h2 = Hidrometro.objects.create(
            numero='H2', lote=self.lote2, ativo=True, data_instalacao=data_instalacao
        )

        # Leituras para h1 (consumo maior)
        self._add_leitura(self.h1, 50, day=1, periodo='manha')   # primeira do mês/ano
        self._add_leitura(self.h1, 60, day=2, periodo='tarde')
        self._add_leitura(self.h1, 70, day=5, periodo='manha')
        self._add_leitura(self.h1, 71, day=5, periodo='tarde')   # última -> total 21 m3 no ano/mes

        # Leituras para h2 (consumo menor)
        self._add_leitura(self.h2, 10, day=1, periodo='manha')
        self._add_leitura(self.h2, 10.5, day=3, periodo='tarde')  # 0.5 m3

    def _add_leitura(self, hidrometro, leitura_valor, day, periodo):
        base = self.agora.replace(day=day, hour=8 if periodo == 'manha' else 16, minute=0, second=0, microsecond=0, tzinfo=None)
        data = timezone.make_aware(base, timezone.get_current_timezone())
        return Leitura.objects.create(
            hidrometro=hidrometro,
            leitura=leitura_valor,
            periodo=periodo,
            data_leitura=data,
        )

    def test_view_returns_top_lotes_and_totals(self):
        url = reverse('consumo:graficos_consumo')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('dados_graficos', response.context)

        dados = response.context['dados_graficos']

        # Top lotes: lote1 deve vir antes de lote2
        top = dados.get('top_lotes', [])
        self.assertGreaterEqual(len(top), 2)
        self.assertEqual(top[0]['lote'], str(self.lote1.numero))
        self.assertTrue(top[0]['consumo_litros'] > top[1]['consumo_litros'])

        # Consumo total do ano deve ser consistente e não-zero
        self.assertGreater(dados['consumo_total_ano'], 0)
        soma_top = sum(item['consumo_litros'] for item in top)
        self.assertGreaterEqual(dados['consumo_total_ano'], soma_top)

        # Consumo diário do dia 5 deve existir (>= 0)
        dia5 = [d for d in dados['consumo_por_dia'] if d['dia'] == 5][0]
        self.assertGreaterEqual(dia5['consumo_litros'], 0)

        # Consumo mensal do mês atual deve existir (>= 0)
        mes_atual = [m for m in dados['consumo_mes'] if m['mes'] == self.mes][0]
        self.assertGreaterEqual(mes_atual['consumo_litros'], 0)


class GraficosConsumoSemDadosTests(TestCase):
    def test_view_sem_hidrometros_retorna_zeros(self):
        url = reverse('consumo:graficos_consumo')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        dados = response.context['dados_graficos']

        self.assertEqual(dados['consumo_total_ano'], 0)
        self.assertEqual(len(dados['top_lotes']), 0)

        # Deve trazer consumo por dia preenchido com zeros do mês atual
        self.assertTrue(len(dados['consumo_por_dia']) > 0)
        self.assertTrue(all(item['consumo_litros'] == 0 for item in dados['consumo_por_dia']))
