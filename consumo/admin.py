from django.contrib import admin
from django import forms

from .models import Lote, Hidrometro, Leitura, UsuarioPerfil


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ['numero', 'tipo', 'proprietario_nome', 'email_responsavel', 'email_responsavel_2', 'endereco', 'ativo', 'criado_em']
    list_filter = ['tipo', 'ativo']
    search_fields = ['numero', 'proprietario_nome', 'email_responsavel', 'email_responsavel_2', 'endereco']
    ordering = ['numero']
    readonly_fields = ['criado_em', 'atualizado_em']
    
    fieldsets = (
        ('Identificação', {
            'fields': ('numero', 'tipo', 'ativo')
        }),
        ('Dados do Proprietário', {
            'fields': ('proprietario_nome', 'endereco')
        }),
        ('Contatos para Relatórios (EMAIL)', {
            'description': 'Adicione pelo menos um email para receber os relatórios mensais de consumo',
            'fields': ('email_responsavel', 'email_responsavel_2')
        }),
        ('Contatos Legados (não utilizados)', {
            'classes': ('collapse',),
            'description': 'Campos mantidos para referência histórica',
            'fields': ('telefone_whatsapp', 'telefone_whatsapp_2')
        }),
        ('Histórico', {
            'classes': ('collapse',),
            'fields': ('criado_em', 'atualizado_em')
        }),
    )


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


@admin.register(UsuarioPerfil)
class UsuarioPerfilAdmin(admin.ModelAdmin):
    list_display = ['user', 'situacao_acesso', 'tipo_acesso', 'telefone_contato', 'criado_em']
    list_filter = ['situacao_acesso', 'tipo_acesso']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'telefone_contato']
    actions = ['aprovar_usuarios', 'recusar_usuarios']

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.action(description='Aprovar usuarios selecionados')
    def aprovar_usuarios(self, request, queryset):
        queryset = queryset.exclude(user__is_superuser=True)
        atualizados = queryset.update(situacao_acesso='aprovado')
        self.message_user(request, f'{atualizados} usuario(s) aprovado(s) com sucesso.')

    @admin.action(description='Recusar usuarios selecionados')
    def recusar_usuarios(self, request, queryset):
        queryset = queryset.exclude(user__is_superuser=True)
        atualizados = queryset.update(situacao_acesso='recusado')
        self.message_user(request, f'{atualizados} usuario(s) recusado(s).')

