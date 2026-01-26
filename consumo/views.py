from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Avg, Max, Min, Count
from django.http import HttpResponse
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import timedelta, datetime
import json
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.chart import BarChart, PieChart, LineChart, Reference
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import matplotlib
matplotlib.use('Agg')  # Backend sem interface gráfica
import matplotlib.pyplot as plt
import numpy as np

from .models import Lote, Hidrometro, Leitura
from .serializers import (
    LoteSerializer, 
    HidrometroSerializer, 
    LeituraSerializer,
    LeituraCreateSerializer
)


class LoteViewSet(viewsets.ModelViewSet):
    """API endpoint para gerenciar lotes"""
    queryset = Lote.objects.all()
    serializer_class = LoteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero', 'endereco']
    ordering_fields = ['numero', 'tipo', 'criado_em']
    ordering = ['numero']
    
    @action(detail=True, methods=['get'])
    def hidrometros(self, request, pk=None):
        """Retorna todos os hidrômetros de um lote"""
        lote = self.get_object()
        hidrometros = lote.hidrometros.filter(ativo=True)
        serializer = HidrometroSerializer(hidrometros, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def consumo_total(self, request, pk=None):
        """Retorna o consumo total de um lote em um período"""
        lote = self.get_object()
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        
        if not data_inicio or not data_fim:
            return Response(
                {'error': 'Parâmetros data_inicio e data_fim são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        leituras = Leitura.objects.filter(
            hidrometro__lote=lote,
            data_leitura__range=[data_inicio, data_fim]
        )
        
        consumo_total = 0
        for hidrometro in lote.hidrometros.filter(ativo=True):
            leituras_h = leituras.filter(hidrometro=hidrometro).order_by('data_leitura')
            if leituras_h.exists():
                primeira = leituras_h.first()
                ultima = leituras_h.last()
                consumo_total += float(ultima.leitura - primeira.leitura)
        
        return Response({
            'lote': lote.numero,
            'periodo': f'{data_inicio} a {data_fim}',
            'consumo_total_m3': consumo_total
        })


class HidrometroViewSet(viewsets.ModelViewSet):
    """API endpoint para gerenciar hidrômetros"""
    queryset = Hidrometro.objects.all()
    serializer_class = HidrometroSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero', 'lote__numero', 'localizacao']
    ordering_fields = ['numero', 'data_instalacao', 'lote__numero']
    ordering = ['numero']
    
    def get_queryset(self):
        queryset = Hidrometro.objects.all()
        lote_id = self.request.query_params.get('lote', None)
        ativo = self.request.query_params.get('ativo', None)
        
        if lote_id:
            queryset = queryset.filter(lote_id=lote_id)
        if ativo is not None:
            queryset = queryset.filter(ativo=ativo.lower() == 'true')
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def leituras_periodo(self, request, pk=None):
        """Retorna leituras de um hidrômetro em um período"""
        hidrometro = self.get_object()
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        
        if not data_inicio or not data_fim:
            return Response(
                {'error': 'Parâmetros data_inicio e data_fim são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        leituras = hidrometro.leituras.filter(
            data_leitura__range=[data_inicio, data_fim]
        ).order_by('data_leitura')
        
        serializer = LeituraSerializer(leituras, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def estatisticas(self, request, pk=None):
        """Retorna estatísticas de consumo de um hidrômetro"""
        hidrometro = self.get_object()
        dias = int(request.query_params.get('dias', 30))
        
        data_inicio = timezone.now() - timedelta(days=dias)
        leituras = hidrometro.leituras.filter(data_leitura__gte=data_inicio).order_by('data_leitura')
        
        if not leituras.exists():
            return Response({'message': 'Sem leituras no período especificado'})
        
        primeira_leitura = leituras.first()
        ultima_leitura = leituras.last()
        consumo_total = float(ultima_leitura.leitura - primeira_leitura.leitura)
        consumo_medio_dia = consumo_total / dias if dias > 0 else 0
        
        return Response({
            'hidrometro': hidrometro.numero,
            'periodo_dias': dias,
            'total_leituras': leituras.count(),
            'consumo_total_m3': consumo_total,
            'consumo_medio_dia_m3': round(consumo_medio_dia, 3),
            'primeira_leitura': primeira_leitura.leitura,
            'ultima_leitura': ultima_leitura.leitura
        })


class LeituraViewSet(viewsets.ModelViewSet):
    """API endpoint para gerenciar leituras"""
    queryset = Leitura.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['hidrometro__numero', 'hidrometro__lote__numero', 'responsavel']
    ordering_fields = ['data_leitura', 'leitura']
    ordering = ['-data_leitura']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return LeituraCreateSerializer
        return LeituraSerializer
    
    def get_queryset(self):
        queryset = Leitura.objects.all()
        hidrometro_id = self.request.query_params.get('hidrometro', None)
        data_inicio = self.request.query_params.get('data_inicio', None)
        data_fim = self.request.query_params.get('data_fim', None)
        periodo = self.request.query_params.get('periodo', None)
        
        if hidrometro_id:
            queryset = queryset.filter(hidrometro_id=hidrometro_id)
        if data_inicio:
            queryset = queryset.filter(data_leitura__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_leitura__lte=data_fim)
        if periodo:
            queryset = queryset.filter(periodo=periodo)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def ultimas_leituras(self, request):
        """Retorna as últimas leituras de todos os hidrômetros ativos"""
        hidrometros = Hidrometro.objects.filter(ativo=True)
        resultado = []
        
        for hidrometro in hidrometros:
            ultima_leitura = hidrometro.leituras.order_by('-data_leitura').first()
            if ultima_leitura:
                resultado.append({
                    'hidrometro': hidrometro.numero,
                    'lote': hidrometro.lote.numero,
                    'leitura': float(ultima_leitura.leitura),
                    'data_leitura': ultima_leitura.data_leitura,
                    'periodo': ultima_leitura.periodo
                })
        
        return Response(resultado)
    
    @action(detail=False, methods=['post'])
    def leitura_em_lote(self, request):
        """Permite criar múltiplas leituras de uma vez"""
        leituras_data = request.data.get('leituras', [])
        
        if not leituras_data:
            return Response(
                {'error': 'Nenhuma leitura fornecida'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        criadas = []
        erros = []
        
        for leitura_data in leituras_data:
            serializer = LeituraCreateSerializer(data=leitura_data)
            if serializer.is_valid():
                serializer.save()
                criadas.append(serializer.data)
            else:
                erros.append({
                    'dados': leitura_data,
                    'erros': serializer.errors
                })
        
        return Response({
            'criadas': len(criadas),
            'erros': len(erros),
            'leituras_criadas': criadas,
            'leituras_com_erro': erros
        }, status=status.HTTP_201_CREATED if criadas else status.HTTP_400_BAD_REQUEST)


# Views HTML para interface web
def dashboard(request):
    """Dashboard principal"""
    total_lotes = Lote.objects.filter(ativo=True).count()
    total_hidrometros = Hidrometro.objects.filter(ativo=True).count()
    
    hoje = timezone.now().date()
    leituras_hoje = Leitura.objects.filter(data_leitura__date=hoje).count()
    
    context = {
        'total_lotes': total_lotes,
        'total_hidrometros': total_hidrometros,
        'leituras_hoje': leituras_hoje,
    }
    
    return render(request, 'consumo/dashboard.html', context)


def listar_hidrometros(request):
    """Lista todos os hidrômetros"""
    hidrometros = Hidrometro.objects.filter(ativo=True).select_related('lote')
    
    context = {
        'hidrometros': hidrometros,
    }
    
    return render(request, 'consumo/listar_hidrometros.html', context)


def listar_leituras(request):
    """Lista todas as leituras"""
    leituras = Leitura.objects.all().select_related('hidrometro__lote').order_by('-data_leitura')
    
    context = {
        'leituras': leituras,
    }
    
    return render(request, 'consumo/listar_leituras.html', context)


def registrar_leitura(request):
    """Formulário para registrar leituras"""
    hidrometros = Hidrometro.objects.filter(ativo=True).select_related('lote')
    
    context = {
        'hidrometros': hidrometros,
    }
    
    return render(request, 'consumo/registrar_leitura.html', context)


def detalhes_hidrometro(request, hidrometro_id):
    """Página com detalhes e histórico de leituras do hidrômetro"""
    hidrometro = get_object_or_404(Hidrometro, id=hidrometro_id)
    leituras = hidrometro.leituras.all().order_by('-data_leitura')
    
    context = {
        'hidrometro': hidrometro,
        'leituras': leituras,
    }
    
    return render(request, 'consumo/detalhes_hidrometro.html', context)


def graficos_consumo(request):
    """Página com gráficos de consumo do condomínio dos últimos 30 dias."""

    hoje = timezone.now()
    dias_filtrados = 30
    data_inicio = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    data_fim = hoje

    periodo_label = f"Últimos {dias_filtrados} dias"

    dados_graficos = {
        'consumo_por_dia': [],
        'consumo_mes': [],
        'consumo_periodo': {'manha': 0, 'tarde': 0},
        'consumo_total_ano': 0.0,
        'top_lotes': [],
        'periodo_label': periodo_label,
    }

    hidrometros_qs = Hidrometro.objects.filter(ativo=True).select_related('lote')

    # ================= CONSUMO POR DIA (NO PERÍODO) =================
    consumo_diario = {}
    datas_periodo = []
    dia_cursor = data_inicio
    while dia_cursor.date() <= data_fim.date():
        consumo_diario[dia_cursor.date()] = 0.0
        datas_periodo.append(dia_cursor.date())
        dia_cursor += timedelta(days=1)

    consumo_mensal = {}
    consumo_periodo_manha = 0.0
    consumo_periodo_tarde = 0.0
    consumo_total = 0.0
    consumo_por_lote = {}

    for hidrometro in hidrometros_qs:
        leituras = hidrometro.leituras.filter(
            data_leitura__gte=data_inicio,
            data_leitura__lte=data_fim
        ).order_by('data_leitura')

        if not leituras.exists():
            continue

        for i in range(1, len(leituras)):
            leitura_atual = leituras[i]
            leitura_anterior = leituras[i - 1]

            # Consumo diário: considera a diferença entre leituras consecutivas
            consumo_m3 = float(leitura_atual.leitura - leitura_anterior.leitura)
            if consumo_m3 < 0:
                continue

            consumo_litros = consumo_m3 * 1000
            dia = leitura_atual.data_leitura.date()
            if dia in consumo_diario:
                consumo_diario[dia] += consumo_litros

            consumo_total += consumo_litros

            if leitura_atual.periodo == 'manha':
                consumo_periodo_manha += consumo_litros
            elif leitura_atual.periodo == 'tarde':
                consumo_periodo_tarde += consumo_litros

            mes_key = (leitura_atual.data_leitura.year, leitura_atual.data_leitura.month)
            consumo_mensal.setdefault(mes_key, 0.0)
            consumo_mensal[mes_key] += consumo_litros

            numero_lote = leitura_atual.hidrometro.lote.numero
            consumo_por_lote.setdefault(numero_lote, 0.0)
            consumo_por_lote[numero_lote] += consumo_litros

    for dia in datas_periodo:
        dados_graficos['consumo_por_dia'].append({
            'dia': dia.day,
            'label': dia.strftime('%d/%m'),
            'consumo_litros': round(consumo_diario[dia], 2)
        })

    nomes_meses = [
        'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
        'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'
    ]

    consumo_mes_ordenado = sorted(consumo_mensal.items(), key=lambda x: (x[0][0], x[0][1]))
    for (ano, mes), valor in consumo_mes_ordenado:
        dados_graficos['consumo_mes'].append({
            'mes': mes,
            'mes_nome': f"{nomes_meses[mes - 1]}/{str(ano)[-2:]}",
            'consumo_litros': round(valor, 2)
        })

    dados_graficos['consumo_total_ano'] = round(consumo_total, 2)
    dados_graficos['consumo_periodo']['manha'] = round(consumo_periodo_manha, 2)
    dados_graficos['consumo_periodo']['tarde'] = round(consumo_periodo_tarde, 2)

    top_lotes = sorted(consumo_por_lote.items(), key=lambda x: x[1], reverse=True)[:10]
    dados_graficos['top_lotes'] = [
        {'lote': lote, 'consumo_litros': round(consumo, 2)} for lote, consumo in top_lotes
    ]

    lotes_disponiveis = Lote.objects.filter(ativo=True).order_by('numero')

    context = {
        'dados_graficos': dados_graficos,
        'hidrometros': hidrometros_qs,
        'lotes': lotes_disponiveis,
    }

    return render(request, 'consumo/graficos_consumo.html', context)


def graficos_lote(request, lote_id):
    """Página com gráficos de consumo específicos de um lote"""
    lote = get_object_or_404(Lote, id=lote_id)
    
    # Obter o mês e ano atual
    hoje = timezone.now()
    ano_atual = hoje.year
    mes_atual = hoje.month
    primeiro_dia_mes = hoje.replace(day=1)
    
    # Estrutura de dados para os gráficos
    dados_graficos = {
        'lote': lote.numero,
        'tipo': lote.get_tipo_display(),
        'mes': f"{primeiro_dia_mes.strftime('%B de %Y')}",
        'consumo_por_dia': [],
        'consumo_mes': [],
        'consumo_periodo': {'manha': 0, 'tarde': 0},
    }
    
    # Obter todos os hidrômetros do lote
    hidrometros = lote.hidrometros.filter(ativo=True)
    
    if not hidrometros.exists():
        context = {
            'lote': lote,
            'dados_graficos': dados_graficos,
            'sem_dados': True,
        }
        return render(request, 'consumo/graficos_lote.html', context)
    
    # Nomes dos meses
    nomes_meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    
    # Calcular o último dia do mês atual
    if mes_atual == 12:
        ultimo_dia_mes = primeiro_dia_mes.replace(year=ano_atual + 1, month=1, day=1) - timedelta(days=1)
    else:
        ultimo_dia_mes = primeiro_dia_mes.replace(month=mes_atual + 1, day=1) - timedelta(days=1)
    
    # ============ CONSUMO POR DIA DO MÊS ATUAL ============
    consumo_diario = {}
    for dia in range(1, ultimo_dia_mes.day + 1):
        consumo_diario[dia] = 0.0
    
    for hidrometro in hidrometros:
        leituras = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_mes,
            data_leitura__lte=ultimo_dia_mes
        ).order_by('data_leitura')
        
        if leituras.exists():
            for i in range(1, len(leituras)):
                leitura_atual = leituras[i]
                leitura_anterior = leituras[i - 1]
                
                # Considerar consumo apenas se está no mesmo dia
                if leitura_atual.data_leitura.date() == leitura_anterior.data_leitura.date():
                    dia = leitura_atual.data_leitura.day
                    consumo_m3 = float(leitura_atual.leitura - leitura_anterior.leitura)
                    consumo_litros = consumo_m3 * 1000
                    consumo_diario[dia] += consumo_litros
    
    # Montar dados de consumo por dia
    for dia in range(1, ultimo_dia_mes.day + 1):
        dados_graficos['consumo_por_dia'].append({
            'dia': dia,
            'consumo_litros': round(consumo_diario[dia], 2)
        })
    
    # ============ CONSUMO POR MÊS DO ANO (para gráfico anual) ============
    consumo_mensal = {}
    for mes in range(1, 13):
        consumo_mensal[mes] = 0.0
        
        # Determinar primeiro e último dia do mês
        if mes == 12:
            primeiro_dia_mes_loop = hoje.replace(month=mes, day=1)
            ultimo_dia_mes_loop = primeiro_dia_mes_loop.replace(year=ano_atual + 1, month=1, day=1) - timedelta(days=1)
        else:
            primeiro_dia_mes_loop = hoje.replace(month=mes, day=1)
            ultimo_dia_mes_loop = primeiro_dia_mes_loop.replace(month=mes + 1, day=1) - timedelta(days=1)
        
        # Se o mês ainda não começou, pular
        if primeiro_dia_mes_loop > hoje:
            continue
        
        # Ajustar o último dia para hoje se o mês atual não terminou
        if mes == hoje.month:
            ultimo_dia_mes_loop = hoje
        
        # Calcular consumo de cada hidrometro neste mês
        for hidrometro in hidrometros:
            leituras_mes = hidrometro.leituras.filter(
                data_leitura__gte=primeiro_dia_mes_loop,
                data_leitura__lte=ultimo_dia_mes_loop
            ).order_by('data_leitura')
            
            if leituras_mes.count() >= 2:
                primeira = leituras_mes.first()
                ultima = leituras_mes.last()
                consumo_m3 = float(ultima.leitura - primeira.leitura)
                consumo_litros = consumo_m3 * 1000
                consumo_mensal[mes] += consumo_litros
    
    # ============ CONSUMO TOTAL DO ANO E POR MÊS ============
    consumo_total_ano = 0.0
    for mes in range(1, 13):
        consumo_total_ano += consumo_mensal[mes]
    
    # Adicionar dados de consumo por mês (sem acumulado)
    for mes in range(1, 13):
        dados_graficos['consumo_mes'].append({
            'mes': mes,
            'mes_nome': nomes_meses[mes - 1],
            'consumo_litros': round(consumo_mensal[mes], 2)
        })
    
    # ============ CONSUMO POR PERÍODO (MANHÃ/TARDE) - ANO INTEIRO ============
    consumo_periodo_manha = 0.0
    consumo_periodo_tarde = 0.0
    
    primeiro_dia_ano = hoje.replace(month=1, day=1)
    ultimo_dia_ano = hoje.replace(month=12, day=31)
    
    for hidrometro in hidrometros:
        leituras_manha = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_ano,
            data_leitura__lte=ultimo_dia_ano,
            periodo='manha'
        ).order_by('data_leitura')
        
        leituras_tarde = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_ano,
            data_leitura__lte=ultimo_dia_ano,
            periodo='tarde'
        ).order_by('data_leitura')
        
        # Calcular consumo da manhã
        if leituras_manha.count() >= 2:
            primeira = leituras_manha.first()
            ultima = leituras_manha.last()
            consumo_m3 = float(ultima.leitura - primeira.leitura)
            consumo_litros = consumo_m3 * 1000
            consumo_periodo_manha += consumo_litros
        
        # Calcular consumo da tarde
        if leituras_tarde.count() >= 2:
            primeira = leituras_tarde.first()
            ultima = leituras_tarde.last()
            consumo_m3 = float(ultima.leitura - primeira.leitura)
            consumo_litros = consumo_m3 * 1000
            consumo_periodo_tarde += consumo_litros
    
    dados_graficos['consumo_periodo'] = {
        'manha': round(consumo_periodo_manha, 2),
        'tarde': round(consumo_periodo_tarde, 2),
    }
    
    dados_graficos['consumo_total_ano'] = round(consumo_total_ano, 2)
    
    context = {
        'lote': lote,
        'dados_graficos': dados_graficos,
        'consumo_total_mes': round(consumo_total_ano, 2),
        'hidrometros': hidrometros,
    }
    
    return render(request, 'consumo/graficos_lote.html', context)


def exportar_graficos_consumo_pdf(request):
    """Exporta os gráficos de consumo do condomínio em PDF"""
    from django.template.loader import render_to_string
    
    # Obter dados dos gráficos (mesma lógica da view graficos_consumo)
    hoje = timezone.now()
    ano_atual = hoje.year
    mes_atual = hoje.month
    primeiro_dia_mes = hoje.replace(day=1)
    
    # Buscar todos os hidrômetros ativos
    hidrometros = Hidrometro.objects.filter(ativo=True).select_related('lote')
    
    # Calcular último dia do mês
    if mes_atual == 12:
        ultimo_dia_mes = primeiro_dia_mes.replace(year=ano_atual + 1, month=1, day=1) - timedelta(days=1)
    else:
        ultimo_dia_mes = primeiro_dia_mes.replace(month=mes_atual + 1, day=1) - timedelta(days=1)
    
    # Calcular consumo diário
    consumo_diario = {}
    for dia in range(1, ultimo_dia_mes.day + 1):
        consumo_diario[dia] = 0.0
    
    for hidrometro in hidrometros:
        leituras = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_mes,
            data_leitura__lte=ultimo_dia_mes
        ).order_by('data_leitura')
        
        if leituras.exists():
            for i in range(1, len(leituras)):
                leitura_atual = leituras[i]
                leitura_anterior = leituras[i - 1]
                
                if leitura_atual.data_leitura.date() == leitura_anterior.data_leitura.date():
                    dia = leitura_atual.data_leitura.day
                    consumo_m3 = float(leitura_atual.leitura - leitura_anterior.leitura)
                    consumo_litros = consumo_m3 * 1000
                    consumo_diario[dia] += consumo_litros
    
    # Calcular consumo mensal
    nomes_meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    
    consumo_mensal = {}
    for mes in range(1, 13):
        consumo_mensal[mes] = 0.0
        
        if mes == 12:
            primeiro_dia_mes_loop = hoje.replace(month=mes, day=1)
            ultimo_dia_mes_loop = primeiro_dia_mes_loop.replace(year=ano_atual + 1, month=1, day=1) - timedelta(days=1)
        else:
            primeiro_dia_mes_loop = hoje.replace(month=mes, day=1)
            ultimo_dia_mes_loop = primeiro_dia_mes_loop.replace(month=mes + 1, day=1) - timedelta(days=1)
        
        if primeiro_dia_mes_loop > hoje:
            continue
        
        if mes == hoje.month:
            ultimo_dia_mes_loop = hoje
        
        for hidrometro in hidrometros:
            leituras_mes = hidrometro.leituras.filter(
                data_leitura__gte=primeiro_dia_mes_loop,
                data_leitura__lte=ultimo_dia_mes_loop
            ).order_by('data_leitura')
            
            if leituras_mes.count() >= 2:
                primeira = leituras_mes.first()
                ultima = leituras_mes.last()
                consumo_m3 = float(ultima.leitura - primeira.leitura)
                consumo_litros = consumo_m3 * 1000
                consumo_mensal[mes] += consumo_litros
    
    # Calcular consumo total do ano
    consumo_total_ano = sum(consumo_mensal.values())
    
    # Calcular consumo por período
    primeiro_dia_ano = hoje.replace(month=1, day=1)
    ultimo_dia_ano = hoje.replace(month=12, day=31)
    
    consumo_periodo_manha = 0.0
    consumo_periodo_tarde = 0.0
    
    for hidrometro in hidrometros:
        leituras_manha = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_ano,
            data_leitura__lte=ultimo_dia_ano,
            periodo='manha'
        ).order_by('data_leitura')
        
        leituras_tarde = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_ano,
            data_leitura__lte=ultimo_dia_ano,
            periodo='tarde'
        ).order_by('data_leitura')
        
        if leituras_manha.count() >= 2:
            primeira = leituras_manha.first()
            ultima = leituras_manha.last()
            consumo_m3 = float(ultima.leitura - primeira.leitura)
            consumo_litros = consumo_m3 * 1000
            consumo_periodo_manha += consumo_litros
        
        if leituras_tarde.count() >= 2:
            primeira = leituras_tarde.first()
            ultima = leituras_tarde.last()
            consumo_m3 = float(ultima.leitura - primeira.leitura)
            consumo_litros = consumo_m3 * 1000
            consumo_periodo_tarde += consumo_litros
    
    # Top 10 lotes
    lotes_consumo = []
    for lote in Lote.objects.filter(ativo=True):
        consumo_lote = 0.0
        hidrometros_lote = lote.hidrometros.filter(ativo=True)
        
        for hidrometro in hidrometros_lote:
            leituras_ano = hidrometro.leituras.filter(
                data_leitura__gte=primeiro_dia_ano,
                data_leitura__lte=ultimo_dia_ano
            ).order_by('data_leitura')
            
            if leituras_ano.count() >= 2:
                primeira = leituras_ano.first()
                ultima = leituras_ano.last()
                consumo_m3 = float(ultima.leitura - primeira.leitura)
                consumo_litros = consumo_m3 * 1000
                consumo_lote += consumo_litros
        
        if consumo_lote > 0:
            lotes_consumo.append({
                'lote': lote,
                'consumo': consumo_lote
            })
    
    lotes_consumo.sort(key=lambda x: x['consumo'], reverse=True)
    top_lotes = lotes_consumo[:10]
    
    # Criar PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                          rightMargin=30, leftMargin=30,
                          topMargin=30, bottomMargin=18)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilo do título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Título
    elements.append(Paragraph(f"Relatório de Consumo de Água - {ano_atual}", title_style))
    elements.append(Paragraph(f"Gerado em: {hoje.strftime('%d/%m/%Y %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Resumo Geral
    elements.append(Paragraph("📊 Resumo Geral", heading_style))
    
    resumo_data = [
        ['Indicador', 'Valor'],
        ['Consumo Total no Ano', f'{consumo_total_ano:,.0f} L'],
        ['Consumo Período Manhã', f'{consumo_periodo_manha:,.0f} L'],
        ['Consumo Período Tarde', f'{consumo_periodo_tarde:,.0f} L'],
        ['Hidrometros Ativos', str(hidrometros.count())],
        ['Lotes Ativos', str(Lote.objects.filter(ativo=True).count())],
    ]
    
    resumo_table = Table(resumo_data, colWidths=[3*inch, 2*inch])
    resumo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(resumo_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # Consumo Mensal
    elements.append(Paragraph("📅 Consumo Mensal", heading_style))
    
    mensal_data = [['Mês', 'Consumo (L)']]
    for mes in range(1, 13):
        mensal_data.append([nomes_meses[mes - 1], f'{consumo_mensal[mes]:,.2f}'])
    
    mensal_table = Table(mensal_data, colWidths=[2*inch, 2*inch])
    mensal_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(mensal_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Gráfico de Consumo Mensal
    plt.figure(figsize=(10, 5))
    meses_labels = [nomes_meses[m-1] for m in range(1, 13)]
    valores_mensais = [consumo_mensal[m] for m in range(1, 13)]
    plt.bar(meses_labels, valores_mensais, color='#27ae60', alpha=0.7)
    plt.title('Consumo Mensal (Litros)', fontsize=14, fontweight='bold')
    plt.xlabel('Mês', fontsize=11)
    plt.ylabel('Consumo (L)', fontsize=11)
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    # Salvar gráfico em buffer
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
    img_buffer.seek(0)
    plt.close()
    
    # Adicionar imagem ao PDF
    img = Image(img_buffer, width=7*inch, height=3.5*inch)
    elements.append(img)
    elements.append(PageBreak())
    
    # Top 10 Lotes
    elements.append(Paragraph("🏆 Top 10 Lotes com Maior Consumo", heading_style))
    
    top_data = [['Posição', 'Lote', 'Tipo', 'Consumo (L)']]
    for idx, item in enumerate(top_lotes, 1):
        lote = item['lote']
        consumo = item['consumo']
        top_data.append([
            str(idx),
            lote.numero,
            lote.get_tipo_display(),
            f'{consumo:,.2f}'
        ])
    
    top_table = Table(top_data, colWidths=[1*inch, 1.5*inch, 1.5*inch, 2*inch])
    top_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(top_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Gráfico Top 10 Lotes
    if top_lotes:
        plt.figure(figsize=(10, 5))
        lotes_labels = [item['lote'].numero for item in top_lotes]
        lotes_valores = [item['consumo'] for item in top_lotes]
        plt.barh(lotes_labels[::-1], lotes_valores[::-1], color='#e74c3c', alpha=0.7)
        plt.title('Top 10 Lotes - Consumo no Ano (Litros)', fontsize=14, fontweight='bold')
        plt.xlabel('Consumo (L)', fontsize=11)
        plt.ylabel('Lote', fontsize=11)
        plt.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        
        # Salvar gráfico em buffer
        img_buffer_top = io.BytesIO()
        plt.savefig(img_buffer_top, format='png', dpi=150, bbox_inches='tight')
        img_buffer_top.seek(0)
        plt.close()
        
        # Adicionar imagem ao PDF
        img_top = Image(img_buffer_top, width=7*inch, height=3.5*inch)
        elements.append(img_top)
    
    elements.append(Spacer(1, 0.3*inch))
    
    # Gráfico de Consumo por Período (Pizza)
    plt.figure(figsize=(7, 7))
    labels_periodo = ['Manhã', 'Tarde']
    valores_periodo = [consumo_periodo_manha, consumo_periodo_tarde]
    colors_periodo = ['#3498db', '#e67e22']
    explode = (0.05, 0.05)
    
    plt.pie(valores_periodo, labels=labels_periodo, autopct='%1.1f%%',
            startangle=90, colors=colors_periodo, explode=explode,
            textprops={'fontsize': 12, 'fontweight': 'bold'})
    plt.title('Distribuição de Consumo por Período', fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    
    # Salvar gráfico em buffer
    img_buffer_periodo = io.BytesIO()
    plt.savefig(img_buffer_periodo, format='png', dpi=150, bbox_inches='tight')
    img_buffer_periodo.seek(0)
    plt.close()
    
    # Adicionar imagem ao PDF
    img_periodo = Image(img_buffer_periodo, width=5*inch, height=5*inch)
    elements.append(img_periodo)
    
    # Construir PDF
    doc.build(elements)
    
    # Preparar resposta
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_consumo_condominio_{hoje.strftime("%Y%m%d")}.pdf"'
    
    return response


def exportar_graficos_consumo_excel(request):
    """Exporta os gráficos de consumo do condomínio em Excel com gráficos"""
    # Obter dados dos gráficos (mesma lógica da view graficos_consumo)
    hoje = timezone.now()
    ano_atual = hoje.year
    mes_atual = hoje.month
    primeiro_dia_mes = hoje.replace(day=1)
    
    # Buscar todos os hidrômetros ativos
    hidrometros = Hidrometro.objects.filter(ativo=True).select_related('lote')
    
    # Calcular último dia do mês
    if mes_atual == 12:
        ultimo_dia_mes = primeiro_dia_mes.replace(year=ano_atual + 1, month=1, day=1) - timedelta(days=1)
    else:
        ultimo_dia_mes = primeiro_dia_mes.replace(month=mes_atual + 1, day=1) - timedelta(days=1)
    
    # Calcular consumo diário
    consumo_diario = {}
    for dia in range(1, ultimo_dia_mes.day + 1):
        consumo_diario[dia] = 0.0
    
    for hidrometro in hidrometros:
        leituras = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_mes,
            data_leitura__lte=ultimo_dia_mes
        ).order_by('data_leitura')
        
        if leituras.exists():
            for i in range(1, len(leituras)):
                leitura_atual = leituras[i]
                leitura_anterior = leituras[i - 1]
                
                if leitura_atual.data_leitura.date() == leitura_anterior.data_leitura.date():
                    dia = leitura_atual.data_leitura.day
                    consumo_m3 = float(leitura_atual.leitura - leitura_anterior.leitura)
                    consumo_litros = consumo_m3 * 1000
                    consumo_diario[dia] += consumo_litros
    
    # Calcular consumo mensal
    nomes_meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    
    consumo_mensal = {}
    for mes in range(1, 13):
        consumo_mensal[mes] = 0.0
        
        if mes == 12:
            primeiro_dia_mes_loop = hoje.replace(month=mes, day=1)
            ultimo_dia_mes_loop = primeiro_dia_mes_loop.replace(year=ano_atual + 1, month=1, day=1) - timedelta(days=1)
        else:
            primeiro_dia_mes_loop = hoje.replace(month=mes, day=1)
            ultimo_dia_mes_loop = primeiro_dia_mes_loop.replace(month=mes + 1, day=1) - timedelta(days=1)
        
        if primeiro_dia_mes_loop > hoje:
            continue
        
        if mes == hoje.month:
            ultimo_dia_mes_loop = hoje
        
        for hidrometro in hidrometros:
            leituras_mes = hidrometro.leituras.filter(
                data_leitura__gte=primeiro_dia_mes_loop,
                data_leitura__lte=ultimo_dia_mes_loop
            ).order_by('data_leitura')
            
            if leituras_mes.count() >= 2:
                primeira = leituras_mes.first()
                ultima = leituras_mes.last()
                consumo_m3 = float(ultima.leitura - primeira.leitura)
                consumo_litros = consumo_m3 * 1000
                consumo_mensal[mes] += consumo_litros
    
    # Calcular consumo total do ano
    consumo_total_ano = sum(consumo_mensal.values())
    
    # Calcular consumo por período
    primeiro_dia_ano = hoje.replace(month=1, day=1)
    ultimo_dia_ano = hoje.replace(month=12, day=31)
    
    consumo_periodo_manha = 0.0
    consumo_periodo_tarde = 0.0
    
    for hidrometro in hidrometros:
        leituras_manha = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_ano,
            data_leitura__lte=ultimo_dia_ano,
            periodo='manha'
        ).order_by('data_leitura')
        
        leituras_tarde = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_ano,
            data_leitura__lte=ultimo_dia_ano,
            periodo='tarde'
        ).order_by('data_leitura')
        
        if leituras_manha.count() >= 2:
            primeira = leituras_manha.first()
            ultima = leituras_manha.last()
            consumo_m3 = float(ultima.leitura - primeira.leitura)
            consumo_litros = consumo_m3 * 1000
            consumo_periodo_manha += consumo_litros
        
        if leituras_tarde.count() >= 2:
            primeira = leituras_tarde.first()
            ultima = leituras_tarde.last()
            consumo_m3 = float(ultima.leitura - primeira.leitura)
            consumo_litros = consumo_m3 * 1000
            consumo_periodo_tarde += consumo_litros
    
    # Top 10 lotes
    lotes_consumo = []
    for lote in Lote.objects.filter(ativo=True):
        consumo_lote = 0.0
        hidrometros_lote = lote.hidrometros.filter(ativo=True)
        
        for hidrometro in hidrometros_lote:
            leituras_ano = hidrometro.leituras.filter(
                data_leitura__gte=primeiro_dia_ano,
                data_leitura__lte=ultimo_dia_ano
            ).order_by('data_leitura')
            
            if leituras_ano.count() >= 2:
                primeira = leituras_ano.first()
                ultima = leituras_ano.last()
                consumo_m3 = float(ultima.leitura - primeira.leitura)
                consumo_litros = consumo_m3 * 1000
                consumo_lote += consumo_litros
        
        if consumo_lote > 0:
            lotes_consumo.append({
                'lote': lote,
                'consumo': consumo_lote
            })
    
    lotes_consumo.sort(key=lambda x: x['consumo'], reverse=True)
    top_lotes = lotes_consumo[:10]
    
    # Criar Excel
    wb = Workbook()
    
    # Aba: Resumo
    ws_resumo = wb.active
    ws_resumo.title = "Resumo"
    
    # Título
    ws_resumo['A1'] = f'Relatório de Consumo de Água - {ano_atual}'
    ws_resumo['A1'].font = Font(size=16, bold=True, color='FFFFFF')
    ws_resumo['A1'].fill = PatternFill(start_color='3498db', end_color='3498db', fill_type='solid')
    ws_resumo['A1'].alignment = Alignment(horizontal='center')
    ws_resumo.merge_cells('A1:C1')
    
    ws_resumo['A2'] = f'Gerado em: {hoje.strftime("%d/%m/%Y %H:%M")}'
    ws_resumo['A2'].alignment = Alignment(horizontal='center')
    ws_resumo.merge_cells('A2:C2')
    
    # Dados resumo
    ws_resumo['A4'] = 'Indicador'
    ws_resumo['B4'] = 'Valor'
    ws_resumo['A4'].font = Font(bold=True)
    ws_resumo['B4'].font = Font(bold=True)
    
    resumo_dados = [
        ['Consumo Total no Ano', f'{consumo_total_ano:,.0f} L'],
        ['Consumo Período Manhã', f'{consumo_periodo_manha:,.0f} L'],
        ['Consumo Período Tarde', f'{consumo_periodo_tarde:,.0f} L'],
        ['Hidrometros Ativos', hidrometros.count()],
        ['Lotes Ativos', Lote.objects.filter(ativo=True).count()],
    ]
    
    for idx, (indicador, valor) in enumerate(resumo_dados, start=5):
        ws_resumo[f'A{idx}'] = indicador
        ws_resumo[f'B{idx}'] = valor
    
    ws_resumo.column_dimensions['A'].width = 30
    ws_resumo.column_dimensions['B'].width = 20
    
    # Aba: Consumo Mensal
    ws_mensal = wb.create_sheet("Consumo Mensal")
    
    ws_mensal['A1'] = 'Mês'
    ws_mensal['B1'] = 'Consumo (L)'
    ws_mensal['A1'].font = Font(bold=True)
    ws_mensal['B1'].font = Font(bold=True)
    
    for mes in range(1, 13):
        ws_mensal[f'A{mes + 1}'] = nomes_meses[mes - 1]
        ws_mensal[f'B{mes + 1}'] = round(consumo_mensal[mes], 2)
    
    # Adicionar gráfico
    chart = BarChart()
    chart.title = "Consumo Mensal de Água"
    chart.y_axis.title = "Consumo (Litros)"
    chart.x_axis.title = "Mês"
    
    data = Reference(ws_mensal, min_col=2, min_row=1, max_row=13)
    cats = Reference(ws_mensal, min_col=1, min_row=2, max_row=13)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.height = 10
    chart.width = 20
    
    ws_mensal.add_chart(chart, "D2")
    
    ws_mensal.column_dimensions['A'].width = 15
    ws_mensal.column_dimensions['B'].width = 15
    
    # Aba: Top 10 Lotes
    ws_top = wb.create_sheet("Top 10 Lotes")
    
    ws_top['A1'] = 'Posição'
    ws_top['B1'] = 'Lote'
    ws_top['C1'] = 'Tipo'
    ws_top['D1'] = 'Consumo (L)'
    
    for col in ['A1', 'B1', 'C1', 'D1']:
        ws_top[col].font = Font(bold=True)
    
    for idx, item in enumerate(top_lotes, 1):
        lote = item['lote']
        consumo = item['consumo']
        ws_top[f'A{idx + 1}'] = idx
        ws_top[f'B{idx + 1}'] = lote.numero
        ws_top[f'C{idx + 1}'] = lote.get_tipo_display()
        ws_top[f'D{idx + 1}'] = round(consumo, 2)
    
    # Adicionar gráfico
    chart_top = BarChart()
    chart_top.title = "Top 10 Lotes - Maior Consumo"
    chart_top.y_axis.title = "Consumo (Litros)"
    chart_top.x_axis.title = "Lote"
    
    data_top = Reference(ws_top, min_col=4, min_row=1, max_row=len(top_lotes) + 1)
    cats_top = Reference(ws_top, min_col=2, min_row=2, max_row=len(top_lotes) + 1)
    chart_top.add_data(data_top, titles_from_data=True)
    chart_top.set_categories(cats_top)
    chart_top.height = 10
    chart_top.width = 20
    
    ws_top.add_chart(chart_top, "F2")
    
    for col in ['A', 'B', 'C', 'D']:
        ws_top.column_dimensions[col].width = 15
    
    # Aba: Consumo por Período
    ws_periodo = wb.create_sheet("Consumo por Período")
    
    ws_periodo['A1'] = 'Período'
    ws_periodo['B1'] = 'Consumo (L)'
    ws_periodo['A1'].font = Font(bold=True)
    ws_periodo['B1'].font = Font(bold=True)
    
    ws_periodo['A2'] = 'Manhã'
    ws_periodo['B2'] = round(consumo_periodo_manha, 2)
    ws_periodo['A3'] = 'Tarde'
    ws_periodo['B3'] = round(consumo_periodo_tarde, 2)
    
    # Adicionar gráfico de pizza
    pie = PieChart()
    pie.title = "Distribuição de Consumo por Período"
    
    data_pie = Reference(ws_periodo, min_col=2, min_row=1, max_row=3)
    cats_pie = Reference(ws_periodo, min_col=1, min_row=2, max_row=3)
    pie.add_data(data_pie, titles_from_data=True)
    pie.set_categories(cats_pie)
    pie.height = 10
    pie.width = 15
    
    ws_periodo.add_chart(pie, "D2")
    
    ws_periodo.column_dimensions['A'].width = 15
    ws_periodo.column_dimensions['B'].width = 15
    
    # Salvar e retornar
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="relatorio_consumo_condominio_{hoje.strftime("%Y%m%d")}.xlsx"'
    
    return response


def exportar_graficos_lote_pdf(request, lote_id):
    """Exporta os gráficos de consumo de um lote específico em PDF"""
    lote = get_object_or_404(Lote, id=lote_id)
    
    # Obter dados do lote (mesma lógica da view graficos_lote)
    hoje = timezone.now()
    ano_atual = hoje.year
    mes_atual = hoje.month
    primeiro_dia_mes = hoje.replace(day=1)
    
    hidrometros = lote.hidrometros.filter(ativo=True)
    
    if not hidrometros.exists():
        return HttpResponse("Nenhum hidrômetro ativo encontrado para este lote.", status=404)
    
    # Calcular último dia do mês
    if mes_atual == 12:
        ultimo_dia_mes = primeiro_dia_mes.replace(year=ano_atual + 1, month=1, day=1) - timedelta(days=1)
    else:
        ultimo_dia_mes = primeiro_dia_mes.replace(month=mes_atual + 1, day=1) - timedelta(days=1)
    
    # Calcular consumo diário
    consumo_diario = {}
    for dia in range(1, ultimo_dia_mes.day + 1):
        consumo_diario[dia] = 0.0
    
    for hidrometro in hidrometros:
        leituras = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_mes,
            data_leitura__lte=ultimo_dia_mes
        ).order_by('data_leitura')
        
        if leituras.exists():
            for i in range(1, len(leituras)):
                leitura_atual = leituras[i]
                leitura_anterior = leituras[i - 1]
                
                if leitura_atual.data_leitura.date() == leitura_anterior.data_leitura.date():
                    dia = leitura_atual.data_leitura.day
                    consumo_m3 = float(leitura_atual.leitura - leitura_anterior.leitura)
                    consumo_litros = consumo_m3 * 1000
                    consumo_diario[dia] += consumo_litros
    
    # Calcular consumo mensal
    nomes_meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    
    consumo_mensal = {}
    for mes in range(1, 13):
        consumo_mensal[mes] = 0.0
        
        if mes == 12:
            primeiro_dia_mes_loop = hoje.replace(month=mes, day=1)
            ultimo_dia_mes_loop = primeiro_dia_mes_loop.replace(year=ano_atual + 1, month=1, day=1) - timedelta(days=1)
        else:
            primeiro_dia_mes_loop = hoje.replace(month=mes, day=1)
            ultimo_dia_mes_loop = primeiro_dia_mes_loop.replace(month=mes + 1, day=1) - timedelta(days=1)
        
        if primeiro_dia_mes_loop > hoje:
            continue
        
        if mes == hoje.month:
            ultimo_dia_mes_loop = hoje
        
        for hidrometro in hidrometros:
            leituras_mes = hidrometro.leituras.filter(
                data_leitura__gte=primeiro_dia_mes_loop,
                data_leitura__lte=ultimo_dia_mes_loop
            ).order_by('data_leitura')
            
            if leituras_mes.count() >= 2:
                primeira = leituras_mes.first()
                ultima = leituras_mes.last()
                consumo_m3 = float(ultima.leitura - primeira.leitura)
                consumo_litros = consumo_m3 * 1000
                consumo_mensal[mes] += consumo_litros
    
    # Calcular consumo total do ano
    consumo_total_ano = sum(consumo_mensal.values())
    
    # Calcular consumo por período
    primeiro_dia_ano = hoje.replace(month=1, day=1)
    ultimo_dia_ano = hoje.replace(month=12, day=31)
    
    consumo_periodo_manha = 0.0
    consumo_periodo_tarde = 0.0
    
    for hidrometro in hidrometros:
        leituras_manha = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_ano,
            data_leitura__lte=ultimo_dia_ano,
            periodo='manha'
        ).order_by('data_leitura')
        
        leituras_tarde = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_ano,
            data_leitura__lte=ultimo_dia_ano,
            periodo='tarde'
        ).order_by('data_leitura')
        
        if leituras_manha.count() >= 2:
            primeira = leituras_manha.first()
            ultima = leituras_manha.last()
            consumo_m3 = float(ultima.leitura - primeira.leitura)
            consumo_litros = consumo_m3 * 1000
            consumo_periodo_manha += consumo_litros
        
        if leituras_tarde.count() >= 2:
            primeira = leituras_tarde.first()
            ultima = leituras_tarde.last()
            consumo_m3 = float(ultima.leitura - primeira.leitura)
            consumo_litros = consumo_m3 * 1000
            consumo_periodo_tarde += consumo_litros
    
    # Criar PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                          rightMargin=30, leftMargin=30,
                          topMargin=30, bottomMargin=18)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilo do título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Título
    elements.append(Paragraph(f"Relatório de Consumo - Lote {lote.numero}", title_style))
    elements.append(Paragraph(f"Tipo: {lote.get_tipo_display()} | Gerado em: {hoje.strftime('%d/%m/%Y %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Resumo Geral
    elements.append(Paragraph("📊 Resumo Geral", heading_style))
    
    resumo_data = [
        ['Indicador', 'Valor'],
        ['Lote', lote.numero],
        ['Tipo', lote.get_tipo_display()],
        ['Consumo Total no Ano', f'{consumo_total_ano:,.0f} L'],
        ['Consumo Período Manhã', f'{consumo_periodo_manha:,.0f} L'],
        ['Consumo Período Tarde', f'{consumo_periodo_tarde:,.0f} L'],
        ['Hidrometros Ativos', str(hidrometros.count())],
    ]
    
    resumo_table = Table(resumo_data, colWidths=[3*inch, 2*inch])
    resumo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(resumo_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # Consumo Mensal
    elements.append(Paragraph("📅 Consumo Mensal", heading_style))
    
    mensal_data = [['Mês', 'Consumo (L)']]
    for mes in range(1, 13):
        mensal_data.append([nomes_meses[mes - 1], f'{consumo_mensal[mes]:,.2f}'])
    
    mensal_table = Table(mensal_data, colWidths=[2*inch, 2*inch])
    mensal_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(mensal_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Gráfico de Consumo Mensal
    plt.figure(figsize=(10, 5))
    meses_labels = [nomes_meses[m-1] for m in range(1, 13)]
    valores_mensais = [consumo_mensal[m] for m in range(1, 13)]
    plt.bar(meses_labels, valores_mensais, color='#27ae60', alpha=0.7)
    plt.title(f'Consumo Mensal - Lote {lote.numero} (Litros)', fontsize=14, fontweight='bold')
    plt.xlabel('Mês', fontsize=11)
    plt.ylabel('Consumo (L)', fontsize=11)
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    # Salvar gráfico em buffer
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
    img_buffer.seek(0)
    plt.close()
    
    # Adicionar imagem ao PDF
    img = Image(img_buffer, width=7*inch, height=3.5*inch)
    elements.append(img)
    elements.append(Spacer(1, 0.3*inch))
    
    # Gráfico de Consumo por Período (Pizza)
    if consumo_periodo_manha > 0 or consumo_periodo_tarde > 0:
        plt.figure(figsize=(7, 7))
        labels_periodo = ['Manhã', 'Tarde']
        valores_periodo = [consumo_periodo_manha, consumo_periodo_tarde]
        colors_periodo = ['#3498db', '#e67e22']
        explode = (0.05, 0.05)
        
        plt.pie(valores_periodo, labels=labels_periodo, autopct='%1.1f%%',
                startangle=90, colors=colors_periodo, explode=explode,
                textprops={'fontsize': 12, 'fontweight': 'bold'})
        plt.title(f'Distribuição de Consumo por Período - Lote {lote.numero}', fontsize=14, fontweight='bold', pad=20)
        plt.tight_layout()
        
        # Salvar gráfico em buffer
        img_buffer_periodo = io.BytesIO()
        plt.savefig(img_buffer_periodo, format='png', dpi=150, bbox_inches='tight')
        img_buffer_periodo.seek(0)
        plt.close()
        
        # Adicionar imagem ao PDF
        img_periodo = Image(img_buffer_periodo, width=5*inch, height=5*inch)
        elements.append(img_periodo)
    
    # Construir PDF
    doc.build(elements)
    
    # Preparar resposta
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_lote_{lote.numero}_{hoje.strftime("%Y%m%d")}.pdf"'
    
    return response


def exportar_graficos_lote_excel(request, lote_id):
    """Exporta os gráficos de consumo de um lote específico em Excel com gráficos"""
    lote = get_object_or_404(Lote, id=lote_id)
    
    # Obter dados do lote (mesma lógica da view graficos_lote)
    hoje = timezone.now()
    ano_atual = hoje.year
    mes_atual = hoje.month
    primeiro_dia_mes = hoje.replace(day=1)
    
    hidrometros = lote.hidrometros.filter(ativo=True)
    
    if not hidrometros.exists():
        return HttpResponse("Nenhum hidrômetro ativo encontrado para este lote.", status=404)
    
    # Calcular último dia do mês
    if mes_atual == 12:
        ultimo_dia_mes = primeiro_dia_mes.replace(year=ano_atual + 1, month=1, day=1) - timedelta(days=1)
    else:
        ultimo_dia_mes = primeiro_dia_mes.replace(month=mes_atual + 1, day=1) - timedelta(days=1)
    
    # Calcular consumo diário
    consumo_diario = {}
    for dia in range(1, ultimo_dia_mes.day + 1):
        consumo_diario[dia] = 0.0
    
    for hidrometro in hidrometros:
        leituras = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_mes,
            data_leitura__lte=ultimo_dia_mes
        ).order_by('data_leitura')
        
        if leituras.exists():
            for i in range(1, len(leituras)):
                leitura_atual = leituras[i]
                leitura_anterior = leituras[i - 1]
                
                if leitura_atual.data_leitura.date() == leitura_anterior.data_leitura.date():
                    dia = leitura_atual.data_leitura.day
                    consumo_m3 = float(leitura_atual.leitura - leitura_anterior.leitura)
                    consumo_litros = consumo_m3 * 1000
                    consumo_diario[dia] += consumo_litros
    
    # Calcular consumo mensal
    nomes_meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    
    consumo_mensal = {}
    for mes in range(1, 13):
        consumo_mensal[mes] = 0.0
        
        if mes == 12:
            primeiro_dia_mes_loop = hoje.replace(month=mes, day=1)
            ultimo_dia_mes_loop = primeiro_dia_mes_loop.replace(year=ano_atual + 1, month=1, day=1) - timedelta(days=1)
        else:
            primeiro_dia_mes_loop = hoje.replace(month=mes, day=1)
            ultimo_dia_mes_loop = primeiro_dia_mes_loop.replace(month=mes + 1, day=1) - timedelta(days=1)
        
        if primeiro_dia_mes_loop > hoje:
            continue
        
        if mes == hoje.month:
            ultimo_dia_mes_loop = hoje
        
        for hidrometro in hidrometros:
            leituras_mes = hidrometro.leituras.filter(
                data_leitura__gte=primeiro_dia_mes_loop,
                data_leitura__lte=ultimo_dia_mes_loop
            ).order_by('data_leitura')
            
            if leituras_mes.count() >= 2:
                primeira = leituras_mes.first()
                ultima = leituras_mes.last()
                consumo_m3 = float(ultima.leitura - primeira.leitura)
                consumo_litros = consumo_m3 * 1000
                consumo_mensal[mes] += consumo_litros
    
    # Calcular consumo total do ano
    consumo_total_ano = sum(consumo_mensal.values())
    
    # Calcular consumo por período
    primeiro_dia_ano = hoje.replace(month=1, day=1)
    ultimo_dia_ano = hoje.replace(month=12, day=31)
    
    consumo_periodo_manha = 0.0
    consumo_periodo_tarde = 0.0
    
    for hidrometro in hidrometros:
        leituras_manha = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_ano,
            data_leitura__lte=ultimo_dia_ano,
            periodo='manha'
        ).order_by('data_leitura')
        
        leituras_tarde = hidrometro.leituras.filter(
            data_leitura__gte=primeiro_dia_ano,
            data_leitura__lte=ultimo_dia_ano,
            periodo='tarde'
        ).order_by('data_leitura')
        
        if leituras_manha.count() >= 2:
            primeira = leituras_manha.first()
            ultima = leituras_manha.last()
            consumo_m3 = float(ultima.leitura - primeira.leitura)
            consumo_litros = consumo_m3 * 1000
            consumo_periodo_manha += consumo_litros
        
        if leituras_tarde.count() >= 2:
            primeira = leituras_tarde.first()
            ultima = leituras_tarde.last()
            consumo_m3 = float(ultima.leitura - primeira.leitura)
            consumo_litros = consumo_m3 * 1000
            consumo_periodo_tarde += consumo_litros
    
    # Criar Excel
    wb = Workbook()
    
    # Aba: Resumo
    ws_resumo = wb.active
    ws_resumo.title = "Resumo"
    
    # Título
    ws_resumo['A1'] = f'Relatório de Consumo - Lote {lote.numero}'
    ws_resumo['A1'].font = Font(size=16, bold=True, color='FFFFFF')
    ws_resumo['A1'].fill = PatternFill(start_color='3498db', end_color='3498db', fill_type='solid')
    ws_resumo['A1'].alignment = Alignment(horizontal='center')
    ws_resumo.merge_cells('A1:C1')
    
    ws_resumo['A2'] = f'Tipo: {lote.get_tipo_display()} | Gerado em: {hoje.strftime("%d/%m/%Y %H:%M")}'
    ws_resumo['A2'].alignment = Alignment(horizontal='center')
    ws_resumo.merge_cells('A2:C2')
    
    # Dados resumo
    ws_resumo['A4'] = 'Indicador'
    ws_resumo['B4'] = 'Valor'
    ws_resumo['A4'].font = Font(bold=True)
    ws_resumo['B4'].font = Font(bold=True)
    
    resumo_dados = [
        ['Lote', lote.numero],
        ['Tipo', lote.get_tipo_display()],
        ['Consumo Total no Ano', f'{consumo_total_ano:,.0f} L'],
        ['Consumo Período Manhã', f'{consumo_periodo_manha:,.0f} L'],
        ['Consumo Período Tarde', f'{consumo_periodo_tarde:,.0f} L'],
        ['Hidrometros Ativos', hidrometros.count()],
    ]
    
    for idx, (indicador, valor) in enumerate(resumo_dados, start=5):
        ws_resumo[f'A{idx}'] = indicador
        ws_resumo[f'B{idx}'] = valor
    
    ws_resumo.column_dimensions['A'].width = 30
    ws_resumo.column_dimensions['B'].width = 20
    
    # Aba: Consumo Mensal
    ws_mensal = wb.create_sheet("Consumo Mensal")
    
    ws_mensal['A1'] = 'Mês'
    ws_mensal['B1'] = 'Consumo (L)'
    ws_mensal['A1'].font = Font(bold=True)
    ws_mensal['B1'].font = Font(bold=True)
    
    for mes in range(1, 13):
        ws_mensal[f'A{mes + 1}'] = nomes_meses[mes - 1]
        ws_mensal[f'B{mes + 1}'] = round(consumo_mensal[mes], 2)
    
    # Adicionar gráfico
    chart = LineChart()
    chart.title = f"Consumo Mensal - Lote {lote.numero}"
    chart.y_axis.title = "Consumo (Litros)"
    chart.x_axis.title = "Mês"
    
    data = Reference(ws_mensal, min_col=2, min_row=1, max_row=13)
    cats = Reference(ws_mensal, min_col=1, min_row=2, max_row=13)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.height = 10
    chart.width = 20
    
    ws_mensal.add_chart(chart, "D2")
    
    ws_mensal.column_dimensions['A'].width = 15
    ws_mensal.column_dimensions['B'].width = 15
    
    # Aba: Consumo por Período
    ws_periodo = wb.create_sheet("Consumo por Período")
    
    ws_periodo['A1'] = 'Período'
    ws_periodo['B1'] = 'Consumo (L)'
    ws_periodo['A1'].font = Font(bold=True)
    ws_periodo['B1'].font = Font(bold=True)
    
    ws_periodo['A2'] = 'Manhã'
    ws_periodo['B2'] = round(consumo_periodo_manha, 2)
    ws_periodo['A3'] = 'Tarde'
    ws_periodo['B3'] = round(consumo_periodo_tarde, 2)
    
    # Adicionar gráfico de pizza
    pie = PieChart()
    pie.title = f"Distribuição de Consumo - Lote {lote.numero}"
    
    data_pie = Reference(ws_periodo, min_col=2, min_row=1, max_row=3)
    cats_pie = Reference(ws_periodo, min_col=1, min_row=2, max_row=3)
    pie.add_data(data_pie, titles_from_data=True)
    pie.set_categories(cats_pie)
    pie.height = 10
    pie.width = 15
    
    ws_periodo.add_chart(pie, "D2")
    
    ws_periodo.column_dimensions['A'].width = 15
    ws_periodo.column_dimensions['B'].width = 15
    
    # Salvar e retornar
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="relatorio_lote_{lote.numero}_{hoje.strftime("%Y%m%d")}.xlsx"'
    
    return response

