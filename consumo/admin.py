from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
import re

from .models import Lote, Hidrometro, Leitura, UsuarioPerfil


class LoteForm(forms.ModelForm):
    """Formulário do admin para Lote que ajuda a preencher e normalizar
    os campos de WhatsApp usando o DDI do Brasil como padrão (+55).
    """
    telefone_whatsapp = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'Ex: 81991234567',
        }),
        initial='+55'
    )
    telefone_whatsapp_2 = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'Ex: 81999887766 (opcional)',
        }),
        initial='+55'
    )

    class Meta:
        model = Lote
        fields = '__all__'

    def _normalizar_telefone(self, val):
        # Remove tudo que não for dígito
        digits = re.sub(r'\D', '', val)

        # Se já veio com o código do país (55) no início, apenas prefixa +
        if digits.startswith('55') and len(digits) >= 11:
            normalized = '+' + digits
        # Se tem 10 ou 11 dígitos assumimos DDD + número e prefixamos +55
        elif len(digits) in (10, 11):
            normalized = '+55' + digits
        else:
            # Caso o usuário tenha digitado com + no início, tenta manter
            if val.startswith('+') and re.fullmatch(r"\+[0-9]{10,15}", val):
                normalized = val
            else:
                raise ValidationError('Formato de telefone inválido. Informe DDD + número (ex: 81991234567) ou um número internacional válido com +.')

        # Validação final: padrão + seguido de 10-15 dígitos
        if not re.fullmatch(r"\+[0-9]{10,15}", normalized):
            raise ValidationError('Telefone normalizado inválido: %s' % normalized)

        return normalized

    def clean_telefone_whatsapp(self):
        val = (self.cleaned_data.get('telefone_whatsapp') or '').strip()
        if not val:
            return ''
        return self._normalizar_telefone(val)

    def clean_telefone_whatsapp_2(self):
        val = (self.cleaned_data.get('telefone_whatsapp_2') or '').strip()
        if not val:
            return ''
        return self._normalizar_telefone(val)


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    form = LoteForm
    list_display = ['numero', 'tipo', 'proprietario_nome', 'telefone_whatsapp', 'telefone_whatsapp_2', 'endereco', 'ativo', 'criado_em']
    list_filter = ['tipo', 'ativo']
    search_fields = ['numero', 'proprietario_nome', 'telefone_whatsapp', 'telefone_whatsapp_2', 'endereco']
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

