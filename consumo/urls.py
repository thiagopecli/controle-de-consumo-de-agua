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
    
    # Views HTML
    path('', views.dashboard, name='dashboard'),
    path('hidrometros/', views.listar_hidrometros, name='listar_hidrometros'),
    path('hidrometros/<int:hidrometro_id>/', views.detalhes_hidrometro, name='detalhes_hidrometro'),
    path('leituras/', views.listar_leituras, name='listar_leituras'),
    path('registrar-leitura/', views.registrar_leitura, name='registrar_leitura'),
    path('graficos/', views.graficos_consumo, name='graficos_consumo'),
]
