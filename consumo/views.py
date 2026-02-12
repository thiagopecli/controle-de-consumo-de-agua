from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Avg, Max, Min, Count, Q
from django.http import HttpResponse
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import timedelta, datetime
import json
import io
import os
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.chart import BarChart, PieChart, LineChart, Reference
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT

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
    """Lista todos os hidrômetros com paginação"""
    from django.core.paginator import Paginator
    
    agora = timezone.localtime(timezone.now())
    hoje = agora.date()
    hidrometros_list = (
        Hidrometro.objects.filter(ativo=True)
        .select_related('lote')
        .annotate(
            leituras_hoje=Count('leituras', filter=Q(leituras__data_leitura__date=hoje)),
            ultima_leitura=Max('leituras__data_leitura'),
        )
        .order_by('numero')
    )
    
    # Paginação: 50 hidrômetros por página
    paginator = Paginator(hidrometros_list, 50)
    page_number = request.GET.get('page', 1)
    hidrometros = paginator.get_page(page_number)
    
    context = {
        'hidrometros': hidrometros,
    }
    
    return render(request, 'consumo/listar_hidrometros.html', context)


def listar_leituras(request):
    """Lista todas as leituras com paginação"""
    from django.core.paginator import Paginator
    
    leituras_list = (
        Leitura.objects.all()
        .select_related('hidrometro__lote')
        .order_by('-data_leitura')
    )

    # Filtro por lote (servidor): ainda paginando em 50 por página
    lote_filtro = request.GET.get('lote', '').strip()
    if lote_filtro:
        if lote_filtro.lower() == 'adm':
            # Filtrar todos os lotes de administração
            leituras_list = leituras_list.filter(hidrometro__lote__tipo='administracao')
        else:
            # Filtro por número de lote específico (inclui possíveis valores como 'ADM-22')
            leituras_list = leituras_list.filter(hidrometro__lote__numero=lote_filtro)

    # Paginação: 50 leituras por página (sempre)
    paginator = Paginator(leituras_list, 50)
    page_number = request.GET.get('page', 1)
    leituras = paginator.get_page(page_number)
    total_leituras = paginator.count
    
    context = {
        'leituras': leituras,
        'total_leituras': total_leituras,
        'lote_filtro': lote_filtro,
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
    """Página com detalhes e histórico de leituras do hidrômetro com filtros e gráficos"""
    from datetime import timedelta
    from django.db.models import Sum
    from collections import defaultdict
    import calendar
    
    hidrometro = get_object_or_404(Hidrometro, id=hidrometro_id)
    
    # Obter filtros de período
    periodo = request.GET.get('periodo', '30dias')
    data_inicio_str = request.GET.get('data_inicio', '')
    data_fim_str = request.GET.get('data_fim', '')
    
    hoje = timezone.now().date()
    data_inicio = None
    data_fim = hoje
    periodo_label = ''
    
    # Definir período baseado no filtro
    if periodo == '7dias':
        data_inicio = hoje - timedelta(days=7)
        periodo_label = 'Últimos 7 dias'
    elif periodo == '15dias':
        data_inicio = hoje - timedelta(days=15)
        periodo_label = 'Últimos 15 dias'
    elif periodo == '30dias':
        data_inicio = hoje - timedelta(days=30)
        periodo_label = 'Últimos 30 dias'
    elif periodo == 'mes_atual':
        data_inicio = hoje.replace(day=1)
        periodo_label = f'{hoje.strftime("%B de %Y").capitalize()}'
    elif periodo == 'ano_atual':
        data_inicio = hoje.replace(month=1, day=1)
        periodo_label = f'Ano de {hoje.year}'
    elif periodo == 'personalizado' and data_inicio_str and data_fim_str:
        try:
            from datetime import datetime
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            periodo_label = f'{data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}'
        except:
            data_inicio = hoje - timedelta(days=30)
            data_fim = hoje
            periodo_label = 'Últimos 30 dias'
            periodo = '30dias'
    else:
        data_inicio = hoje - timedelta(days=30)
        periodo_label = 'Últimos 30 dias'
    
    # Obter leituras filtradas
    leituras = hidrometro.leituras.filter(
        data_leitura__date__gte=data_inicio,
        data_leitura__date__lte=data_fim
    ).order_by('-data_leitura')
    
    # Obter todas as leituras para o histórico completo (limitado)
    leituras_historico = hidrometro.leituras.all().order_by('-data_leitura')[:50]
    
    # Calcular consumo total no período
    consumo_total_periodo = 0
    leituras_ordenadas = hidrometro.leituras.filter(
        data_leitura__date__gte=data_inicio,
        data_leitura__date__lte=data_fim
    ).order_by('data_leitura')
    
    for i, leitura_atual in enumerate(leituras_ordenadas):
        if i > 0:
            leitura_anterior = list(leituras_ordenadas)[i-1]
            diferenca = float(leitura_atual.leitura) - float(leitura_anterior.leitura)
            if diferenca > 0:
                consumo_litros = diferenca * 1000
                consumo_total_periodo += consumo_litros
    
    # Preparar dados para gráficos
    # Gráfico 1: Consumo por Dia
    consumo_por_dia = defaultdict(float)
    for i, leitura_atual in enumerate(leituras_ordenadas):
        if i > 0:
            leitura_anterior = list(leituras_ordenadas)[i-1]
            diferenca = float(leitura_atual.leitura) - float(leitura_anterior.leitura)
            if diferenca > 0:
                consumo_litros = diferenca * 1000
                dia_str = leitura_atual.data_leitura.strftime('%d/%m')
                consumo_por_dia[dia_str] += consumo_litros
    
    consumo_dia_lista = [
        {'dia': dia, 'consumo_litros': consumo}
        for dia, consumo in sorted(consumo_por_dia.items())
    ]
    
    # Gráfico 2: Consumo por Mês
    consumo_por_mes = defaultdict(float)
    for i, leitura_atual in enumerate(leituras_ordenadas):
        if i > 0:
            leitura_anterior = list(leituras_ordenadas)[i-1]
            diferenca = float(leitura_atual.leitura) - float(leitura_anterior.leitura)
            if diferenca > 0:
                consumo_litros = diferenca * 1000
                mes_numero = leitura_atual.data_leitura.month
                consumo_por_mes[mes_numero] += consumo_litros
    
    consumo_mes_lista = []
    for mes in sorted(consumo_por_mes.keys()):
        mes_nome = calendar.month_name[mes].capitalize() if mes <= 12 else f'Mês {mes}'
        consumo_mes_lista.append({
            'mes': mes,
            'mes_nome': mes_nome,
            'consumo_litros': consumo_por_mes[mes]
        })
    
    # Dados dos gráficos (sem período do dia - removido do template)
    dados_graficos = {
        'consumo_dia': consumo_dia_lista,
        'consumo_mes': consumo_mes_lista,
        'consumo_total_periodo': consumo_total_periodo,
        'periodo_label': periodo_label,
        'periodo_selecionado': periodo,
    }
    
    # Serializar dados para JSON
    import json
    dados_graficos_json = json.dumps(dados_graficos, ensure_ascii=False)
    
    context = {
        'hidrometro': hidrometro,
        'leituras': leituras_historico,
        'dados_graficos': dados_graficos_json,
    }
    
    return render(request, 'consumo/detalhes_hidrometro.html', context)


def graficos_consumo(request):
    """Página com gráficos de consumo do condomínio com filtro de período."""

    agora = timezone.localtime(timezone.now())
    hoje = agora
    ano_atual = hoje.year
    
    # Obter o período selecionado (padrão: últimos 30 dias)
    periodo_selecionado = request.GET.get('periodo', '30dias')
    
    # Definir data de início baseada no período selecionado
    if periodo_selecionado == '7dias':
        dias_filtrados = 7
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 7 dias"
    elif periodo_selecionado == '15dias':
        dias_filtrados = 15
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 15 dias"
    elif periodo_selecionado == '30dias':
        dias_filtrados = 30
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 30 dias"
    elif periodo_selecionado == 'mes_atual':
        # Mês atual (do dia 1 até hoje)
        data_inicio_dias = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        dias_filtrados = (hoje - data_inicio_dias).days + 1
        periodo_label = f"Mês Atual ({hoje.strftime('%B/%Y')})"
    elif periodo_selecionado == 'ano_atual':
        # Ano atual (de 1º de janeiro até hoje)
        data_inicio_ano = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
        data_inicio_dias = data_inicio_ano
        dias_filtrados = (hoje - data_inicio_ano).days + 1
        periodo_label = f"Ano Atual ({ano_atual})"
    elif periodo_selecionado == 'personalizado':
        # Período personalizado (data_inicio e data_fim via GET)
        data_inicio_str = request.GET.get('data_inicio')
        data_fim_str = request.GET.get('data_fim')
        
        if data_inicio_str and data_fim_str:
            try:
                data_inicio_dias = timezone.datetime.strptime(data_inicio_str, '%Y-%m-%d')
                data_inicio_dias = timezone.make_aware(data_inicio_dias.replace(hour=0, minute=0, second=0, microsecond=0))
                data_fim_personalizada = timezone.datetime.strptime(data_fim_str, '%Y-%m-%d')
                data_fim_personalizada = timezone.make_aware(data_fim_personalizada.replace(hour=23, minute=59, second=59, microsecond=999999))
                
                # Limitar data_fim ao hoje se for futuro
                if data_fim_personalizada > hoje:
                    data_fim_personalizada = hoje
                
                data_inicio_ano = data_inicio_dias
                dias_filtrados = (data_fim_personalizada - data_inicio_dias).days + 1
                periodo_label = f"{data_inicio_dias.strftime('%d/%m/%Y')} até {data_fim_personalizada.strftime('%d/%m/%Y')}"
                hoje = data_fim_personalizada  # Usar data_fim personalizada
            except (ValueError, TypeError):
                # Se houver erro, usar padrão (últimos 30 dias)
                dias_filtrados = 30
                data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
                data_inicio_ano = data_inicio_dias
                periodo_label = "Últimos 30 dias (erro na data personalizada)"
        else:
            # Sem datas fornecidas, usar padrão
            dias_filtrados = 30
            data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
            data_inicio_ano = data_inicio_dias
            periodo_label = "Últimos 30 dias"
    else:
        # Padrão: últimos 30 dias
        dias_filtrados = 30
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 30 dias"
    
    data_fim = hoje

    dados_graficos = {
        'consumo_por_dia': [],
        'consumo_mes': [],
        'consumo_total_ano': 0.0,
        'top_lotes': [],
        'consumo_por_hidrometro': [],
        'periodo_label': periodo_label,
        'periodo_selecionado': periodo_selecionado,
        'ano_atual': ano_atual,
    }

    hidrometros_qs = Hidrometro.objects.filter(
        ativo=True,
        lote__tipo='residencial'
    ).select_related('lote')

    # ================= CONSUMO POR DIA (ÚLTIMOS 30 DIAS) =================
    consumo_diario = {}
    datas_periodo = []
    dia_cursor = data_inicio_dias
    while dia_cursor.date() <= data_fim.date():
        consumo_diario[dia_cursor.date()] = 0.0
        datas_periodo.append(dia_cursor.date())
        dia_cursor += timedelta(days=1)

    consumo_mensal = {}
    consumo_total_ano = 0.0
    consumo_por_lote_ano = {}
    consumo_por_hidrometro = []

    for hidrometro in hidrometros_qs:
        # Buscar leituras do período filtrado para calcular o consumo total
        leituras_ano = hidrometro.leituras.filter(
            data_leitura__gte=data_inicio_dias,
            data_leitura__lte=data_fim
        ).order_by('data_leitura')

        consumo_hidrometro_litros = 0.0
        if not leituras_ano.exists():
            continue

        # Calcular consumo do ano (para total e top lotes)
        for i in range(1, len(leituras_ano)):
            leitura_atual = leituras_ano[i]
            leitura_anterior = leituras_ano[i - 1]

            consumo_m3 = float(leitura_atual.leitura - leitura_anterior.leitura)
            if consumo_m3 < 0:
                continue

            consumo_litros = consumo_m3 * 1000
            consumo_total_ano += consumo_litros
            consumo_hidrometro_litros += consumo_litros

            # Consumo por lote (ano)
            numero_lote = leitura_atual.hidrometro.lote.numero
            consumo_por_lote_ano.setdefault(numero_lote, 0.0)
            consumo_por_lote_ano[numero_lote] += consumo_litros

            # Consumo por mês (ano)
            mes_key = (leitura_atual.data_leitura.year, leitura_atual.data_leitura.month)
            consumo_mensal.setdefault(mes_key, 0.0)
            consumo_mensal[mes_key] += consumo_litros

            # Consumo diário (apenas últimos 30 dias)
            dia = leitura_atual.data_leitura.date()
            if dia in consumo_diario:
                consumo_diario[dia] += consumo_litros

        if consumo_hidrometro_litros > 0:
            consumo_por_hidrometro.append({
                'hidrometro': hidrometro.numero,
                'lote': hidrometro.lote.numero,
                'consumo_litros': round(consumo_hidrometro_litros, 2),
            })

    # Preparar dados dos gráficos
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

    dados_graficos['consumo_total_ano'] = round(consumo_total_ano, 2)

    top_lotes = sorted(consumo_por_lote_ano.items(), key=lambda x: x[1], reverse=True)[:10]
    dados_graficos['top_lotes'] = [
        {'lote': lote, 'consumo_litros': round(consumo, 2)} for lote, consumo in top_lotes
    ]

    def _ordenar_lote(item):
        numero = item['lote']
        # Lotes numéricos primeiro, ordenados por valor inteiro; depois lotes ADM/strings
        try:
            return (0, int(numero), numero)
        except ValueError:
            # Tentar extrair número após prefixo ADM-
            if numero.upper().startswith('ADM-'):
                try:
                    return (1, int(numero.split('-', 1)[1]), numero)
                except ValueError:
                    return (1, float('inf'), numero)
            return (1, float('inf'), numero)

    dados_graficos['consumo_por_hidrometro'] = sorted(
        consumo_por_hidrometro,
        key=lambda x: (_ordenar_lote(x), x['hidrometro'])
    )

    lotes_disponiveis = Lote.objects.filter(
        ativo=True,
        tipo='residencial'
    ).order_by('numero')

    context = {
        'dados_graficos': dados_graficos,
        'hidrometros': hidrometros_qs,
        'lotes': lotes_disponiveis,
    }

    return render(request, 'consumo/graficos_consumo.html', context)


def graficos_lote(request, lote_id):
    """Página com gráficos de consumo específicos de um lote com filtros de período"""
    from collections import defaultdict
    import calendar
    
    lote = get_object_or_404(Lote, id=lote_id)
    
    # Obter filtros de período
    periodo = request.GET.get('periodo', '30dias')
    data_inicio_str = request.GET.get('data_inicio', '')
    data_fim_str = request.GET.get('data_fim', '')
    
    hoje = timezone.now().date()
    data_inicio = None
    data_fim = hoje
    periodo_label = ''
    
    # Definir período baseado no filtro
    if periodo == '7dias':
        data_inicio = hoje - timedelta(days=7)
        periodo_label = 'Últimos 7 dias'
    elif periodo == '15dias':
        data_inicio = hoje - timedelta(days=15)
        periodo_label = 'Últimos 15 dias'
    elif periodo == '30dias':
        data_inicio = hoje - timedelta(days=30)
        periodo_label = 'Últimos 30 dias'
    elif periodo == 'mes_atual':
        data_inicio = hoje.replace(day=1)
        periodo_label = f'{hoje.strftime("%B de %Y").capitalize()}'
    elif periodo == 'ano_atual':
        data_inicio = hoje.replace(month=1, day=1)
        periodo_label = f'Ano de {hoje.year}'
    elif periodo == 'personalizado' and data_inicio_str and data_fim_str:
        try:
            from datetime import datetime
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            periodo_label = f'{data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}'
        except:
            data_inicio = hoje - timedelta(days=30)
            data_fim = hoje
            periodo_label = 'Últimos 30 dias'
            periodo = '30dias'
    else:
        data_inicio = hoje - timedelta(days=30)
        periodo_label = 'Últimos 30 dias'
    
    # Obter todos os hidrômetros do lote
    hidrometros = lote.hidrometros.filter(ativo=True)
    
    if not hidrometros.exists():
        dados_graficos = {
            'lote': lote.numero,
            'tipo': lote.get_tipo_display(),
            'consumo_por_dia': [],
            'consumo_mes': [],
            'consumo_periodo': [],
            'consumo_total_periodo': 0,
            'periodo_label': periodo_label,
            'periodo_selecionado': periodo,
        }
        
        import json
        dados_graficos_json = json.dumps(dados_graficos, ensure_ascii=False)
        
        context = {
            'lote': lote,
            'dados_graficos': dados_graficos_json,
            'sem_dados': True,
        }
        return render(request, 'consumo/graficos_lote.html', context)
    
    # Calcular consumo total no período para todos os hidrômetros do lote
    consumo_total_periodo = 0
    
    for hidrometro in hidrometros:
        leituras_ordenadas = hidrometro.leituras.filter(
            data_leitura__date__gte=data_inicio,
            data_leitura__date__lte=data_fim
        ).order_by('data_leitura')
        
        for i, leitura_atual in enumerate(leituras_ordenadas):
            if i > 0:
                leitura_anterior = list(leituras_ordenadas)[i-1]
                diferenca = float(leitura_atual.leitura) - float(leitura_anterior.leitura)
                if diferenca > 0:
                    consumo_litros = diferenca * 1000
                    consumo_total_periodo += consumo_litros
    
    # Preparar dados para gráficos
    # Gráfico 1: Consumo por Dia
    consumo_por_dia = defaultdict(float)
    
    for hidrometro in hidrometros:
        leituras_ordenadas = hidrometro.leituras.filter(
            data_leitura__date__gte=data_inicio,
            data_leitura__date__lte=data_fim
        ).order_by('data_leitura')
        
        for i, leitura_atual in enumerate(leituras_ordenadas):
            if i > 0:
                leitura_anterior = list(leituras_ordenadas)[i-1]
                diferenca = float(leitura_atual.leitura) - float(leitura_anterior.leitura)
                if diferenca > 0:
                    consumo_litros = diferenca * 1000
                    dia_str = leitura_atual.data_leitura.strftime('%d/%m')
                    consumo_por_dia[dia_str] += consumo_litros
    
    consumo_dia_lista = [
        {'dia': dia, 'consumo_litros': consumo}
        for dia, consumo in sorted(consumo_por_dia.items())
    ]
    
    # Gráfico 2: Consumo por Mês
    consumo_por_mes = defaultdict(float)
    
    for hidrometro in hidrometros:
        leituras_ordenadas = hidrometro.leituras.filter(
            data_leitura__date__gte=data_inicio,
            data_leitura__date__lte=data_fim
        ).order_by('data_leitura')
        
        for i, leitura_atual in enumerate(leituras_ordenadas):
            if i > 0:
                leitura_anterior = list(leituras_ordenadas)[i-1]
                diferenca = float(leitura_atual.leitura) - float(leitura_anterior.leitura)
                if diferenca > 0:
                    consumo_litros = diferenca * 1000
                    mes_numero = leitura_atual.data_leitura.month
                    consumo_por_mes[mes_numero] += consumo_litros
    
    consumo_mes_lista = []
    for mes in sorted(consumo_por_mes.keys()):
        mes_nome = calendar.month_name[mes].capitalize() if mes <= 12 else f'Mês {mes}'
        consumo_mes_lista.append({
            'mes': mes,
            'mes_nome': mes_nome,
            'consumo_litros': consumo_por_mes[mes]
        })
    
    # Dados dos gráficos (sem período do dia - removido do template)
    dados_graficos = {
        'lote': lote.numero,
        'tipo': lote.get_tipo_display(),
        'consumo_por_dia': consumo_dia_lista,
        'consumo_mes': consumo_mes_lista,
        'consumo_total_periodo': consumo_total_periodo,
        'periodo_label': periodo_label,
        'periodo_selecionado': periodo,
    }
    
    # Serializar dados para JSON
    import json
    dados_graficos_json = json.dumps(dados_graficos, ensure_ascii=False)
    
    context = {
        'lote': lote,
        'dados_graficos': dados_graficos_json,
        'hidrometros': hidrometros,
    }
    
    return render(request, 'consumo/graficos_lote.html', context)


def exportar_graficos_consumo_pdf(request):
    """Exporta os gráficos de consumo do condomínio em PDF"""
    import os
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    from django.template.loader import render_to_string
    
    # Obter dados dos gráficos (mesma lógica da view graficos_consumo)
    agora = timezone.localtime(timezone.now())
    hoje = agora
    ano_atual = hoje.year
    
    # Obter o período selecionado (padrão: últimos 30 dias)
    periodo_selecionado = request.GET.get('periodo', '30dias')
    
    # Definir data de início baseada no período selecionado
    if periodo_selecionado == '7dias':
        dias_filtrados = 7
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 7 dias"
    elif periodo_selecionado == '15dias':
        dias_filtrados = 15
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 15 dias"
    elif periodo_selecionado == '30dias':
        dias_filtrados = 30
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 30 dias"
    elif periodo_selecionado == 'mes_atual':
        # Mês atual (do dia 1 até hoje)
        data_inicio_dias = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        dias_filtrados = (hoje - data_inicio_dias).days + 1
        periodo_label = f"Mês Atual ({hoje.strftime('%B/%Y')})"
    elif periodo_selecionado == 'ano_atual':
        # Ano atual (de 1º de janeiro até hoje)
        data_inicio_ano = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
        data_inicio_dias = data_inicio_ano
        dias_filtrados = (hoje - data_inicio_ano).days + 1
        periodo_label = f"Ano Atual ({ano_atual})"
    elif periodo_selecionado == 'personalizado':
        # Período personalizado (data_inicio e data_fim via GET)
        data_inicio_str = request.GET.get('data_inicio')
        data_fim_str = request.GET.get('data_fim')
        
        if data_inicio_str and data_fim_str:
            try:
                data_inicio_dias = timezone.datetime.strptime(data_inicio_str, '%Y-%m-%d')
                data_inicio_dias = timezone.make_aware(data_inicio_dias.replace(hour=0, minute=0, second=0, microsecond=0))
                data_fim_personalizada = timezone.datetime.strptime(data_fim_str, '%Y-%m-%d')
                data_fim_personalizada = timezone.make_aware(data_fim_personalizada.replace(hour=23, minute=59, second=59, microsecond=999999))
                
                # Limitar data_fim ao hoje se for futuro
                if data_fim_personalizada > hoje:
                    data_fim_personalizada = hoje
                
                data_inicio_ano = data_inicio_dias
                dias_filtrados = (data_fim_personalizada - data_inicio_dias).days + 1
                periodo_label = f"{data_inicio_dias.strftime('%d/%m/%Y')} até {data_fim_personalizada.strftime('%d/%m/%Y')}"
                hoje = data_fim_personalizada  # Usar data_fim personalizada
            except (ValueError, TypeError):
                # Se houver erro, usar padrão (últimos 30 dias)
                dias_filtrados = 30
                data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
                data_inicio_ano = data_inicio_dias
                periodo_label = "Últimos 30 dias (erro na data personalizada)"
        else:
            # Sem datas fornecidas, usar padrão
            dias_filtrados = 30
            data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
            data_inicio_ano = data_inicio_dias
            periodo_label = "Últimos 30 dias"
    else:
        # Padrão: últimos 30 dias
        dias_filtrados = 30
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 30 dias"
    
    data_fim = hoje
    
    # Buscar todos os hidrômetros ativos
    hidrometros = Hidrometro.objects.filter(
        ativo=True,
        lote__tipo='residencial'
    ).select_related('lote')
    
    # Calcular consumo diário baseado no período filtrado
    consumo_diario = {}
    datas_periodo = []
    dia_cursor = data_inicio_dias
    while dia_cursor.date() <= data_fim.date():
        consumo_diario[dia_cursor.date()] = 0.0
        datas_periodo.append(dia_cursor.date())
        dia_cursor += timedelta(days=1)

    # Consumo por hidrômetro (individual) no período
    consumo_por_hidrometro = []
    consumo_total_periodo = 0.0
    
    for hidrometro in hidrometros:
        leituras = hidrometro.leituras.filter(
            data_leitura__gte=data_inicio_dias,
            data_leitura__lte=data_fim
        ).order_by('data_leitura')
        
        consumo_hidrometro_litros = 0.0
        if leituras.exists():
            for i in range(1, len(leituras)):
                leitura_atual = leituras[i]
                leitura_anterior = leituras[i - 1]
                
                consumo_m3 = float(leitura_atual.leitura - leitura_anterior.leitura)
                if consumo_m3 < 0:
                    continue
                    
                consumo_litros = consumo_m3 * 1000
                consumo_hidrometro_litros += consumo_litros
                consumo_total_periodo += consumo_litros
                
                # Consumo diário
                dia = leitura_atual.data_leitura.date()
                if dia in consumo_diario:
                    consumo_diario[dia] += consumo_litros

        if consumo_hidrometro_litros > 0:
            consumo_por_hidrometro.append({
                'hidrometro': hidrometro.numero,
                'lote': hidrometro.lote.numero,
                'consumo_litros': round(consumo_hidrometro_litros, 2),
            })
    
    # Top 10 lotes por consumo (baseado no período filtrado)
    lotes_consumo = []
    for lote in Lote.objects.filter(ativo=True, tipo='residencial'):
        consumo_lote = 0.0
        hidrometros_lote = lote.hidrometros.filter(ativo=True)
        
        for hidrometro in hidrometros_lote:
            leituras_periodo = hidrometro.leituras.filter(
                data_leitura__gte=data_inicio_dias,
                data_leitura__lte=data_fim
            ).order_by('data_leitura')
            
            if leituras_periodo.count() >= 2:
                primeira = leituras_periodo.first()
                ultima = leituras_periodo.last()
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

    # Ordenar hidrômetros por lote (numéricos primeiro, depois ADM)
    def _ordenar_lote(item):
        numero = item['lote']
        try:
            return (0, int(numero), numero)
        except ValueError:
            if numero.upper().startswith('ADM-'):
                try:
                    return (1, int(numero.split('-', 1)[1]), numero)
                except ValueError:
                    return (1, float('inf'), numero)
            return (1, float('inf'), numero)

    consumo_por_hidrometro = sorted(
        consumo_por_hidrometro,
        key=lambda x: (_ordenar_lote(x), x['hidrometro'])
    )
    
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
    elements.append(Paragraph(f"Relatório de Consumo de Água - {periodo_label}", title_style))
    elements.append(Paragraph(f"Gerado em: {agora.strftime('%d/%m/%Y %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Resumo Geral
    elements.append(Paragraph("📊 Resumo Geral", heading_style))
    
    resumo_data = [
        ['Indicador', 'Valor'],
        ['Período', periodo_label],
        ['Consumo Total', f'{consumo_total_periodo:,.0f} L'],
        ['Hidrômetros Ativos', str(hidrometros.count())],
        ['Lotes Ativos', str(Lote.objects.filter(ativo=True, tipo='residencial').count())],
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
    
    # Gráfico de Consumo Diário
    elements.append(Paragraph("📈 Consumo Diário", heading_style))
    
    plt.figure(figsize=(10, 5))
    datas_labels = [d.strftime('%d/%m') for d in datas_periodo]
    valores_diarios = [consumo_diario[d] for d in datas_periodo]
    plt.plot(datas_labels, valores_diarios, marker='o', color='#3498db', linewidth=2, markersize=4)
    plt.title(f'Consumo Diário - {periodo_label}', fontsize=14, fontweight='bold')
    plt.xlabel('Data', fontsize=11)
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
        plt.title(f'Top 10 Lotes - Consumo ({periodo_label})', fontsize=14, fontweight='bold')
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
    elements.append(PageBreak())
    
    # Tabela: Consumo por Hidrômetro (período)
    elements.append(Paragraph("📈 Consumo por Hidrômetro (período)", heading_style))

    hidrometro_data = [['Hidrômetro', 'Lote', 'Consumo (L)']]
    for item in consumo_por_hidrometro:
        hidrometro_data.append([
            item['hidrometro'],
            item['lote'],
            f"{item['consumo_litros']:,.0f}"
        ])

    hidrometro_table = Table(hidrometro_data, colWidths=[2*inch, 1.5*inch, 2*inch])
    hidrometro_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2980b9')),
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

    elements.append(hidrometro_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Construir PDF
    doc.build(elements)
    
    # Preparar resposta
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_consumo_condominio_{agora.strftime("%Y%m%d")}.pdf"'
    
    return response


def exportar_graficos_consumo_excel(request):
    """Exporta os gráficos de consumo do condomínio em Excel com gráficos"""
    import os
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    # Obter dados dos gráficos (mesma lógica da view graficos_consumo)
    agora = timezone.localtime(timezone.now())
    hoje = agora
    ano_atual = hoje.year
    
    # Obter o período selecionado (padrão: últimos 30 dias)
    periodo_selecionado = request.GET.get('periodo', '30dias')
    
    # Definir data de início baseada no período selecionado
    if periodo_selecionado == '7dias':
        dias_filtrados = 7
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 7 dias"
    elif periodo_selecionado == '15dias':
        dias_filtrados = 15
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 15 dias"
    elif periodo_selecionado == '30dias':
        dias_filtrados = 30
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 30 dias"
    elif periodo_selecionado == 'mes_atual':
        # Mês atual (do dia 1 até hoje)
        data_inicio_dias = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        dias_filtrados = (hoje - data_inicio_dias).days + 1
        periodo_label = f"Mês Atual ({hoje.strftime('%B/%Y')})"
    elif periodo_selecionado == 'ano_atual':
        # Ano atual (de 1º de janeiro até hoje)
        data_inicio_ano = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
        data_inicio_dias = data_inicio_ano
        dias_filtrados = (hoje - data_inicio_ano).days + 1
        periodo_label = f"Ano Atual ({ano_atual})"
    elif periodo_selecionado == 'personalizado':
        # Período personalizado (data_inicio e data_fim via GET)
        data_inicio_str = request.GET.get('data_inicio')
        data_fim_str = request.GET.get('data_fim')
        
        if data_inicio_str and data_fim_str:
            try:
                data_inicio_dias = timezone.datetime.strptime(data_inicio_str, '%Y-%m-%d')
                data_inicio_dias = timezone.make_aware(data_inicio_dias.replace(hour=0, minute=0, second=0, microsecond=0))
                data_fim_personalizada = timezone.datetime.strptime(data_fim_str, '%Y-%m-%d')
                data_fim_personalizada = timezone.make_aware(data_fim_personalizada.replace(hour=23, minute=59, second=59, microsecond=999999))
                
                # Limitar data_fim ao hoje se for futuro
                if data_fim_personalizada > hoje:
                    data_fim_personalizada = hoje
                
                data_inicio_ano = data_inicio_dias
                dias_filtrados = (data_fim_personalizada - data_inicio_dias).days + 1
                periodo_label = f"{data_inicio_dias.strftime('%d/%m/%Y')} até {data_fim_personalizada.strftime('%d/%m/%Y')}"
                hoje = data_fim_personalizada  # Usar data_fim personalizada
            except (ValueError, TypeError):
                # Se houver erro, usar padrão (últimos 30 dias)
                dias_filtrados = 30
                data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
                data_inicio_ano = data_inicio_dias
                periodo_label = "Últimos 30 dias (erro na data personalizada)"
        else:
            # Sem datas fornecidas, usar padrão
            dias_filtrados = 30
            data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
            data_inicio_ano = data_inicio_dias
            periodo_label = "Últimos 30 dias"
    else:
        # Padrão: últimos 30 dias
        dias_filtrados = 30
        data_inicio_dias = (hoje - timedelta(days=dias_filtrados - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data_inicio_ano = data_inicio_dias
        periodo_label = "Últimos 30 dias"
    
    data_fim = hoje
    
    # Buscar todos os hidrômetros ativos
    hidrometros = Hidrometro.objects.filter(
        ativo=True,
        lote__tipo='residencial'
    ).select_related('lote')
    
    # Calcular consumo diário baseado no período filtrado
    consumo_diario = {}
    datas_periodo = []
    dia_cursor = data_inicio_dias
    while dia_cursor.date() <= data_fim.date():
        consumo_diario[dia_cursor.date()] = 0.0
        datas_periodo.append(dia_cursor.date())
        dia_cursor += timedelta(days=1)
    
    # Consumo por hidrômetro (individual) no período
    consumo_por_hidrometro = []
    consumo_total_periodo = 0.0
    
    for hidrometro in hidrometros:
        leituras = hidrometro.leituras.filter(
            data_leitura__gte=data_inicio_dias,
            data_leitura__lte=data_fim
        ).order_by('data_leitura')
        
        consumo_hidrometro_litros = 0.0
        if leituras.exists():
            for i in range(1, len(leituras)):
                leitura_atual = leituras[i]
                leitura_anterior = leituras[i - 1]
                
                consumo_m3 = float(leitura_atual.leitura - leitura_anterior.leitura)
                if consumo_m3 < 0:
                    continue
                    
                consumo_litros = consumo_m3 * 1000
                consumo_hidrometro_litros += consumo_litros
                consumo_total_periodo += consumo_litros
                
                # Consumo diário
                dia = leitura_atual.data_leitura.date()
                if dia in consumo_diario:
                    consumo_diario[dia] += consumo_litros

        consumo_por_hidrometro.append({
            'hidrometro': hidrometro.numero,
            'lote': hidrometro.lote.numero,
            'consumo_litros': round(consumo_hidrometro_litros, 2),
        })
    
    # Top 10 lotes por consumo (baseado no período filtrado)
    lotes_consumo = []
    for lote in Lote.objects.filter(ativo=True, tipo='residencial'):
        consumo_lote = 0.0
        hidrometros_lote = lote.hidrometros.filter(ativo=True)
        
        for hidrometro in hidrometros_lote:
            leituras_periodo = hidrometro.leituras.filter(
                data_leitura__gte=data_inicio_dias,
                data_leitura__lte=data_fim
            ).order_by('data_leitura')
            
            if leituras_periodo.count() >= 2:
                primeira = leituras_periodo.first()
                ultima = leituras_periodo.last()
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
    
    # Ordenar hidrômetros por lote (numéricos primeiro, depois ADM)
    def _ordenar_lote(item):
        numero = item['lote']
        try:
            return (0, int(numero), numero)
        except ValueError:
            if numero.upper().startswith('ADM-'):
                try:
                    return (1, int(numero.split('-', 1)[1]), numero)
                except ValueError:
                    return (1, float('inf'), numero)
            return (1, float('inf'), numero)

    consumo_por_hidrometro = sorted(
        consumo_por_hidrometro,
        key=lambda x: (_ordenar_lote(x), x['hidrometro'])
    )
    
    # Criar Excel
    wb = Workbook()
    
    # Aba: Resumo
    ws_resumo = wb.active
    ws_resumo.title = "Resumo"
    
    # Título
    ws_resumo['A1'] = f'Relatório de Consumo de Água - {periodo_label}'
    ws_resumo['A1'].font = Font(size=16, bold=True, color='FFFFFF')
    ws_resumo['A1'].fill = PatternFill(start_color='3498db', end_color='3498db', fill_type='solid')
    ws_resumo['A1'].alignment = Alignment(horizontal='center')
    ws_resumo.merge_cells('A1:C1')
    
    ws_resumo['A2'] = f'Gerado em: {agora.strftime("%d/%m/%Y %H:%M")}'
    ws_resumo['A2'].alignment = Alignment(horizontal='center')
    ws_resumo.merge_cells('A2:C2')
    
    # Dados resumo
    ws_resumo['A4'] = 'Indicador'
    ws_resumo['B4'] = 'Valor'
    ws_resumo['A4'].font = Font(bold=True)
    ws_resumo['B4'].font = Font(bold=True)
    
    resumo_dados = [
        ['Período', periodo_label],
        ['Consumo Total', f'{consumo_total_periodo:,.0f} L'],
        ['Hidrômetros Ativos', hidrometros.count()],
        ['Lotes Ativos', Lote.objects.filter(ativo=True, tipo='residencial').count()],
    ]
    
    for idx, (indicador, valor) in enumerate(resumo_dados, start=5):
        ws_resumo[f'A{idx}'] = indicador
        ws_resumo[f'B{idx}'] = valor
    
    ws_resumo.column_dimensions['A'].width = 30
    ws_resumo.column_dimensions['B'].width = 20
    
    # Aba: Consumo Diário (baseado no período filtrado)
    ws_diario = wb.create_sheet("Consumo Diário")
    
    ws_diario['A1'] = 'Data'
    ws_diario['B1'] = 'Consumo (L)'
    ws_diario['A1'].font = Font(bold=True)
    ws_diario['B1'].font = Font(bold=True)
    
    for idx, data in enumerate(datas_periodo, start=2):
        ws_diario[f'A{idx}'] = data.strftime('%d/%m/%Y')
        ws_diario[f'B{idx}'] = round(consumo_diario[data], 2)
    
    # Gerar gráfico com matplotlib (igual ao PDF)
    plt.figure(figsize=(12, 6))
    datas_labels = [d.strftime('%d/%m') for d in datas_periodo]
    valores_diarios = [consumo_diario[d] for d in datas_periodo]
    plt.plot(datas_labels, valores_diarios, marker='o', color='#3498db', linewidth=2, markersize=4)
    plt.title(f'Consumo Diário - {periodo_label}', fontsize=14, fontweight='bold')
    plt.xlabel('Data', fontsize=11)
    plt.ylabel('Consumo (L)', fontsize=11)
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    # Salvar gráfico em buffer
    img_buffer_diario = io.BytesIO()
    plt.savefig(img_buffer_diario, format='png', dpi=100, bbox_inches='tight')
    img_buffer_diario.seek(0)
    plt.close()
    
    # Adicionar imagem ao Excel
    from openpyxl.drawing.image import Image as XLImage
    img_diario = XLImage(img_buffer_diario)
    img_diario.width = 600
    img_diario.height = 300
    ws_diario.add_image(img_diario, "D2")
    
    ws_diario.column_dimensions['A'].width = 15
    ws_diario.column_dimensions['B'].width = 15
    
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
    
    # Gerar gráfico com matplotlib (igual ao PDF)
    if top_lotes:
        plt.figure(figsize=(12, 6))
        lotes_labels = [item['lote'].numero for item in top_lotes]
        lotes_valores = [item['consumo'] for item in top_lotes]
        plt.barh(lotes_labels[::-1], lotes_valores[::-1], color='#e74c3c', alpha=0.7)
        plt.title(f'Top 10 Lotes - Consumo ({periodo_label})', fontsize=14, fontweight='bold')
        plt.xlabel('Consumo (L)', fontsize=11)
        plt.ylabel('Lote', fontsize=11)
        plt.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        
        # Salvar gráfico em buffer
        img_buffer_top = io.BytesIO()
        plt.savefig(img_buffer_top, format='png', dpi=100, bbox_inches='tight')
        img_buffer_top.seek(0)
        plt.close()
        
        # Adicionar imagem ao Excel
        from openpyxl.drawing.image import Image as XLImage
        img_top_chart = XLImage(img_buffer_top)
        img_top_chart.width = 600
        img_top_chart.height = 300
        ws_top.add_image(img_top_chart, "F2")
    
    for col in ['A', 'B', 'C', 'D']:
        ws_top.column_dimensions[col].width = 15

    # Aba: Consumo por Hidrômetro
    ws_hid = wb.create_sheet("Consumo por Hidrômetro")
    ws_hid['A1'] = 'Hidrômetro'
    ws_hid['B1'] = 'Lote'
    ws_hid['C1'] = 'Consumo (L)'
    for col in ['A1', 'B1', 'C1']:
        ws_hid[col].font = Font(bold=True)

    for idx, item in enumerate(consumo_por_hidrometro, start=2):
        ws_hid[f'A{idx}'] = item['hidrometro']
        ws_hid[f'B{idx}'] = item['lote']
        ws_hid[f'C{idx}'] = item['consumo_litros']

    for col in ['A', 'B', 'C']:
        ws_hid.column_dimensions[col].width = 18

    # Gráfico de barras por hidrômetro
    if consumo_por_hidrometro:
        plt.figure(figsize=(14, 6))
        labels_h = [f"{item['hidrometro']} (Lote {item['lote']})" for item in consumo_por_hidrometro]
        valores_h = [item['consumo_litros'] for item in consumo_por_hidrometro]
        plt.bar(range(len(labels_h)), valores_h, color='#eab308', alpha=0.85)
        plt.title(f'Consumo por Hidrômetro ({periodo_label})', fontsize=14, fontweight='bold')
        plt.xlabel('Hidrômetro', fontsize=11)
        plt.ylabel('Consumo (L)', fontsize=11)
        plt.xticks(range(len(labels_h)), labels_h, rotation=60, ha='right', fontsize=8)
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()

        img_buffer_h = io.BytesIO()
        plt.savefig(img_buffer_h, format='png', dpi=100, bbox_inches='tight')
        img_buffer_h.seek(0)
        plt.close()

        from openpyxl.drawing.image import Image as XLImage
        img_h_chart = XLImage(img_buffer_h)
        img_h_chart.width = 700
        img_h_chart.height = 320
        ws_hid.add_image(img_h_chart, "E2")
    
    # Salvar e retornar
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="relatorio_consumo_condominio_{agora.strftime("%Y%m%d")}.xlsx"'
    
    return response


def exportar_graficos_lote_pdf(request, lote_id):
    """Exporta os gráficos de consumo de um lote específico em PDF"""
    import os
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    lote = get_object_or_404(Lote, id=lote_id)
    
    # Obter dados do lote (mesma lógica da view graficos_lote)
    agora = timezone.localtime(timezone.now())
    hoje = agora.date()
    periodo = request.GET.get('periodo', '30dias')
    data_inicio_str = request.GET.get('data_inicio', '')
    data_fim_str = request.GET.get('data_fim', '')
    data_fim = hoje
    periodo_label = ''

    if periodo == '7dias':
        data_inicio = hoje - timedelta(days=7)
        periodo_label = 'Últimos 7 dias'
    elif periodo == '15dias':
        data_inicio = hoje - timedelta(days=15)
        periodo_label = 'Últimos 15 dias'
    elif periodo == '30dias':
        data_inicio = hoje - timedelta(days=30)
        periodo_label = 'Últimos 30 dias'
    elif periodo == 'mes_atual':
        data_inicio = hoje.replace(day=1)
        periodo_label = f'{hoje.strftime("%B de %Y").capitalize()}'
    elif periodo == 'ano_atual':
        data_inicio = hoje.replace(month=1, day=1)
        periodo_label = f'Ano de {hoje.year}'
    elif periodo == 'personalizado' and data_inicio_str and data_fim_str:
        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            if data_fim > hoje:
                data_fim = hoje
            periodo_label = f'{data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}'
        except (ValueError, TypeError):
            data_inicio = hoje - timedelta(days=30)
            data_fim = hoje
            periodo_label = 'Últimos 30 dias'
            periodo = '30dias'
    else:
        data_inicio = hoje - timedelta(days=30)
        periodo_label = 'Últimos 30 dias'
    
    hidrometros = lote.hidrometros.filter(ativo=True)
    
    if not hidrometros.exists():
        return HttpResponse("Nenhum hidrômetro ativo encontrado para este lote.", status=404)
    
    # Calcular consumo no periodo
    nomes_meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    consumo_total_periodo = 0.0
    consumo_por_dia = {}
    consumo_por_mes = {}

    for hidrometro in hidrometros:
        leituras = hidrometro.leituras.filter(
            data_leitura__date__gte=data_inicio,
            data_leitura__date__lte=data_fim
        ).order_by('data_leitura')

        for i in range(1, len(leituras)):
            leitura_atual = leituras[i]
            leitura_anterior = leituras[i - 1]
            diferenca = float(leitura_atual.leitura - leitura_anterior.leitura)
            if diferenca <= 0:
                continue

            consumo_litros = diferenca * 1000
            consumo_total_periodo += consumo_litros

            dia = leitura_atual.data_leitura.date()
            consumo_por_dia[dia] = consumo_por_dia.get(dia, 0.0) + consumo_litros

            mes_key = (leitura_atual.data_leitura.year, leitura_atual.data_leitura.month)
            consumo_por_mes[mes_key] = consumo_por_mes.get(mes_key, 0.0) + consumo_litros

    datas_periodo = []
    dia_cursor = data_inicio
    while dia_cursor <= data_fim:
        datas_periodo.append(dia_cursor)
        consumo_por_dia.setdefault(dia_cursor, 0.0)
        dia_cursor += timedelta(days=1)

    meses_periodo = []
    mes_cursor = data_inicio.replace(day=1)
    while mes_cursor <= data_fim:
        meses_periodo.append((mes_cursor.year, mes_cursor.month))
        if mes_cursor.month == 12:
            mes_cursor = mes_cursor.replace(year=mes_cursor.year + 1, month=1)
        else:
            mes_cursor = mes_cursor.replace(month=mes_cursor.month + 1)
    
    
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
    elements.append(Paragraph(f"Relatório de Consumo - Lote {lote.numero} ({periodo_label})", title_style))
    elements.append(Paragraph(
        f"Tipo: {lote.get_tipo_display()} | Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')} | Gerado em: {agora.strftime('%d/%m/%Y %H:%M')}",
        subtitle_style
    ))
    elements.append(Spacer(1, 0.3*inch))
    
    # Resumo Geral
    elements.append(Paragraph("📊 Resumo Geral", heading_style))
    
    resumo_data = [
        ['Indicador', 'Valor'],
        ['Lote', lote.numero],
        ['Tipo', lote.get_tipo_display()],
        ['Período', periodo_label],
        ['Consumo Total no Período', f'{consumo_total_periodo:,.0f} L'],
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
    for (ano, mes) in meses_periodo:
        mes_nome = f'{nomes_meses[mes - 1]}/{str(ano)[-2:]}'
        mensal_data.append([mes_nome, f'{consumo_por_mes.get((ano, mes), 0.0):,.2f}'])
    
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
    meses_labels = [f'{nomes_meses[mes - 1]}/{str(ano)[-2:]}' for (ano, mes) in meses_periodo]
    valores_mensais = [consumo_por_mes.get((ano, mes), 0.0) for (ano, mes) in meses_periodo]
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

    leituras_periodo = Leitura.objects.filter(
        hidrometro__lote=lote,
        data_leitura__date__gte=data_inicio,
        data_leitura__date__lte=data_fim
    ).select_related('hidrometro').order_by('data_leitura')

    elements.append(PageBreak())
    elements.append(Paragraph("📋 Leituras no Período", heading_style))

    leituras_data = [[
        'Data/Hora',
        'Hidrômetro',
        'Leitura (m³)',
        'Consumo (L)',
        'Responsável',
        'Observações'
    ]]

    for leitura in leituras_periodo:
        consumo_litros = leitura.consumo_desde_ultima_leitura_litros()
        responsavel = leitura.responsavel or 'N/A'
        observacoes = leitura.observacoes or '—'
        if len(observacoes) > 60:
            observacoes = f"{observacoes[:57]}..."
        leituras_data.append([
            leitura.data_leitura.strftime('%d/%m/%Y %H:%M'),
            leitura.hidrometro.numero,
            f"{leitura.leitura}",
            f"{consumo_litros:,.0f}",
            responsavel,
            observacoes,
        ])

    leituras_table = Table(
        leituras_data,
        colWidths=[1.4*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.2*inch, 2.1*inch]
    )
    leituras_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))

    elements.append(leituras_table)
    elements.append(Spacer(1, 0.3*inch))

    leituras_com_foto = [leitura for leitura in leituras_periodo if leitura.foto]
    if leituras_com_foto:
        elements.append(PageBreak())
        elements.append(Paragraph("📷 Fotos das Leituras", heading_style))
        for leitura in leituras_com_foto:
            foto_path = getattr(leitura.foto, 'path', '')
            if not foto_path or not os.path.exists(foto_path):
                continue
            legenda = (
                f"Hidrômetro {leitura.hidrometro.numero} - "
                f"{leitura.data_leitura.strftime('%d/%m/%Y %H:%M')}"
            )
            elements.append(Paragraph(legenda, styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Image(foto_path, width=6.5*inch, height=3.8*inch))
            elements.append(Spacer(1, 0.2*inch))
    
    
    # Construir PDF
    doc.build(elements)
    
    # Preparar resposta
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="relatorio_lote_{lote.numero}_{data_inicio.strftime("%Y%m%d")}_'
        f'{data_fim.strftime("%Y%m%d")}.pdf"'
    )
    
    return response


def exportar_graficos_lote_excel(request, lote_id):
    """Exporta os gráficos de consumo de um lote específico em Excel com gráficos"""
    import os
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    lote = get_object_or_404(Lote, id=lote_id)
    
    # Obter dados do lote (mesma lógica da view graficos_lote)
    agora = timezone.localtime(timezone.now())
    hoje = agora.date()
    periodo = request.GET.get('periodo', '30dias')
    data_inicio_str = request.GET.get('data_inicio', '')
    data_fim_str = request.GET.get('data_fim', '')
    data_fim = hoje
    periodo_label = ''

    if periodo == '7dias':
        data_inicio = hoje - timedelta(days=7)
        periodo_label = 'Últimos 7 dias'
    elif periodo == '15dias':
        data_inicio = hoje - timedelta(days=15)
        periodo_label = 'Últimos 15 dias'
    elif periodo == '30dias':
        data_inicio = hoje - timedelta(days=30)
        periodo_label = 'Últimos 30 dias'
    elif periodo == 'mes_atual':
        data_inicio = hoje.replace(day=1)
        periodo_label = f'{hoje.strftime("%B de %Y").capitalize()}'
    elif periodo == 'ano_atual':
        data_inicio = hoje.replace(month=1, day=1)
        periodo_label = f'Ano de {hoje.year}'
    elif periodo == 'personalizado' and data_inicio_str and data_fim_str:
        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            if data_fim > hoje:
                data_fim = hoje
            periodo_label = f'{data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}'
        except (ValueError, TypeError):
            data_inicio = hoje - timedelta(days=30)
            data_fim = hoje
            periodo_label = 'Últimos 30 dias'
            periodo = '30dias'
    else:
        data_inicio = hoje - timedelta(days=30)
        periodo_label = 'Últimos 30 dias'
    
    hidrometros = lote.hidrometros.filter(ativo=True)
    
    if not hidrometros.exists():
        return HttpResponse("Nenhum hidrômetro ativo encontrado para este lote.", status=404)
    
    # Calcular consumo no periodo
    nomes_meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    consumo_total_periodo = 0.0
    consumo_por_dia = {}
    consumo_por_mes = {}

    for hidrometro in hidrometros:
        leituras = hidrometro.leituras.filter(
            data_leitura__date__gte=data_inicio,
            data_leitura__date__lte=data_fim
        ).order_by('data_leitura')

        for i in range(1, len(leituras)):
            leitura_atual = leituras[i]
            leitura_anterior = leituras[i - 1]
            diferenca = float(leitura_atual.leitura - leitura_anterior.leitura)
            if diferenca <= 0:
                continue

            consumo_litros = diferenca * 1000
            consumo_total_periodo += consumo_litros

            dia = leitura_atual.data_leitura.date()
            consumo_por_dia[dia] = consumo_por_dia.get(dia, 0.0) + consumo_litros

            mes_key = (leitura_atual.data_leitura.year, leitura_atual.data_leitura.month)
            consumo_por_mes[mes_key] = consumo_por_mes.get(mes_key, 0.0) + consumo_litros

    datas_periodo = []
    dia_cursor = data_inicio
    while dia_cursor <= data_fim:
        datas_periodo.append(dia_cursor)
        consumo_por_dia.setdefault(dia_cursor, 0.0)
        dia_cursor += timedelta(days=1)

    meses_periodo = []
    mes_cursor = data_inicio.replace(day=1)
    while mes_cursor <= data_fim:
        meses_periodo.append((mes_cursor.year, mes_cursor.month))
        if mes_cursor.month == 12:
            mes_cursor = mes_cursor.replace(year=mes_cursor.year + 1, month=1)
        else:
            mes_cursor = mes_cursor.replace(month=mes_cursor.month + 1)
    
    
    # Criar Excel
    wb = Workbook()
    
    # Aba: Resumo
    ws_resumo = wb.active
    ws_resumo.title = "Resumo"
    
    # Título
    ws_resumo['A1'] = f'Relatório de Consumo - Lote {lote.numero} ({periodo_label})'
    ws_resumo['A1'].font = Font(size=16, bold=True, color='FFFFFF')
    ws_resumo['A1'].fill = PatternFill(start_color='3498db', end_color='3498db', fill_type='solid')
    ws_resumo['A1'].alignment = Alignment(horizontal='center')
    ws_resumo.merge_cells('A1:C1')
    
    ws_resumo['A2'] = (
        f'Tipo: {lote.get_tipo_display()} | Período: {data_inicio.strftime("%d/%m/%Y")} '
        f'a {data_fim.strftime("%d/%m/%Y")} | Gerado em: {agora.strftime("%d/%m/%Y %H:%M")}'
    )
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
        ['Período', periodo_label],
        ['Consumo Total no Período', f'{consumo_total_periodo:,.0f} L'],
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
    
    for idx, (ano, mes) in enumerate(meses_periodo, start=2):
        ws_mensal[f'A{idx}'] = f'{nomes_meses[mes - 1]}/{str(ano)[-2:]}'
        ws_mensal[f'B{idx}'] = round(consumo_por_mes.get((ano, mes), 0.0), 2)
    
    # Gerar gráfico com matplotlib (igual ao PDF)
    plt.figure(figsize=(12, 6))
    meses_labels = [f'{nomes_meses[mes - 1]}/{str(ano)[-2:]}' for (ano, mes) in meses_periodo]
    valores_mensais = [consumo_por_mes.get((ano, mes), 0.0) for (ano, mes) in meses_periodo]
    plt.bar(meses_labels, valores_mensais, color='#27ae60', alpha=0.7)
    plt.title(f'Consumo Mensal - Lote {lote.numero} (Litros)', fontsize=14, fontweight='bold')
    plt.xlabel('Mês', fontsize=11)
    plt.ylabel('Consumo (L)', fontsize=11)
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    # Salvar gráfico em buffer
    img_buffer_mensal = io.BytesIO()
    plt.savefig(img_buffer_mensal, format='png', dpi=100, bbox_inches='tight')
    img_buffer_mensal.seek(0)
    plt.close()
    
    # Adicionar imagem ao Excel
    from openpyxl.drawing.image import Image as XLImage
    img_mensal = XLImage(img_buffer_mensal)
    img_mensal.width = 600
    img_mensal.height = 300
    ws_mensal.add_image(img_mensal, "D2")
    
    ws_mensal.column_dimensions['A'].width = 15
    ws_mensal.column_dimensions['B'].width = 15
    
    # Aba: Consumo Diário
    ws_diario_lote = wb.create_sheet("Consumo Diário")
    
    ws_diario_lote['A1'] = 'Dia'
    ws_diario_lote['B1'] = 'Consumo (L)'
    ws_diario_lote['A1'].font = Font(bold=True)
    ws_diario_lote['B1'].font = Font(bold=True)
    
    for idx, dia in enumerate(datas_periodo, start=2):
        ws_diario_lote[f'A{idx}'] = dia.strftime('%d/%m/%Y')
        ws_diario_lote[f'B{idx}'] = round(consumo_por_dia.get(dia, 0.0), 2)
    
    # Gerar gráfico com matplotlib (igual ao PDF)
    plt.figure(figsize=(12, 6))
    dias_labels = [d.strftime('%d/%m') for d in datas_periodo]
    valores_diarios_lote = [consumo_por_dia.get(d, 0.0) for d in datas_periodo]
    plt.plot(dias_labels, valores_diarios_lote, marker='o', color='#3498db', linewidth=2, markersize=4)
    plt.title(f'Consumo Diário - Lote {lote.numero} ({periodo_label})', fontsize=14, fontweight='bold')
    plt.xlabel('Dia', fontsize=11)
    plt.ylabel('Consumo (L)', fontsize=11)
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    # Salvar gráfico em buffer
    img_buffer_diario_lote = io.BytesIO()
    plt.savefig(img_buffer_diario_lote, format='png', dpi=100, bbox_inches='tight')
    img_buffer_diario_lote.seek(0)
    plt.close()
    
    # Adicionar imagem ao Excel
    img_diario_lote = XLImage(img_buffer_diario_lote)
    img_diario_lote.width = 600
    img_diario_lote.height = 300
    ws_diario_lote.add_image(img_diario_lote, "D2")
    
    ws_diario_lote.column_dimensions['A'].width = 15
    ws_diario_lote.column_dimensions['B'].width = 15

    leituras_periodo = Leitura.objects.filter(
        hidrometro__lote=lote,
        data_leitura__date__gte=data_inicio,
        data_leitura__date__lte=data_fim
    ).select_related('hidrometro').order_by('data_leitura')

    ws_leituras = wb.create_sheet("Leituras")
    ws_leituras['A1'] = 'Data/Hora'
    ws_leituras['B1'] = 'Hidrômetro'
    ws_leituras['C1'] = 'Leitura (m³)'
    ws_leituras['D1'] = 'Consumo (L)'
    ws_leituras['E1'] = 'Responsável'
    ws_leituras['F1'] = 'Observações'
    ws_leituras['G1'] = 'Foto'

    for col in ['A1', 'B1', 'C1', 'D1', 'E1', 'F1', 'G1']:
        ws_leituras[col].font = Font(bold=True)

    for idx, leitura in enumerate(leituras_periodo, start=2):
        consumo_litros = leitura.consumo_desde_ultima_leitura_litros()
        ws_leituras[f'A{idx}'] = leitura.data_leitura.strftime('%d/%m/%Y %H:%M')
        ws_leituras[f'B{idx}'] = leitura.hidrometro.numero
        ws_leituras[f'C{idx}'] = float(leitura.leitura)
        ws_leituras[f'D{idx}'] = round(consumo_litros, 2)
        ws_leituras[f'E{idx}'] = leitura.responsavel or 'N/A'
        ws_leituras[f'F{idx}'] = leitura.observacoes or '—'

        if leitura.foto:
            foto_path = getattr(leitura.foto, 'path', '')
            if foto_path and os.path.exists(foto_path):
                img = XLImage(foto_path)
                img.width = 120
                img.height = 90
                ws_leituras.add_image(img, f'G{idx}')
                ws_leituras.row_dimensions[idx].height = 70

    ws_leituras.column_dimensions['A'].width = 18
    ws_leituras.column_dimensions['B'].width = 15
    ws_leituras.column_dimensions['C'].width = 14
    ws_leituras.column_dimensions['D'].width = 14
    ws_leituras.column_dimensions['E'].width = 18
    ws_leituras.column_dimensions['F'].width = 40
    ws_leituras.column_dimensions['G'].width = 22
    
    # Salvar e retornar
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="relatorio_lote_{lote.numero}_{data_inicio.strftime("%Y%m%d")}_'
        f'{data_fim.strftime("%Y%m%d")}.xlsx"'
    )
    
    return response

