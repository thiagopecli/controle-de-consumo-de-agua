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
    path('service-worker.js', views.service_worker, name='service_worker'),
    path('offline/', views.offline_page, name='offline_page'),
    
    # Views HTML
    path('', views.dashboard, name='dashboard'),
    path('hidrometros/', views.listar_hidrometros, name='listar_hidrometros'),
    path('hidrometros/<int:hidrometro_id>/', views.detalhes_hidrometro, name='detalhes_hidrometro'),
    path('lotes/<int:lote_id>/graficos/', views.graficos_lote, name='graficos_lote'),
    path('leituras/', views.listar_leituras, name='listar_leituras'),
    path('registrar-leitura/', views.registrar_leitura, name='registrar_leitura'),
    path('graficos/', views.graficos_consumo, name='graficos_consumo'),
    path('jobs/pregerar-relatorios/', views.pregerar_relatorios_job, name='pregerar_relatorios_job'),
    
    # Exportação de relatórios
    path('graficos/exportar/pdf/', views.exportar_graficos_consumo_pdf, name='exportar_graficos_consumo_pdf'),
    path('graficos/exportar/excel/', views.exportar_graficos_consumo_excel, name='exportar_graficos_consumo_excel'),
    path('graficos/exportar/relatorios-lotes/', views.baixar_relatorios_lotes_periodo_zip, name='baixar_relatorios_lotes_periodo_zip'),
    path('lotes/<int:lote_id>/graficos/exportar/pdf/', views.exportar_graficos_lote_pdf, name='exportar_graficos_lote_pdf'),
    path('lotes/<int:lote_id>/graficos/exportar/excel/', views.exportar_graficos_lote_excel, name='exportar_graficos_lote_excel'),
]
