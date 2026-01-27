"""
Testes para integridade de dados, segurança, validações e edge cases
Garante que o aplicativo seja robusto, seguro e eficiente
"""
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal
import json

from consumo.models import Lote, Hidrometro, Leitura


class ModelIntegridadeTests(TestCase):
    """Testes de integridade dos modelos e relacionamentos"""
    
    def setUp(self):
        self.agora = timezone.now()
        self.lote = Lote.objects.create(numero='TEST-001', tipo='residencial')
        self.hidrometro = Hidrometro.objects.create(
            numero='H001',
            lote=self.lote,
            data_instalacao=self.agora.date()
        )
    
    def test_leitura_unique_together_constraint(self):
        """Testa constraint unique_together: hidrometro, data_leitura, periodo"""
        # Criar primeira leitura
        leitura1 = Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('100.000'),
            data_leitura=self.agora,
            periodo='manha'
        )
        
        # Tentar criar segunda leitura com mesmos hidrometro, data e período
        with self.assertRaises(Exception):
            Leitura.objects.create(
                hidrometro=self.hidrometro,
                leitura=Decimal('100.500'),
                data_leitura=self.agora,
                periodo='manha'
            )
    
    def test_hidrometro_cascade_delete(self):
        """Testa se deletar hidrometro deleta suas leituras"""
        leitura = Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('100.000'),
            data_leitura=self.agora,
            periodo='manha'
        )
        
        hidrometro_id = self.hidrometro.id
        leitura_id = leitura.id
        
        # Deletar hidrometro
        self.hidrometro.delete()
        
        # Verificar que hidrometro foi deletado
        self.assertFalse(Hidrometro.objects.filter(id=hidrometro_id).exists())
        
        # Verificar que leitura foi deletada em cascata
        self.assertFalse(Leitura.objects.filter(id=leitura_id).exists())
    
    def test_lote_cascade_delete(self):
        """Testa se deletar lote deleta seus hidrômetros e leituras"""
        hidrometro = Hidrometro.objects.create(
            numero='H002',
            lote=self.lote,
            data_instalacao=self.agora.date()
        )
        
        leitura = Leitura.objects.create(
            hidrometro=hidrometro,
            leitura=Decimal('100.000'),
            data_leitura=self.agora,
            periodo='manha'
        )
        
        lote_id = self.lote.id
        hidrometro_id = hidrometro.id
        leitura_id = leitura.id
        
        # Deletar lote
        self.lote.delete()
        
        # Verificar que tudo foi deletado em cascata
        self.assertFalse(Lote.objects.filter(id=lote_id).exists())
        self.assertFalse(Hidrometro.objects.filter(id=hidrometro_id).exists())
        self.assertFalse(Leitura.objects.filter(id=leitura_id).exists())
    
    def test_numero_hidrometro_unique(self):
        """Testa se números de hidrômetro são únicos"""
        # Tentar criar dois hidrômetros com mesmo número
        with self.assertRaises(Exception):
            Hidrometro.objects.create(
                numero='H001',
                lote=self.lote,
                data_instalacao=self.agora.date()
            )


class ValidacaoLeituraTests(TestCase):
    """Testes de validação de leituras"""
    
    def setUp(self):
        self.agora = timezone.now()
        self.lote = Lote.objects.create(numero='VAL-001', tipo='residencial')
        self.hidrometro = Hidrometro.objects.create(
            numero='HV001',
            lote=self.lote,
            data_instalacao=self.agora.date()
        )
    
    def test_leitura_negativa_invalida(self):
        """Testa que leitura negativa é rejeitada"""
        from django.core.exceptions import ValidationError
        
        leitura = Leitura(
            hidrometro=self.hidrometro,
            leitura=Decimal('-10.000'),  # Negativo
            data_leitura=self.agora,
            periodo='manha'
        )
        
        with self.assertRaises(ValidationError):
            leitura.full_clean()
    
    def test_leitura_acima_limite_maxima(self):
        """Testa que leitura acima do limite máximo é rejeitada"""
        from django.core.exceptions import ValidationError
        
        leitura = Leitura(
            hidrometro=self.hidrometro,
            leitura=Decimal('100000.000'),  # Acima do máximo
            data_leitura=self.agora,
            periodo='manha'
        )
        
        with self.assertRaises(ValidationError):
            leitura.full_clean()
    
    def test_leitura_com_casas_decimais_validas(self):
        """Testa leituras com 0 a 3 casas decimais"""
        valores_validos = [
            Decimal('10'),
            Decimal('10.1'),
            Decimal('10.12'),
            Decimal('10.123'),
        ]
        
        for idx, valor in enumerate(valores_validos):
            leitura = Leitura.objects.create(
                hidrometro=self.hidrometro,
                leitura=valor,
                data_leitura=self.agora + timezone.timedelta(days=idx),
                periodo='manha'  # Variar período também para evitar constraint
            )
            self.assertEqual(leitura.leitura, valor)
    
    def test_leitura_descrescente_invalida_api(self):
        """Testa que API rejeita leitura descrescente"""
        # Criar primeira leitura
        Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('100.000'),
            data_leitura=self.agora,
            periodo='manha'
        )
        
        # Tentar criar leitura menor que anterior
        url = reverse('consumo:leitura-list')
        payload = {
            'hidrometro': self.hidrometro.id,
            'leitura': '50.000',  # Menor que 100
            'data_leitura': (self.agora + timezone.timedelta(days=1)).isoformat(),
            'periodo': 'tarde'
        }
        
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_consumo_calculo_correto(self):
        """Testa cálculo correto de consumo entre leituras"""
        # Criar duas leituras
        leitura1 = Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('100.000'),
            data_leitura=self.agora,
            periodo='manha'
        )
        
        leitura2 = Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('105.500'),
            data_leitura=self.agora + timezone.timedelta(days=1),
            periodo='tarde'
        )
        
        # Verificar consumo
        consumo = leitura2.consumo_desde_ultima_leitura()
        self.assertEqual(consumo, Decimal('5.500'))
        
        # Verificar em litros
        consumo_litros = leitura2.consumo_desde_ultima_leitura_litros()
        self.assertAlmostEqual(float(consumo_litros), 5500.0, places=2)


class PeriodoTestCase(TestCase):
    """Testes sobre períodos de leitura"""
    
    def setUp(self):
        self.agora = timezone.now()
        self.lote = Lote.objects.create(numero='PER-001', tipo='residencial')
        self.hidrometro = Hidrometro.objects.create(
            numero='HP001',
            lote=self.lote,
            data_instalacao=self.agora.date()
        )
    
    def test_periodo_manha_tarde_validos(self):
        """Testa se períodos válidos são aceitos"""
        periodos_validos = ['manha', 'tarde']
        
        for periodo in periodos_validos:
            leitura = Leitura.objects.create(
                hidrometro=self.hidrometro,
                leitura=Decimal('100.000'),
                data_leitura=self.agora + timezone.timedelta(hours=1),
                periodo=periodo
            )
            self.assertEqual(leitura.periodo, periodo)
    
    def test_mesmo_dia_dois_periodos(self):
        """Testa leituras do mesmo dia em períodos diferentes"""
        leitura_manha = Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('100.000'),
            data_leitura=self.agora.replace(hour=8, minute=0, second=0, microsecond=0),
            periodo='manha'
        )
        
        leitura_tarde = Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('102.500'),
            data_leitura=self.agora.replace(hour=16, minute=0, second=0, microsecond=0),
            periodo='tarde'
        )
        
        # Verificar que ambas existem
        self.assertTrue(Leitura.objects.filter(periodo='manha').exists())
        self.assertTrue(Leitura.objects.filter(periodo='tarde').exists())


class APIAutenticacaoTestes(APITestCase):
    """Testes de autenticação e controle de acesso na API"""
    
    def setUp(self):
        self.agora = timezone.now()
        self.lote = Lote.objects.create(numero='API-001', tipo='residencial')
        self.hidrometro = Hidrometro.objects.create(
            numero='HA001',
            lote=self.lote,
            data_instalacao=self.agora.date()
        )
    
    def test_leitura_list_accessible(self):
        """Testa se lista de leituras é acessível (sem autenticação obrigatória)"""
        url = reverse('consumo:leitura-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_leitura_create_accessible(self):
        """Testa se criação de leitura é acessível (sem autenticação obrigatória)"""
        url = reverse('consumo:leitura-list')
        payload = {
            'hidrometro': self.hidrometro.id,
            'leitura': '100.000',
            'data_leitura': self.agora.isoformat(),
            'periodo': 'manha'
        }
        response = self.client.post(url, payload, format='json')
        # Pode ser 201 ou 400 dependendo de validação, mas não deve ser 401/403
        self.assertNotEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 403)


class ValidacaoCamposTests(TestCase):
    """Testes de validação de campos dos modelos"""
    
    def test_lote_tipo_choices(self):
        """Testa se tipos de lote são validados"""
        # Tipo válido
        lote = Lote(numero='CH-001', tipo='residencial')
        lote.full_clean()  # Não deve lançar exceção
        
        # Tipo válido
        lote2 = Lote(numero='CH-002', tipo='administracao')
        lote2.full_clean()  # Não deve lançar exceção
    
    def test_lote_numero_max_length(self):
        """Testa se número do lote respeita max_length"""
        numero_longo = 'A' * 11  # Maior que max_length=10
        lote = Lote(numero=numero_longo, tipo='residencial')
        
        with self.assertRaises(ValidationError):
            lote.full_clean()
    
    def test_hidrometro_numero_max_length(self):
        """Testa se número do hidrômetro respeita max_length"""
        numero_longo = 'H' * 21  # Maior que max_length=20
        lote = Lote.objects.create(numero='VAL-H', tipo='residencial')
        hidrometro = Hidrometro(
            numero=numero_longo,
            lote=lote,
            data_instalacao=timezone.now().date()
        )
        
        with self.assertRaises(ValidationError):
            hidrometro.full_clean()
    
    def test_leitura_responsavel_max_length(self):
        """Testa se responsável respeita max_length"""
        lote = Lote.objects.create(numero='VAL-R', tipo='residencial')
        hidrometro = Hidrometro.objects.create(
            numero='HVR001',
            lote=lote,
            data_instalacao=timezone.now().date()
        )
        
        responsavel_longo = 'X' * 101  # Maior que max_length=100
        leitura = Leitura(
            hidrometro=hidrometro,
            leitura=Decimal('100.000'),
            data_leitura=timezone.now(),
            periodo='manha',
            responsavel=responsavel_longo
        )
        
        with self.assertRaises(ValidationError):
            leitura.full_clean()


class ConsumoDiarioTests(TestCase):
    """Testes de cálculos de consumo diário"""
    
    def setUp(self):
        self.agora = timezone.now()
        self.lote = Lote.objects.create(numero='CON-001', tipo='residencial')
        self.hidrometro = Hidrometro.objects.create(
            numero='HCD001',
            lote=self.lote,
            data_instalacao=self.agora.date()
        )
    
    def test_consumo_diario_sem_leituras(self):
        """Testa consumo diário quando não há leituras"""
        consumo = self.hidrometro.consumo_diario_atual()
        self.assertEqual(consumo, 0)
    
    def test_consumo_diario_uma_leitura(self):
        """Testa consumo diário com apenas uma leitura no dia"""
        Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('100.000'),
            data_leitura=self.agora,
            periodo='manha'
        )
        
        consumo = self.hidrometro.consumo_diario_atual()
        self.assertEqual(consumo, 0)  # Precisa de duas leituras
    
    def test_consumo_diario_duas_leituras(self):
        """Testa consumo diário com duas leituras no dia"""
        Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('100.000'),
            data_leitura=self.agora.replace(hour=8, minute=0, second=0, microsecond=0),
            periodo='manha'
        )
        
        Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('105.000'),
            data_leitura=self.agora.replace(hour=16, minute=0, second=0, microsecond=0),
            periodo='tarde'
        )
        
        consumo = self.hidrometro.consumo_diario_atual()
        self.assertEqual(consumo, Decimal('5.000'))
    
    def test_consumo_diario_litros(self):
        """Testa conversão de consumo diário para litros"""
        Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('100.000'),
            data_leitura=self.agora.replace(hour=8, minute=0, second=0, microsecond=0),
            periodo='manha'
        )
        
        Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('105.500'),
            data_leitura=self.agora.replace(hour=16, minute=0, second=0, microsecond=0),
            periodo='tarde'
        )
        
        consumo_litros = self.hidrometro.consumo_diario_atual_litros()
        self.assertAlmostEqual(float(consumo_litros), 5500.0, places=2)


class HidrometroAtivoTests(TestCase):
    """Testes de status ativo/inativo de hidrômetros"""
    
    def setUp(self):
        self.agora = timezone.now()
        self.lote = Lote.objects.create(numero='ATI-001', tipo='residencial')
    
    def test_hidrometro_ativo_por_padrao(self):
        """Testa se hidrômetro é ativo por padrão"""
        hidrometro = Hidrometro.objects.create(
            numero='HAA001',
            lote=self.lote,
            data_instalacao=self.agora.date()
        )
        
        self.assertTrue(hidrometro.ativo)
    
    def test_hidrometro_inativo(self):
        """Testa se é possível desativar hidrômetro"""
        hidrometro = Hidrometro.objects.create(
            numero='HAA002',
            lote=self.lote,
            data_instalacao=self.agora.date(),
            ativo=False
        )
        
        self.assertFalse(hidrometro.ativo)


class LoteAtivoTests(TestCase):
    """Testes de status ativo/inativo de lotes"""
    
    def test_lote_ativo_por_padrao(self):
        """Testa se lote é ativo por padrão"""
        lote = Lote.objects.create(numero='AT-001', tipo='residencial')
        self.assertTrue(lote.ativo)
    
    def test_lote_inativo(self):
        """Testa se é possível desativar lote"""
        lote = Lote.objects.create(numero='AT-002', tipo='residencial', ativo=False)
        self.assertFalse(lote.ativo)


class StrRepresentationTests(TestCase):
    """Testes de representação em string (__str__)"""
    
    def setUp(self):
        self.agora = timezone.now()
        self.lote = Lote.objects.create(numero='STR-001', tipo='residencial')
        self.hidrometro = Hidrometro.objects.create(
            numero='HS001',
            lote=self.lote,
            data_instalacao=self.agora.date()
        )
    
    def test_lote_str(self):
        """Testa representação em string de Lote"""
        str_repr = str(self.lote)
        self.assertIn('STR-001', str_repr)
        self.assertIn('Residencial', str_repr)
    
    def test_hidrometro_str(self):
        """Testa representação em string de Hidrometro"""
        str_repr = str(self.hidrometro)
        self.assertIn('HS001', str_repr)
        self.assertIn('STR-001', str_repr)
    
    def test_leitura_str(self):
        """Testa representação em string de Leitura"""
        leitura = Leitura.objects.create(
            hidrometro=self.hidrometro,
            leitura=Decimal('100.000'),
            data_leitura=self.agora,
            periodo='manha'
        )
        
        str_repr = str(leitura)
        self.assertIn('HS001', str_repr)
        self.assertIn('100', str_repr)


class APIBulkOperationsTests(APITestCase):
    """Testes para operações em lote da API"""
    
    def setUp(self):
        self.agora = timezone.now()
        self.lote = Lote.objects.create(numero='BULK-001', tipo='residencial')
        self.hidrometro1 = Hidrometro.objects.create(
            numero='HB001',
            lote=self.lote,
            data_instalacao=self.agora.date()
        )
        self.hidrometro2 = Hidrometro.objects.create(
            numero='HB002',
            lote=self.lote,
            data_instalacao=self.agora.date()
        )
    
    def test_bulk_leitura_multiplos_hidrometros(self):
        """Testa criação em lote para múltiplos hidrômetros"""
        url = reverse('consumo:leitura-leitura-em-lote')
        
        payload = {
            'leituras': [
                {
                    'hidrometro': self.hidrometro1.id,
                    'leitura': '100.000',
                    'data_leitura': self.agora.isoformat(),
                    'periodo': 'manha'
                },
                {
                    'hidrometro': self.hidrometro2.id,
                    'leitura': '50.000',
                    'data_leitura': self.agora.isoformat(),
                    'periodo': 'manha'
                }
            ]
        }
        
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['criadas'], 2)
        self.assertEqual(response.data['erros'], 0)
