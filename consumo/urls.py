from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'lotes', views.LoteViewSet, basename='lote')
router.register(r'hidrometros', views.HidrometroViewSet, basename='hidrometro')
router.register(r'leituras', views.LeituraViewSet, basename='leitura')

app_name = 'consumo'

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    path('webhooks/zapi/disconnected/', views.webhook_zapi_desconectado, name='webhook_zapi_desconectado'),
    path('webhooks/zapi/connected/', views.webhook_zapi_conectado, name='webhook_zapi_conectado'),
    path('service-worker.js', views.service_worker, name='service_worker'),
    path('offline/', views.offline_page, name='offline_page'),

    # Autenticacao e usuarios
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('cadastro/', views.cadastro_usuario, name='cadastro_usuario'),
    path('acesso-negado/', views.acesso_negado, name='acesso_negado'),
    
    # Views HTML
    path('', views.inicio, name='inicio'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('hidrometros/', views.listar_hidrometros, name='listar_hidrometros'),
    path('lotes/<int:lote_id>/graficos/', views.graficos_lote, name='graficos_lote'),
    path('leituras/', views.listar_leituras, name='listar_leituras'),
    path('leituras/<int:leitura_id>/foto/', views.visualizar_foto_leitura, name='visualizar_foto_leitura'),
    path('jobs/leituras/<int:leitura_id>/foto/', views.baixar_foto_leitura_job, name='baixar_foto_leitura_job'),
    path('registrar-leitura/', views.registrar_leitura, name='registrar_leitura'),
    path('graficos/', views.graficos_consumo, name='graficos_consumo'),
    path('jobs/pregerar-relatorios/', views.pregerar_relatorios_job, name='pregerar_relatorios_job'),
    path('jobs/enviar-emails/', views.enviar_emails_job, name='enviar_emails_job'),
    path('jobs/lotes/<int:lote_id>/graficos/exportar/pdf/', views.exportar_graficos_lote_pdf_job, name='exportar_graficos_lote_pdf_job'),
    
    # Exportação de relatórios
    path('graficos/exportar/pdf/', views.exportar_graficos_consumo_pdf, name='exportar_graficos_consumo_pdf'),
    path('graficos/exportar/relatorios-lotes/', views.baixar_relatorios_lotes_periodo_zip, name='baixar_relatorios_lotes_periodo_zip'),
    path('lotes/<int:lote_id>/graficos/exportar/pdf/', views.exportar_graficos_lote_pdf, name='exportar_graficos_lote_pdf'),
]
