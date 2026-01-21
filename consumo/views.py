from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Avg, Max, Min, Count
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import timedelta, datetime
import json

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
    """Página com gráficos de consumo"""
    return render(request, 'consumo/graficos_consumo.html')

