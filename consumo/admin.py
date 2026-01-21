from django.contrib import admin
from .models import Lote, Hidrometro, Leitura


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ['numero', 'tipo', 'endereco', 'ativo', 'criado_em']
    list_filter = ['tipo', 'ativo']
    search_fields = ['numero', 'endereco']
    ordering = ['numero']


@admin.register(Hidrometro)
class HidrometroAdmin(admin.ModelAdmin):
    list_display = ['numero', 'lote', 'localizacao', 'data_instalacao', 'ativo']
    list_filter = ['ativo', 'data_instalacao', 'lote__tipo']
    search_fields = ['numero', 'lote__numero', 'localizacao']
    ordering = ['numero']
    date_hierarchy = 'data_instalacao'


@admin.register(Leitura)
class LeituraAdmin(admin.ModelAdmin):
    list_display = ['hidrometro', 'leitura', 'data_leitura', 'periodo', 'responsavel']
    list_filter = ['periodo', 'data_leitura', 'hidrometro__lote__tipo']
    search_fields = ['hidrometro__numero', 'hidrometro__lote__numero', 'responsavel']
    ordering = ['-data_leitura']
    date_hierarchy = 'data_leitura'
    readonly_fields = ['criado_em', 'atualizado_em']

