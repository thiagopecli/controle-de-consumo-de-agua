from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db.models import Sum, Avg, Max, Min, Count, Q, Case, When, Value, IntegerField
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import timedelta, datetime
import json
import io
import os
import hmac
import logging
import zipfile
import glob
import mimetypes
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.utils import ImageReader

from .forms import CadastroUsuarioForm, LoginForm
from .models import Lote, Hidrometro, Leitura
from .services.relatorios_cache import calcular_data_coleta, pasta_relatorios_coleta
from .services.whatsapp import processar_webhook_desconexao_whatsapp
from .serializers import (
    LoteSerializer, 
    HidrometroSerializer, 
    LeituraSerializer,
    LeituraCreateSerializer
)


LOGGER = logging.getLogger(__name__)


# Mapeamento de meses em português do Brasil
MESES_PT_BR = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}


def usuario_eh_administracao(user):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True

    perfil = getattr(user, 'perfil', None)
    return bool(perfil and perfil.tipo_acesso == 'administracao')


def _redirecionar_pos_login(user):
    if usuario_eh_administracao(user):
        return redirect('consumo:dashboard')
    return redirect('consumo:registrar_leitura')


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not usuario_eh_administracao(request.user):
            return redirect('consumo:acesso_negado')
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def formatar_mes_ano_ptbr(data):
    """Retorna string formatada 'Mês/Ano' em português do Brasil"""
    mes_nome = MESES_PT_BR[data.month]
    return f"{mes_nome}/{data.year}"


def _obter_caminho_logo_marca_dagua():
    caminhos = [
        os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.jpeg'),
        os.path.join(settings.BASE_DIR, 'logo.jpeg'),
    ]
    for caminho in caminhos:
        if os.path.exists(caminho):
            return caminho
    return None


def _desenhar_marca_dagua_logo(canvas, doc):
    caminho_logo = _obter_caminho_logo_marca_dagua()
    if not caminho_logo:
        return

    try:
        pagina_largura, pagina_altura = doc.pagesize
        imagem = ImageReader(caminho_logo)
        img_largura, img_altura = imagem.getSize()
        proporcao = img_altura / float(img_largura) if img_largura else 1

        logo_largura = pagina_largura * 0.45
        logo_altura = logo_largura * proporcao

        if logo_altura > pagina_altura * 0.6:
            logo_altura = pagina_altura * 0.6
            logo_largura = logo_altura / proporcao if proporcao else logo_largura

        pos_x = (pagina_largura - logo_largura) / 2
        pos_y = (pagina_altura - logo_altura) / 2

        canvas.saveState()
        if hasattr(canvas, 'setFillAlpha'):
            canvas.setFillAlpha(0.08)
        canvas.drawImage(
            caminho_logo,
            pos_x,
            pos_y,
            width=logo_largura,
            height=logo_altura,
            preserveAspectRatio=True,
            mask='auto'
        )
        canvas.restoreState()
    except Exception:
        return


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
@admin_required
def dashboard(request):
    """Dashboard principal"""
    total_lotes = Lote.objects.filter(ativo=True).count()
    total_hidrometros = Hidrometro.objects.filter(ativo=True).count()

    hoje = timezone.localdate()
    inicio_dia = timezone.make_aware(
        datetime.combine(hoje, datetime.min.time()),
        timezone.get_current_timezone()
    )
    fim_dia = inicio_dia + timedelta(days=1)
    leituras_hoje = Leitura.objects.filter(
        data_leitura__gte=inicio_dia,
        data_leitura__lt=fim_dia,
    ).count()
    
    context = {
        'total_lotes': total_lotes,
        'total_hidrometros': total_hidrometros,
        'leituras_hoje': leituras_hoje,
    }
    
    return render(request, 'consumo/dashboard.html', context)


def offline_page(request):
    """Página exibida quando o usuário está sem conexão"""
    return render(request, 'consumo/offline.html')


def service_worker(request):
    """Entrega o service worker na raiz para permitir escopo global"""
    response = render(
        request,
        'consumo/service-worker.js',
        {'app_version': getattr(settings, 'APP_VERSION', '1.0.0')},
        content_type='application/javascript'
    )
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


def login_view(request):
    if request.user.is_authenticated:
        return _redirecionar_pos_login(request.user)

    max_tentativas = getattr(settings, 'LOGIN_MAX_ATTEMPTS', 5)
    tempo_bloqueio = getattr(settings, 'LOGIN_LOCKOUT_SECONDS', 900)

    identificador_raw = (request.POST.get('username') or '').strip() if request.method == 'POST' else ''
    identificador_normalizado = identificador_raw.lower()
    ip = (request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or 'desconhecido').split(',')[0].strip()

    chave_falhas_ip = f'auth:falhas:ip:{ip}'
    chave_bloqueio_ip = f'auth:bloqueio:ip:{ip}'
    chave_falhas_identificador = f'auth:falhas:identificador:{ip}:{identificador_normalizado}' if identificador_normalizado else None
    chave_bloqueio_identificador = f'auth:bloqueio:identificador:{ip}:{identificador_normalizado}' if identificador_normalizado else None

    bloqueado = bool(cache.get(chave_bloqueio_ip))
    if chave_bloqueio_identificador:
        bloqueado = bloqueado or bool(cache.get(chave_bloqueio_identificador))

    form = LoginForm(request=request, data=request.POST or None)
    if request.method == 'POST' and bloqueado:
        form.add_error(None, 'Muitas tentativas de login. Aguarde alguns minutos e tente novamente.')
        return render(request, 'consumo/login.html', {'form': form, 'next': request.GET.get('next', '')})

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)

        cache.delete(chave_falhas_ip)
        cache.delete(chave_bloqueio_ip)
        if chave_falhas_identificador:
            cache.delete(chave_falhas_identificador)
        if chave_bloqueio_identificador:
            cache.delete(chave_bloqueio_identificador)

        next_url = request.POST.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)

        return _redirecionar_pos_login(user)

    if request.method == 'POST' and not form.is_valid():
        falhas_ip = cache.get(chave_falhas_ip, 0) + 1
        cache.set(chave_falhas_ip, falhas_ip, timeout=tempo_bloqueio)

        if falhas_ip >= max_tentativas:
            cache.set(chave_bloqueio_ip, True, timeout=tempo_bloqueio)

        if chave_falhas_identificador and chave_bloqueio_identificador:
            falhas_identificador = cache.get(chave_falhas_identificador, 0) + 1
            cache.set(chave_falhas_identificador, falhas_identificador, timeout=tempo_bloqueio)
            if falhas_identificador >= max_tentativas:
                cache.set(chave_bloqueio_identificador, True, timeout=tempo_bloqueio)

    context = {
        'form': form,
        'next': request.GET.get('next', ''),
    }
    return render(request, 'consumo/login.html', context)


def logout_view(request):
    logout(request)
    return redirect('consumo:login')


def cadastro_usuario(request):
    if request.user.is_authenticated:
        return _redirecionar_pos_login(request.user)

    form = CadastroUsuarioForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Cadastro enviado com sucesso. Aguarde aprovacao do superusuario para acessar o sistema.')
        return redirect('consumo:login')

    return render(request, 'consumo/cadastro_usuario.html', {'form': form})


@login_required
def acesso_negado(request):
    return render(request, 'consumo/acesso_negado.html', status=403)


@login_required
def inicio(request):
    return _redirecionar_pos_login(request.user)


@csrf_exempt
def pregerar_relatorios_job(request):
    """
    Endpoint interno para disparar pregeração de PDFs no serviço web.
    Assim os arquivos são gerados onde o disco persistente e as fotos existem.
    """
    if request.method != 'POST':
        return JsonResponse({'erro': 'Metodo nao permitido'}, status=405)

    token_configurado = os.getenv('JOB_SECRET_TOKEN', '').strip()
    token_recebido = (request.headers.get('X-Job-Token') or '').strip()

    if not token_configurado:
        return JsonResponse({'erro': 'Servico indisponivel: JOB_SECRET_TOKEN nao configurado'}, status=503)

    if not token_recebido or not hmac.compare_digest(token_recebido, token_configurado):
        return JsonResponse({'erro': 'Nao autorizado'}, status=401)

    data_coleta = request.GET.get('data_coleta') or request.POST.get('data_coleta')
    sobrescrever_raw = request.GET.get('sobrescrever') or request.POST.get('sobrescrever')
    base_url = request.GET.get('base_url') or request.POST.get('base_url')
    lote_numero = request.GET.get('lote_numero') or request.POST.get('lote_numero')
    intervalo_segundos = request.GET.get('intervalo_segundos') or request.POST.get('intervalo_segundos')
    tentativas = request.GET.get('tentativas') or request.POST.get('tentativas')
    permitir_lotes_incompletos_raw = (
        request.GET.get('permitir_lotes_incompletos')
        or request.POST.get('permitir_lotes_incompletos')
        or request.GET.get('permitir-lotes-incompletos')
        or request.POST.get('permitir-lotes-incompletos')
    )
    sobrescrever = str(sobrescrever_raw).lower() in {'1', 'true', 'yes', 'sim'}
    permitir_lotes_incompletos = str(permitir_lotes_incompletos_raw).lower() in {
        '1',
        'true',
        'yes',
        'sim',
    }

    output = io.StringIO()
    kwargs = {'stdout': output, 'stderr': output}
    if data_coleta:
        kwargs['data_coleta'] = data_coleta
    if sobrescrever:
        kwargs['sobrescrever'] = True
    if base_url:
        kwargs['base_url'] = base_url
    if lote_numero:
        kwargs['lote_numero'] = lote_numero
    if intervalo_segundos:
        kwargs['intervalo_segundos'] = intervalo_segundos
    if tentativas:
        kwargs['tentativas'] = tentativas
    if permitir_lotes_incompletos:
        kwargs['permitir_lotes_incompletos'] = True

    try:
        call_command('pregerar_relatorios_mensais', **kwargs)
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(
            {
                'ok': False,
                'erro': str(exc),
                'output': output.getvalue(),
            },
            status=500,
        )

    return JsonResponse(
        {
            'ok': True,
            'output': output.getvalue(),
        }
    )


@csrf_exempt
def webhook_zapi_desconectado(request):
    """
    Webhook chamado pela Z-API quando a instancia perde conexao.
    """
    if request.method not in {'POST', 'PUT'}:
        return JsonResponse({'erro': 'Metodo nao permitido'}, status=405)

    segredo_configurado = os.getenv('ZAPI_WEBHOOK_SECRET', '').strip()
    segredo_recebido = (
        request.headers.get('X-ZAPI-Webhook-Secret')
        or request.headers.get('X-Webhook-Token')
        or ''
    ).strip()

    if segredo_configurado and not hmac.compare_digest(segredo_recebido, segredo_configurado):
        return JsonResponse({'erro': 'Nao autorizado'}, status=401)

    try:
        payload = json.loads((request.body or b'{}').decode('utf-8'))
    except Exception:
        payload = {}

    try:
        resultado = processar_webhook_desconexao_whatsapp(payload=payload)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception('Falha ao processar webhook de desconexao da Z-API: %s', exc)
        return JsonResponse({'ok': False, 'erro': str(exc)}, status=500)

    status_http = 200 if resultado.get('ok') else 202
    return JsonResponse({'ok': bool(resultado.get('ok')), 'resultado': resultado}, status=status_http)


@csrf_exempt
def webhook_zapi_conectado(request):
    """
    Webhook de auditoria de reconexao/conexao da Z-API.
    """
    if request.method not in {'POST', 'PUT'}:
        return JsonResponse({'erro': 'Metodo nao permitido'}, status=405)

    segredo_configurado = os.getenv('ZAPI_WEBHOOK_SECRET', '').strip()
    segredo_recebido = (
        request.headers.get('X-ZAPI-Webhook-Secret')
        or request.headers.get('X-Webhook-Token')
        or ''
    ).strip()

    if segredo_configurado and not hmac.compare_digest(segredo_recebido, segredo_configurado):
        return JsonResponse({'erro': 'Nao autorizado'}, status=401)

    try:
        payload = json.loads((request.body or b'{}').decode('utf-8'))
    except Exception:
        payload = {}

    LOGGER.info('Webhook conectado recebido da Z-API: %s', payload)
    return JsonResponse({'ok': True})


@admin_required
def listar_hidrometros(request):
    """Lista todos os hidrômetros com paginação"""
    from django.core.paginator import Paginator

    hoje = timezone.localdate()
    inicio_dia = timezone.make_aware(
        datetime.combine(hoje, datetime.min.time()),
        timezone.get_current_timezone()
    )
    fim_dia = inicio_dia + timedelta(days=1)
    
    # Query base
    hidrometros_list = (
        Hidrometro.objects.filter(ativo=True)
        .select_related('lote')
        .annotate(
            leituras_hoje=Count(
                'leituras',
                filter=Q(
                    leituras__data_leitura__gte=inicio_dia,
                    leituras__data_leitura__lt=fim_dia,
                ),
            ),
            ultima_leitura=Max('leituras__data_leitura'),
            # Cria um campo de ordenação: administração = 0, residencial = 1
            ordem_tipo=Case(
                When(lote__tipo='administracao', then=Value(0)),
                default=Value(1),
                output_field=IntegerField()
            )
        )
    )
    
    # Filtro de busca
    search_query = request.GET.get('search', '').strip()
    if search_query:
        # Busca por número do hidrômetro OU número do lote
        hidrometros_list = hidrometros_list.filter(
            Q(numero__icontains=search_query) | 
            Q(lote__numero__icontains=search_query)
        )
    
    # Ordena: primeiro administração (ordem_tipo=0), depois residenciais (ordem_tipo=1), ambos por número crescente
    hidrometros_list = hidrometros_list.order_by('ordem_tipo', 'numero')
    
    # Paginação: 50 hidrômetros por página
    paginator = Paginator(hidrometros_list, 50)
    page_number = request.GET.get('page', 1)
    hidrometros = paginator.get_page(page_number)
    
    context = {
        'hidrometros': hidrometros,
        'search_query': search_query,
    }
    
    return render(request, 'consumo/listar_hidrometros.html', context)


@login_required
def listar_leituras(request):
    """Lista todas as leituras com paginação"""
    from django.core.paginator import Paginator
    
    # Query base
    leituras_list = (
        Leitura.objects.all()
        .select_related('hidrometro__lote')
        .order_by('-data_leitura')
    )

    # Filtro de busca
    search_query = request.GET.get('search', '').strip()
    if search_query:
        # Busca por número do hidrômetro OU número do lote
        leituras_list = leituras_list.filter(
            Q(hidrometro__numero__icontains=search_query) | 
            Q(hidrometro__lote__numero__icontains=search_query)
        )

    # Paginação: 50 leituras por página
    paginator = Paginator(leituras_list, 50)
    page_number = request.GET.get('page', 1)
    leituras = paginator.get_page(page_number)
    total_leituras = paginator.count

    for leitura in leituras:
        leitura.foto_disponivel = False
        if leitura.foto and leitura.foto.name:
            try:
                leitura.foto_disponivel = leitura.foto.storage.exists(leitura.foto.name)
            except Exception:
                leitura.foto_disponivel = False
    
    context = {
        'leituras': leituras,
        'total_leituras': total_leituras,
        'search_query': search_query,
    }
    
    return render(request, 'consumo/listar_leituras.html', context)


@login_required
def visualizar_foto_leitura(request, leitura_id):
    leitura = get_object_or_404(Leitura, id=leitura_id)
    if not leitura.foto:
        raise Http404('Leitura sem foto anexada.')

    if not leitura.foto.name or not leitura.foto.storage.exists(leitura.foto.name):
        return HttpResponse(
            'Foto indisponivel: o arquivo nao foi encontrado no armazenamento local.',
            status=404,
            content_type='text/plain; charset=utf-8'
        )

    nome_arquivo = leitura.foto.name.split('/')[-1]
    tipo_conteudo, _ = mimetypes.guess_type(nome_arquivo)
    tipo_conteudo = tipo_conteudo or 'application/octet-stream'

    try:
        leitura.foto.open('rb')
    except FileNotFoundError:
        return HttpResponse(
            'Foto indisponivel: o arquivo foi removido ou nao existe neste ambiente.',
            status=404,
            content_type='text/plain; charset=utf-8'
        )

    response = FileResponse(leitura.foto, content_type=tipo_conteudo)
    response['Content-Disposition'] = f'inline; filename="{nome_arquivo}"'
    return response


@login_required
def registrar_leitura(request):
    """Formulário para registrar leituras"""
    hidrometros_queryset = Hidrometro.objects.filter(ativo=True).select_related('lote')

    def chave_natural(texto):
        import re
        partes = re.split(r'(\d+)', (texto or '').strip().lower())
        return [int(parte) if parte.isdigit() else parte for parte in partes]

    def chave_ordenacao_hidrometro(hidrometro):
        tipo_prioridade = 0 if hidrometro.lote.tipo == 'administracao' else 1
        if tipo_prioridade == 0:
            return (tipo_prioridade, chave_natural(hidrometro.numero), chave_natural(hidrometro.lote.numero))
        return (tipo_prioridade, chave_natural(hidrometro.lote.numero), chave_natural(hidrometro.numero))

    hidrometros = sorted(hidrometros_queryset, key=chave_ordenacao_hidrometro)
    nome_responsavel = (request.user.get_full_name() or '').strip() or request.user.username
    
    context = {
        'hidrometros': hidrometros,
        'nome_responsavel': nome_responsavel,
    }
    
    return render(request, 'consumo/registrar_leitura.html', context)


@admin_required
def detalhes_hidrometro(request, hidrometro_id):
    """Página com detalhes e histórico de leituras do hidrômetro com filtros e gráficos"""
    from datetime import timedelta
    from django.db.models import Sum
    from collections import defaultdict
    import calendar
    
    hidrometro = get_object_or_404(Hidrometro, id=hidrometro_id)
    
    # Obter filtros de período
    periodo = request.GET.get('periodo', 'ano_atual')
    data_inicio_str = request.GET.get('data_inicio', '')
    data_fim_str = request.GET.get('data_fim', '')
    
    hoje = timezone.localdate()
    data_inicio = None
    data_fim = hoje
    periodo_label = ''
    
    # Definir período baseado no filtro
    if periodo == 'ano_atual':
        data_inicio = hoje.replace(month=1, day=1)
        periodo_label = f'Ano de {hoje.year}'
    elif periodo == 'personalizado' and data_inicio_str and data_fim_str:
        try:
            from datetime import datetime
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            periodo_label = f'{data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}'
        except:
            data_inicio = hoje.replace(month=1, day=1)
            data_fim = hoje
            periodo_label = f'Ano de {hoje.year}'
            periodo = 'ano_atual'
    else:
        data_inicio = hoje.replace(month=1, day=1)
        periodo_label = f'Ano de {hoje.year}'
    
# Buscar última leitura ANTES do período (para ter base de comparação)
    leitura_anterior_periodo = hidrometro.leituras.filter(
        data_leitura__date__lt=data_inicio
    ).order_by('-data_leitura').first()

    # Obter leituras do período
    leituras_periodo = list(hidrometro.leituras.filter(
        data_leitura__date__gte=data_inicio,
        data_leitura__date__lte=data_fim
    ).order_by('-data_leitura'))

    # Obter todas as leituras para o histórico completo (limitado)
    leituras_historico = hidrometro.leituras.all().order_by('-data_leitura')[:50]

    # Preparar leituras ordenadas (combinar anterior + período)
    leituras_para_calculo = list(hidrometro.leituras.filter(
        data_leitura__date__gte=data_inicio,
        data_leitura__date__lte=data_fim
    ).order_by('data_leitura'))

    if leitura_anterior_periodo:
        leituras_para_calculo = [leitura_anterior_periodo] + leituras_para_calculo

    # Calcular consumo total no período
    consumo_total_periodo = 0

    for i in range(1, len(leituras_para_calculo)):
        leitura_atual = leituras_para_calculo[i]
        leitura_anterior = leituras_para_calculo[i - 1]

        # Só contabilizar se a leitura ATUAL estiver dentro do período filtrado
        if leitura_atual.data_leitura.date() < data_inicio:
            continue

        diferenca = float(leitura_atual.leitura) - float(leitura_anterior.leitura)
        if diferenca > 0:
            consumo_litros = diferenca * 1000
            consumo_total_periodo += consumo_litros

    # Preparar dados para gráficos
    # Gráfico 1: Consumo por Dia
    consumo_por_dia = defaultdict(float)
    for i in range(1, len(leituras_para_calculo)):
        leitura_atual = leituras_para_calculo[i]
        leitura_anterior = leituras_para_calculo[i - 1]

        # Só contabilizar se a leitura ATUAL estiver dentro do período filtrado
        if leitura_atual.data_leitura.date() < data_inicio:
            continue

        diferenca = float(leitura_atual.leitura) - float(leitura_anterior.leitura)
        if diferenca > 0:
            consumo_litros = diferenca * 1000
            dia_str = leitura_atual.data_leitura.strftime('%d/%m')
            consumo_por_dia[dia_str] += consumo_litros

    consumo_dia_lista = [
        {'dia': dia, 'consumo_litros': consumo}
        for dia, consumo in sorted(consumo_por_dia.items())
    ]

    # Gráfico 2: Consumo por Mês (sempre exibe todos os 12 meses)
    # Inicializar todos os meses com 0
    consumo_por_mes = {mes: 0.0 for mes in range(1, 13)}
    for i in range(1, len(leituras_para_calculo)):
        leitura_atual = leituras_para_calculo[i]
        leitura_anterior = leituras_para_calculo[i - 1]

        # Só contabilizar se a leitura ATUAL estiver dentro do período filtrado
        if leitura_atual.data_leitura.date() < data_inicio:
            continue

        diferenca = float(leitura_atual.leitura) - float(leitura_anterior.leitura)
        if diferenca > 0:
            consumo_litros = diferenca * 1000
            mes_numero = leitura_atual.data_leitura.month
            consumo_por_mes[mes_numero] += consumo_litros
    
    # Sempre exibir todos os 12 meses em português
    consumo_mes_lista = []
    for mes in range(1, 13):
        mes_nome = MESES_PT_BR[mes]
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


@admin_required
def graficos_consumo(request):
    """Página com gráficos de consumo do condomínio com filtro de período."""

    LIMITE_MENSAL_LITROS = 15000

    agora = timezone.localtime(timezone.now())
    ultima_coleta = Leitura.objects.filter(
        hidrometro__ativo=True,
        hidrometro__lote__tipo='residencial'
    ).aggregate(ultima=Max('data_leitura'))['ultima']

    if ultima_coleta:
        hoje = timezone.localtime(ultima_coleta) if timezone.is_aware(ultima_coleta) else timezone.make_aware(ultima_coleta)
    else:
        hoje = agora

    ano_atual = hoje.year

    def _inicio_mes_menos(data_referencia, meses_anteriores):
        total_meses = data_referencia.year * 12 + (data_referencia.month - 1) - meses_anteriores
        ano = total_meses // 12
        mes = (total_meses % 12) + 1
        return data_referencia.replace(year=ano, month=mes, day=1, hour=0, minute=0, second=0, microsecond=0)

    # Obter o período selecionado (padrão: ano atual)
    periodo_selecionado = request.GET.get('periodo', 'ano_atual')

    # Definir data de início baseada no período selecionado
    if periodo_selecionado == 'ano_atual':
        # Ano atual (de 1º de janeiro até hoje)
        data_inicio_ano = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
        data_inicio_dias = data_inicio_ano
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
                periodo_label = f"{data_inicio_dias.strftime('%d/%m/%Y')} até {data_fim_personalizada.strftime('%d/%m/%Y')}"
                hoje = data_fim_personalizada  # Usar data_fim personalizada
            except (ValueError, TypeError):
                # Se houver erro, usar padrão (ano atual)
                data_inicio_dias = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
                data_inicio_ano = data_inicio_dias
                periodo_label = f"Ano Atual ({ano_atual})"
        else:
            # Sem datas fornecidas, usar padrão
            data_inicio_dias = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
            data_inicio_ano = data_inicio_dias
            periodo_label = f"Ano Atual ({ano_atual})"
    else:
        # Padrão: ano atual
        data_inicio_dias = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
        data_inicio_ano = data_inicio_dias
        periodo_label = f"Ano Atual ({ano_atual})"
    
    data_fim = hoje
    ano_referencia_mensal = data_fim.year if periodo_selecionado == 'personalizado' else ano_atual
    data_inicio_grafico_mensal = data_inicio_dias
    if periodo_selecionado == 'personalizado':
        data_inicio_grafico_mensal = timezone.datetime(
            ano_referencia_mensal, 1, 1, 0, 0, 0, tzinfo=data_fim.tzinfo
        )

    dados_graficos = {
        'consumo_mes': [],
        'consumo_total_ano': 0.0,
        'lotes_acima_limite_mensal': [],
        'limite_mensal_litros': LIMITE_MENSAL_LITROS,
        'consumo_por_hidrometro': [],
        'periodo_label': periodo_label,
        'periodo_selecionado': periodo_selecionado,
        'ano_atual': ano_referencia_mensal,
    }

    hidrometros_qs = Hidrometro.objects.filter(
        ativo=True,
        lote__tipo='residencial'
    ).select_related('lote')

    consumo_mensal = {mes: 0.0 for mes in range(1, 13)}
    consumo_total_ano = 0.0
    consumo_por_lote_mes = {}
    consumo_por_hidrometro = []

    leituras_stream = (
        Leitura.objects.filter(
            hidrometro__ativo=True,
            hidrometro__lote__tipo='residencial',
            data_leitura__lte=data_fim,
        )
        .order_by('hidrometro_id', 'data_leitura')
        .values('hidrometro_id', 'data_leitura', 'leitura', 'hidrometro__numero', 'hidrometro__lote__numero')
        .iterator(chunk_size=2000)
    )

    hidrometro_atual_id = None
    hidrometro_atual_numero = None
    lote_atual_numero = None
    leitura_anterior_valor = None
    consumo_hidrometro_litros = 0.0

    for leitura in leituras_stream:
        leitura_hidrometro_id = leitura['hidrometro_id']
        leitura_data = leitura['data_leitura']
        leitura_valor = leitura['leitura']

        if leitura_hidrometro_id != hidrometro_atual_id:
            if hidrometro_atual_id is not None and consumo_hidrometro_litros > 0:
                consumo_por_hidrometro.append({
                    'hidrometro': hidrometro_atual_numero,
                    'lote': lote_atual_numero,
                    'consumo_litros': round(consumo_hidrometro_litros, 2),
                })

            hidrometro_atual_id = leitura_hidrometro_id
            hidrometro_atual_numero = leitura['hidrometro__numero']
            lote_atual_numero = leitura['hidrometro__lote__numero']
            leitura_anterior_valor = leitura_valor
            consumo_hidrometro_litros = 0.0
            continue

        if leitura_anterior_valor is None:
            leitura_anterior_valor = leitura_valor
            continue

        consumo_m3 = float(leitura_valor - leitura_anterior_valor)
        leitura_anterior_valor = leitura_valor

        if consumo_m3 <= 0:
            continue

        consumo_litros = consumo_m3 * 1000
        if leitura_data >= data_inicio_dias:
            consumo_total_ano += consumo_litros
            consumo_hidrometro_litros += consumo_litros

            chave_lote_mes = (lote_atual_numero, leitura_data.year, leitura_data.month)
            consumo_por_lote_mes.setdefault(chave_lote_mes, 0.0)
            consumo_por_lote_mes[chave_lote_mes] += consumo_litros

        if leitura_data >= data_inicio_grafico_mensal and leitura_data.year == ano_referencia_mensal:
            consumo_mensal[leitura_data.month] += consumo_litros

    if hidrometro_atual_id is not None and consumo_hidrometro_litros > 0:
        consumo_por_hidrometro.append({
            'hidrometro': hidrometro_atual_numero,
            'lote': lote_atual_numero,
            'consumo_litros': round(consumo_hidrometro_litros, 2),
        })

    nomes_meses = [
        'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
        'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'
    ]

    for mes in range(1, 13):
        dados_graficos['consumo_mes'].append({
            'mes': mes,
            'mes_nome': f"{nomes_meses[mes - 1]}/{str(ano_referencia_mensal)[-2:]}",
            'consumo_litros': round(consumo_mensal[mes], 2)
        })

    dados_graficos['consumo_total_ano'] = round(consumo_total_ano, 2)

    excedentes_por_lote = {}
    for (lote, ano, mes), consumo_litros in consumo_por_lote_mes.items():
        if consumo_litros <= LIMITE_MENSAL_LITROS:
            continue

        excedente_atual = excedentes_por_lote.get(lote)
        if (not excedente_atual) or (consumo_litros > excedente_atual['consumo_litros']):
            excedentes_por_lote[lote] = {
                'lote': lote,
                'ano': ano,
                'mes': mes,
                'mes_nome': f"{nomes_meses[mes - 1]}/{str(ano)[-2:]}",
                'consumo_litros': round(consumo_litros, 2),
            }

    dados_graficos['lotes_acima_limite_mensal'] = sorted(
        excedentes_por_lote.values(),
        key=lambda item: item['consumo_litros'],
        reverse=True,
    )

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


@admin_required
def graficos_lote(request, lote_id):
    """Página com gráficos de consumo específicos de um lote com filtros de período"""
    from collections import defaultdict
    import calendar
    
    lote = get_object_or_404(Lote, id=lote_id)
    
    # Obter filtros de período
    periodo = request.GET.get('periodo', 'ano_atual')
    data_inicio_str = request.GET.get('data_inicio', '')
    data_fim_str = request.GET.get('data_fim', '')
    
    hoje = timezone.localdate()
    data_inicio = None
    data_fim = hoje
    periodo_label = ''
    
    # Definir período baseado no filtro
    if periodo == 'ano_atual':
        data_inicio = hoje.replace(month=1, day=1)
        periodo_label = f'Ano de {hoje.year}'
    elif periodo == 'personalizado' and data_inicio_str and data_fim_str:
        try:
            from datetime import datetime
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            periodo_label = f'{data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}'
        except:
            data_inicio = hoje.replace(month=1, day=1)
            data_fim = hoje
            periodo_label = f'Ano de {hoje.year}'
            periodo = 'ano_atual'
    else:
        data_inicio = hoje.replace(month=1, day=1)
        periodo_label = f'Ano de {hoje.year}'

    # No período personalizado, o gráfico mensal deve exibir comparativo
    # desde o início do ano até a data final selecionada.
    data_inicio_grafico_mensal = data_inicio
    if periodo == 'personalizado':
        data_inicio_grafico_mensal = data_fim.replace(month=1, day=1)
    
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
    
    # Calcula uma única vez para reduzir carga de banco e evitar timeout.
    consumo_total_periodo = 0.0
    consumo_por_dia = defaultdict(float)
    consumo_por_mes = {mes: 0.0 for mes in range(1, 13)}

    leituras_lote = (
        Leitura.objects.filter(
            hidrometro__lote=lote,
            hidrometro__ativo=True,
            data_leitura__date__lte=data_fim,
        )
        .order_by('hidrometro_id', 'data_leitura')
        .values('hidrometro_id', 'data_leitura', 'leitura')
        .iterator(chunk_size=1000)
    )

    hidrometro_atual_id = None
    leitura_anterior = None

    for leitura in leituras_lote:
        if leitura['hidrometro_id'] != hidrometro_atual_id:
            hidrometro_atual_id = leitura['hidrometro_id']
            leitura_anterior = leitura
            continue

        if leitura_anterior is None:
            leitura_anterior = leitura
            continue

        diferenca = float(leitura['leitura']) - float(leitura_anterior['leitura'])
        leitura_anterior = leitura

        if diferenca <= 0:
            continue

        data_leitura_atual = leitura['data_leitura'].date()
        consumo_litros = diferenca * 1000

        if data_leitura_atual >= data_inicio:
            consumo_total_periodo += consumo_litros
            consumo_por_dia[leitura['data_leitura'].strftime('%d/%m')] += consumo_litros

        if data_leitura_atual >= data_inicio_grafico_mensal:
            consumo_por_mes[leitura['data_leitura'].month] += consumo_litros

    consumo_dia_lista = [
        {'dia': dia, 'consumo_litros': consumo}
        for dia, consumo in sorted(consumo_por_dia.items())
    ]
    
    # Sempre exibir todos os 12 meses em português
    consumo_mes_lista = []
    for mes in range(1, 13):
        mes_nome = MESES_PT_BR[mes]
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


@admin_required
def exportar_graficos_consumo_pdf(request):
    """Exporta os gráficos de consumo do condomínio em PDF"""
    LIMITE_MENSAL_LITROS = 15000

    import os
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    from django.template.loader import render_to_string
    
    # Obter dados dos gráficos (mesma lógica da view graficos_consumo)
    agora = timezone.localtime(timezone.now())
    ultima_coleta = Leitura.objects.filter(
        hidrometro__ativo=True,
        hidrometro__lote__tipo='residencial'
    ).aggregate(ultima=Max('data_leitura'))['ultima']

    if ultima_coleta:
        hoje = timezone.localtime(ultima_coleta) if timezone.is_aware(ultima_coleta) else timezone.make_aware(ultima_coleta)
    else:
        hoje = agora

    ano_atual = hoje.year

    # Obter o período selecionado (padrão: ano atual)
    periodo_selecionado = request.GET.get('periodo', 'ano_atual')

    # Definir data de início baseada no período selecionado
    if periodo_selecionado == 'ano_atual':
        # Ano atual (de 1º de janeiro até hoje)
        data_inicio_ano = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
        data_inicio_dias = data_inicio_ano
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
                periodo_label = f"{data_inicio_dias.strftime('%d/%m/%Y')} até {data_fim_personalizada.strftime('%d/%m/%Y')}"
                hoje = data_fim_personalizada  # Usar data_fim personalizada
            except (ValueError, TypeError):
                # Se houver erro, usar padrão (ano atual)
                data_inicio_dias = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
                data_inicio_ano = data_inicio_dias
                periodo_label = f"Ano Atual ({ano_atual})"
        else:
            # Sem datas fornecidas, usar padrão
            data_inicio_dias = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
            data_inicio_ano = data_inicio_dias
            periodo_label = f"Ano Atual ({ano_atual})"
    else:
        # Padrão: ano atual
        data_inicio_dias = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
        data_inicio_ano = data_inicio_dias
        periodo_label = f"Ano Atual ({ano_atual})"
    
    data_fim = hoje
    
    # Buscar todos os hidrômetros ativos
    hidrometros = Hidrometro.objects.filter(
        ativo=True,
        lote__tipo='residencial'
    ).select_related('lote')
    
    # Consumo por hidrômetro (individual) no período
    consumo_por_hidrometro = []
    consumo_total_periodo = 0.0
    consumo_por_lote_mes = {}
    
    for hidrometro in hidrometros:
        # Buscar última leitura ANTES do período (para ter base de comparação)
        leitura_anterior_periodo = hidrometro.leituras.filter(
            data_leitura__lt=data_inicio_dias
        ).order_by('-data_leitura').first()

        # Preparar leituras do período
        leituras_periodo = list(hidrometro.leituras.filter(
            data_leitura__gte=data_inicio_dias,
            data_leitura__lte=data_fim
        ).order_by('data_leitura'))

        # Combinar (anterior + período)
        if leitura_anterior_periodo:
            leituras_para_calculo = [leitura_anterior_periodo] + leituras_periodo
        else:
            leituras_para_calculo = leituras_periodo
        
        consumo_hidrometro_litros = 0.0
        for i in range(1, len(leituras_para_calculo)):
            leitura_atual = leituras_para_calculo[i]
            leitura_anterior = leituras_para_calculo[i - 1]

            # Só contabilizar se a leitura ATUAL estiver dentro do período filtrado
            if leitura_atual.data_leitura < data_inicio_dias:
                continue
            
            consumo_m3 = float(leitura_atual.leitura - leitura_anterior.leitura)
            if consumo_m3 < 0:
                continue
                
            consumo_litros = consumo_m3 * 1000
            consumo_hidrometro_litros += consumo_litros
            consumo_total_periodo += consumo_litros

            chave_lote_mes = (hidrometro.lote.numero, leitura_atual.data_leitura.year, leitura_atual.data_leitura.month)
            consumo_por_lote_mes.setdefault(chave_lote_mes, 0.0)
            consumo_por_lote_mes[chave_lote_mes] += consumo_litros
                
        if consumo_hidrometro_litros > 0:
            consumo_por_hidrometro.append({
                'hidrometro': hidrometro.numero,
                'lote': hidrometro.lote.numero,
                'consumo_litros': round(consumo_hidrometro_litros, 2),
            })

    nomes_meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    lotes_acima_limite = {}
    for (lote_numero, ano, mes), consumo_litros in consumo_por_lote_mes.items():
        if consumo_litros <= LIMITE_MENSAL_LITROS:
            continue

        atual = lotes_acima_limite.get(lote_numero)
        if (not atual) or (consumo_litros > atual['consumo_litros']):
            lotes_acima_limite[lote_numero] = {
                'lote': lote_numero,
                'mes_nome': f"{nomes_meses[mes - 1]}/{str(ano)[-2:]}",
                'consumo_litros': round(consumo_litros, 2),
            }

    lotes_acima_limite_lista = sorted(
        lotes_acima_limite.values(),
        key=lambda item: item['consumo_litros'],
        reverse=True,
    )

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
    img_buffer = None
    img_buffer_top = None
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
    
    # Lotes com excedente mensal
    elements.append(Paragraph(f"⚠️ Lotes com consumo mensal acima de {LIMITE_MENSAL_LITROS:,.0f} L", heading_style))

    top_data = [['Posição', 'Lote', 'Mês de Referência', 'Maior Consumo Mensal (L)']]
    if lotes_acima_limite_lista:
        for idx, item in enumerate(lotes_acima_limite_lista, 1):
            top_data.append([
                str(idx),
                item['lote'],
                item['mes_nome'],
                f"{item['consumo_litros']:,.0f}",
            ])
    else:
        top_data.append(['-', '-', '-', 'Nenhum lote excedeu o limite no período'])

    top_table = Table(top_data, colWidths=[1*inch, 1.5*inch, 2*inch, 2.5*inch])
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
    
    # Gráfico de excedentes mensais por lote
    if lotes_acima_limite_lista:
        plt.figure(figsize=(10, 5))
        lotes_labels = [f"Lote {item['lote']} ({item['mes_nome']})" for item in lotes_acima_limite_lista]
        lotes_valores = [item['consumo_litros'] for item in lotes_acima_limite_lista]
        plt.barh(lotes_labels[::-1], lotes_valores[::-1], color='#e74c3c', alpha=0.7)
        plt.title(f'Lotes acima de {LIMITE_MENSAL_LITROS:,.0f} L/mês ({periodo_label})', fontsize=14, fontweight='bold')
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
    doc.build(
        elements,
        onFirstPage=_desenhar_marca_dagua_logo,
        onLaterPages=_desenhar_marca_dagua_logo
    )
    
    # Preparar resposta
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_consumo_condominio_{agora.strftime("%Y%m%d")}.pdf"'
    buffer.close()
    if img_buffer is not None:
        img_buffer.close()
    if img_buffer_top is not None:
        img_buffer_top.close()
    
    return response


@admin_required
def baixar_relatorios_lotes_periodo_zip(request):
    """Gera e baixa relatórios individuais de lotes em um único ZIP.
    
    Suporta paginação por faixa de lotes (ex: lote_inicio=1, lote_fim=50)
    para evitar timeout do servidor ao processar todos os 310 lotes.
    """
    from django.test import RequestFactory
    
    agora = timezone.localtime(timezone.now())
    ultima_coleta = Leitura.objects.filter(
        hidrometro__ativo=True,
        hidrometro__lote__tipo='residencial'
    ).aggregate(ultima=Max('data_leitura'))['ultima']

    if ultima_coleta:
        hoje_ref = timezone.localtime(ultima_coleta) if timezone.is_aware(ultima_coleta) else timezone.make_aware(ultima_coleta)
    else:
        hoje_ref = agora

    periodo_selecionado = request.GET.get('periodo', 'mes_atual')

    def _inicio_mes_menos(data_referencia, meses_anteriores):
        total_meses = data_referencia.year * 12 + (data_referencia.month - 1) - meses_anteriores
        ano = total_meses // 12
        mes = (total_meses % 12) + 1
        return data_referencia.replace(year=ano, month=mes, day=1, hour=0, minute=0, second=0, microsecond=0)

    if periodo_selecionado == 'mes_atual':
        data_inicio_dt = hoje_ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        data_fim_dt = hoje_ref
    elif periodo_selecionado == '2meses':
        data_inicio_dt = _inicio_mes_menos(hoje_ref, 1)
        data_fim_dt = hoje_ref
    elif periodo_selecionado == '3meses':
        data_inicio_dt = _inicio_mes_menos(hoje_ref, 2)
        data_fim_dt = hoje_ref
    elif periodo_selecionado == 'ano_atual':
        data_inicio_dt = timezone.datetime(hoje_ref.year, 1, 1, 0, 0, 0, tzinfo=hoje_ref.tzinfo)
        data_fim_dt = hoje_ref
    elif periodo_selecionado == 'personalizado':
        data_inicio_str = request.GET.get('data_inicio')
        data_fim_str = request.GET.get('data_fim')
        if data_inicio_str and data_fim_str:
            try:
                data_inicio_dt = timezone.make_aware(
                    timezone.datetime.strptime(data_inicio_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)
                )
                data_fim_dt = timezone.make_aware(
                    timezone.datetime.strptime(data_fim_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59, microsecond=999999)
                )
                if data_fim_dt > hoje_ref:
                    data_fim_dt = hoje_ref
            except (ValueError, TypeError):
                data_inicio_dt = hoje_ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                data_fim_dt = hoje_ref
        else:
            data_inicio_dt = hoje_ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            data_fim_dt = hoje_ref
    else:
        data_inicio_dt = hoje_ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        data_fim_dt = hoje_ref

    data_inicio = data_inicio_dt.date()
    data_fim = data_fim_dt.date()
    intervalo_token = f"{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}"

    # Paginação por faixa de lotes (para evitar timeout)
    lote_inicio = request.GET.get('lote_inicio')
    lote_fim = request.GET.get('lote_fim')
    
    # Buscar apenas lotes que têm leituras no período (otimização crítica)
    query = Lote.objects.filter(
        tipo='residencial',
        hidrometros__ativo=True,
        hidrometros__leituras__data_leitura__date__gte=data_inicio,
        hidrometros__leituras__data_leitura__date__lte=data_fim
    ).distinct()
    
    # Aplicar filtro de faixa se fornecido
    if lote_inicio and lote_fim:
        try:
            # Converter números dos lotes para inteiros e filtrar
            inicio_num = int(lote_inicio)
            fim_num = int(lote_fim)
            # Filtrar lotes cujo número está na faixa (especificando o nome completo da tabela)
            # Usa '"consumo_lote"."numero"' para evitar ambiguidade com hidrometro.numero
            query = query.extra(
                where=['CAST("consumo_lote"."numero" AS INTEGER) >= %s AND CAST("consumo_lote"."numero" AS INTEGER) <= %s'],
                params=[inicio_num, fim_num]
            )
            faixa_label = f"_lotes_{inicio_num}_a_{fim_num}"
        except (ValueError, TypeError):
            faixa_label = ""
    else:
        faixa_label = "_todos"
    
    # Executar query e ordenar
    lotes_com_leituras = list(query)
    lotes_com_leituras.sort(key=lambda lote: int(lote.numero) if lote.numero.isdigit() else 0)

    if not lotes_com_leituras:
        return HttpResponse(
            f'Nenhum lote residencial com leituras encontrado para o período de '
            f'{data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}.',
            status=404
        )

    data_coleta_ref = calcular_data_coleta(hoje_ref.date())
    pasta_cache_ref = pasta_relatorios_coleta(data_coleta_ref)

    def _buscar_pdf_pregerado(lote_numero):
        nome_arquivo = f'relatorio_lote_{lote_numero}_{intervalo_token}.pdf'

        caminho_preferencial = os.path.join(str(pasta_cache_ref), nome_arquivo)
        if os.path.exists(caminho_preferencial):
            return caminho_preferencial

        padrao = os.path.join(str(settings.MEDIA_ROOT), 'relatorios_mensais', '*', nome_arquivo)
        candidatos = glob.glob(padrao)
        if candidatos:
            candidatos.sort(reverse=True)
            return candidatos[0]

        return None

    # Criar ZIP em memória
    buffer = io.BytesIO()
    factory = RequestFactory()
    total_pdfs_gerados = 0
    total_pdfs_cache = 0
    total_pdfs_dinamicos = 0

    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as arquivo_zip:
        for lote in lotes_com_leituras:
            # 1) Tenta usar PDF pregerado em disco
            try:
                caminho_pdf_cache = _buscar_pdf_pregerado(lote.numero)
                nome_arquivo = f'relatorio_lote_{lote.numero}_{intervalo_token}.pdf'
                caminho_no_zip = f'relatorios_lotes_{intervalo_token}/{nome_arquivo}'

                if caminho_pdf_cache and os.path.exists(caminho_pdf_cache):
                    with open(caminho_pdf_cache, 'rb') as arquivo_pdf:
                        arquivo_zip.writestr(caminho_no_zip, arquivo_pdf.read())
                    total_pdfs_gerados += 1
                    total_pdfs_cache += 1
                    continue
            except Exception:
                pass

            # 2) Fallback: gera dinamicamente apenas se nao existir cache
            fake_request = factory.get(
                f'/consumo/graficos/lote/{lote.id}/exportar/pdf/',
                {
                    'periodo': 'personalizado',
                    'data_inicio': data_inicio.strftime('%Y-%m-%d'),
                    'data_fim': data_fim.strftime('%Y-%m-%d')
                }
            )
            fake_request.user = request.user
            fake_request.META = request.META.copy()
            fake_request.session = request.session

            try:
                response_pdf = exportar_graficos_lote_pdf(fake_request, lote.id)

                if response_pdf.status_code == 200:
                    nome_arquivo = f'relatorio_lote_{lote.numero}_{intervalo_token}.pdf'
                    caminho_no_zip = f'relatorios_lotes_{intervalo_token}/{nome_arquivo}'
                    arquivo_zip.writestr(caminho_no_zip, response_pdf.content)
                    total_pdfs_gerados += 1
                    total_pdfs_dinamicos += 1
            except Exception:
                continue

    if total_pdfs_gerados == 0:
        return HttpResponse(
            f'Não foi possível gerar nenhum relatório para o período de '
            f'{data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}.',
            status=500
        )

    # Retornar ZIP
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = (
        f'attachment; filename="relatorios_{intervalo_token}{faixa_label}_{total_pdfs_gerados}_pdfs.zip"'
    )
    response['X-Relatorios-Cache'] = str(total_pdfs_cache)
    response['X-Relatorios-Dinamicos'] = str(total_pdfs_dinamicos)
    return response


@admin_required
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
    periodo = request.GET.get('periodo', 'ano_atual')
    data_inicio_str = request.GET.get('data_inicio', '')
    data_fim_str = request.GET.get('data_fim', '')
    data_fim = hoje
    periodo_label = ''

    if periodo == 'ano_atual':
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
            data_inicio = hoje.replace(month=1, day=1)
            data_fim = hoje
            periodo_label = f'Ano de {hoje.year}'
            periodo = 'ano_atual'
    else:
        data_inicio = hoje.replace(month=1, day=1)
        periodo_label = f'Ano de {hoje.year}'

    # No período personalizado, incluir meses anteriores do ano para comparação no gráfico mensal.
    data_inicio_grafico_mensal = data_inicio
    if periodo == 'personalizado':
        data_inicio_grafico_mensal = data_fim.replace(month=1, day=1)
    
    hidrometros = list(lote.hidrometros.filter(ativo=True).only('id', 'numero'))
    
    if not hidrometros:
        return HttpResponse("Nenhum hidrômetro ativo encontrado para este lote.", status=404)
    
    # Calcular consumo no periodo
    nomes_meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    consumo_total_periodo = 0.0
    consumo_por_dia = {}
    consumo_por_mes = {}

    tz_atual = timezone.get_current_timezone()
    inicio_periodo_dt = timezone.make_aware(
        datetime.combine(data_inicio, datetime.min.time()),
        tz_atual
    )
    inicio_grafico_mensal_dt = timezone.make_aware(
        datetime.combine(data_inicio_grafico_mensal, datetime.min.time()),
        tz_atual
    )
    fim_periodo_dt = timezone.make_aware(
        datetime.combine(data_fim, datetime.max.time()),
        tz_atual
    )

    leituras_periodo_lista = list(
        Leitura.objects.filter(
            hidrometro__lote=lote,
            hidrometro__ativo=True,
            data_leitura__gte=inicio_grafico_mensal_dt,
            data_leitura__lte=fim_periodo_dt
        )
        .select_related('hidrometro')
        .order_by('data_leitura')
    )

    leituras_por_hidrometro = {}
    for leitura in leituras_periodo_lista:
        leituras_por_hidrometro.setdefault(leitura.hidrometro_id, []).append(leitura)

    ultima_leitura_antes_periodo = {}
    for hidrometro in hidrometros:
        leitura_anterior = (
            Leitura.objects.filter(
                hidrometro=hidrometro,
                data_leitura__lt=inicio_grafico_mensal_dt
            )
            .only('leitura', 'data_leitura', 'hidrometro_id')
            .order_by('-data_leitura')
            .first()
        )
        if leitura_anterior:
            ultima_leitura_antes_periodo[hidrometro.id] = leitura_anterior

    for hidrometro in hidrometros:
        leituras_hidrometro = leituras_por_hidrometro.get(hidrometro.id, [])
        if not leituras_hidrometro:
            continue

        leitura_referencia = ultima_leitura_antes_periodo.get(hidrometro.id)
        for leitura_atual in leituras_hidrometro:
            if leitura_referencia is None:
                leitura_referencia = leitura_atual
                continue

            diferenca = float(leitura_atual.leitura - leitura_referencia.leitura)
            leitura_referencia = leitura_atual
            if diferenca <= 0:
                continue

            consumo_litros = diferenca * 1000
            data_leitura_atual = leitura_atual.data_leitura.date()

            if data_leitura_atual >= data_inicio:
                consumo_total_periodo += consumo_litros

                dia = data_leitura_atual
                consumo_por_dia[dia] = consumo_por_dia.get(dia, 0.0) + consumo_litros

            if data_leitura_atual >= data_inicio_grafico_mensal:
                mes_key = (leitura_atual.data_leitura.year, leitura_atual.data_leitura.month)
                consumo_por_mes[mes_key] = consumo_por_mes.get(mes_key, 0.0) + consumo_litros

    datas_periodo = []
    dia_cursor = data_inicio
    while dia_cursor <= data_fim:
        datas_periodo.append(dia_cursor)
        consumo_por_dia.setdefault(dia_cursor, 0.0)
        dia_cursor += timedelta(days=1)

    # Sempre exibir todos os 12 meses do ano de referência do filtro.
    ano_referencia = data_fim.year if periodo == 'personalizado' else hoje.year
    meses_periodo = [(ano_referencia, mes) for mes in range(1, 13)]
    # Garantir que todos os meses tenham valor 0 se não houver consumo
    for mes in range(1, 13):
        consumo_por_mes.setdefault((ano_referencia, mes), 0.0)
    
    
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
        ['Hidrometros Ativos', str(len(hidrometros))],
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
        mensal_data.append([mes_nome, f'{consumo_por_mes.get((ano, mes), 0.0):,.0f}'])
    
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
    
    # Gráfico de Consumo Mensal (otimizado para performance)
    fig = plt.figure(figsize=(10, 5))
    meses_labels = [f'{nomes_meses[mes - 1]}/{str(ano)[-2:]}' for (ano, mes) in meses_periodo]
    valores_mensais = [consumo_por_mes.get((ano, mes), 0.0) for (ano, mes) in meses_periodo]
    plt.bar(meses_labels, valores_mensais, color='#27ae60', alpha=0.7)
    plt.title(f'Consumo Mensal - Lote {lote.numero} (Litros)', fontsize=14, fontweight='bold')
    plt.xlabel('Mês', fontsize=11)
    plt.ylabel('Consumo (L)', fontsize=11)
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    # Salvar gráfico em buffer (DPI reduzido para performance em batch)
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=100, bbox_inches='tight',
                pil_kwargs={'compress_level': 1})  # Compressão rápida
    img_buffer.seek(0)
    plt.close(fig)  # Fechar figura explicitamente
    
    # Adicionar imagem ao PDF
    img = Image(img_buffer, width=7*inch, height=3.5*inch)
    elements.append(img)
    elements.append(Spacer(1, 0.3*inch))

    leituras_periodo = leituras_periodo_lista

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

    # Limita o detalhe em períodos grandes para evitar timeout/memória excessiva no servidor.
    max_linhas_detalhe = 1200
    leituras_exibidas = leituras_periodo[:max_linhas_detalhe]

    ultima_por_hidrometro = {
        hid_id: leitura for hid_id, leitura in ultima_leitura_antes_periodo.items()
    }

    for leitura in leituras_exibidas:
        leitura_anterior = ultima_por_hidrometro.get(leitura.hidrometro_id)
        if leitura_anterior is None:
            consumo_litros = 0.0
        else:
            diferenca = float(leitura.leitura - leitura_anterior.leitura)
            consumo_litros = diferenca * 1000 if diferenca > 0 else 0.0
        ultima_por_hidrometro[leitura.hidrometro_id] = leitura

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

    if len(leituras_periodo) > max_linhas_detalhe:
        elements.append(Paragraph(
            f"Observação: exibindo {max_linhas_detalhe} de {len(leituras_periodo)} leituras do período para manter performance.",
            styles['Italic']
        ))
        elements.append(Spacer(1, 0.12*inch))

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

    buffers_fotos_pdf = []
    # Para lotes administrativos, removemos completamente o processamento de fotos
    # para reduzir uso de CPU/memória na geração do PDF.
    if lote.tipo != 'administracao':
        incluir_fotos_param = request.GET.get('incluir_fotos')
        if incluir_fotos_param is None:
            incluir_fotos = (data_fim - data_inicio).days <= 62
        else:
            incluir_fotos = incluir_fotos_param.lower() in ('1', 'true', 'sim', 'yes')

        max_fotos = 40
        leituras_com_foto = [leitura for leitura in leituras_periodo if leitura.foto][:max_fotos] if incluir_fotos else []

        if leituras_com_foto:
            elements.append(PageBreak())
            elements.append(Paragraph("📷 Fotos das Leituras", heading_style))
            for leitura in leituras_com_foto:
                try:
                    if not leitura.foto:
                        continue

                    foto_source = None

                    # Prioriza stream do storage (funciona com storage remoto e local).
                    try:
                        leitura.foto.open('rb')
                        conteudo = leitura.foto.read()
                        if conteudo:
                            foto_buffer = io.BytesIO(conteudo)
                            buffers_fotos_pdf.append(foto_buffer)
                            foto_source = foto_buffer
                    except Exception:
                        foto_source = None
                    finally:
                        try:
                            leitura.foto.close()
                        except Exception:
                            pass

                    # Fallback para caminho de arquivo local quando disponível.
                    if foto_source is None:
                        foto_path = None
                        if hasattr(leitura.foto, 'path'):
                            foto_path = leitura.foto.path
                            if not os.path.isabs(foto_path):
                                foto_path = os.path.join(settings.MEDIA_ROOT, foto_path)
                        elif hasattr(leitura.foto, 'file'):
                            foto_file = leitura.foto.file.name
                            if not os.path.isabs(foto_file):
                                foto_path = os.path.join(settings.MEDIA_ROOT, foto_file)
                            else:
                                foto_path = foto_file

                        if foto_path and os.path.exists(foto_path):
                            foto_source = foto_path
                        else:
                            alt_path = os.path.join(settings.MEDIA_ROOT, str(leitura.foto))
                            if os.path.exists(alt_path):
                                foto_source = alt_path

                    if foto_source is None:
                        continue

                    legenda = (
                        f"Hidrômetro {leitura.hidrometro.numero} - "
                        f"{leitura.data_leitura.strftime('%d/%m/%Y %H:%M')}"
                    )
                    elements.append(Paragraph(legenda, styles['Normal']))
                    elements.append(Spacer(1, 0.1*inch))

                    # Adicionar foto com tratamento de erro
                    try:
                        img_foto = Image(foto_source, width=6.5*inch, height=3.8*inch)
                        elements.append(img_foto)
                    except Exception as img_error:
                        # Se falhar ao carregar imagem, adicionar nota
                        elements.append(Paragraph(
                            f"[Foto não disponível: {str(img_error)[:50]}]",
                            styles['Normal']
                        ))

                    elements.append(Spacer(1, 0.2*inch))
                except Exception:
                    # Continuar com próxima foto se houver erro
                    continue

            if incluir_fotos and len([leitura for leitura in leituras_periodo if leitura.foto]) > max_fotos:
                elements.append(Paragraph(
                    f"Observação: exibindo {max_fotos} fotos para manter a performance do relatório.",
                    styles['Italic']
                ))
        elif not incluir_fotos:
            elements.append(Paragraph(
                "Fotos não incluídas automaticamente em períodos longos para evitar timeout. Use incluir_fotos=1 para forçar inclusão.",
                styles['Italic']
            ))
    
    
    # Construir PDF
    doc.build(
        elements,
        onFirstPage=_desenhar_marca_dagua_logo,
        onLaterPages=_desenhar_marca_dagua_logo
    )
    
    # Preparar resposta
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="relatorio_lote_{lote.numero}_{data_inicio.strftime("%Y%m%d")}_'
        f'{data_fim.strftime("%Y%m%d")}.pdf"'
    )
    
    for foto_buffer in buffers_fotos_pdf:
        try:
            foto_buffer.close()
        except Exception:
            pass

    return response


@csrf_exempt
def exportar_graficos_lote_pdf_job(request, lote_id):
    """
    Endpoint interno para gerar PDF por lote sem sessao web.
    Autenticado por X-Job-Token (mesmo padrao dos jobs internos).
    """
    if request.method != 'GET':
        return JsonResponse({'erro': 'Metodo nao permitido'}, status=405)

    token_configurado = os.getenv('JOB_SECRET_TOKEN', '').strip()
    token_recebido = (request.headers.get('X-Job-Token') or '').strip()

    if not token_configurado:
        return JsonResponse({'erro': 'Servico indisponivel: JOB_SECRET_TOKEN nao configurado'}, status=503)

    if not token_recebido or not hmac.compare_digest(token_recebido, token_configurado):
        return JsonResponse({'erro': 'Nao autorizado'}, status=401)

    return exportar_graficos_lote_pdf.__wrapped__(request, lote_id)



