import re

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import UsuarioPerfil


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='E-mail ou telefone',
        widget=forms.TextInput(attrs={'autofocus': True, 'placeholder': 'seuemail@dominio.com ou 81999998888', 'class': 'form-control'})
    )

    password = forms.CharField(
        label='Senha',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def confirm_login_allowed(self, user):
        if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
            return

        perfil = getattr(user, 'perfil', None)
        if not perfil:
            return

        if perfil.situacao_acesso == 'pendente':
            raise ValidationError('Seu cadastro esta pendente de aprovacao do administrador.', code='acesso_pendente')
        if perfil.situacao_acesso == 'recusado':
            raise ValidationError('Seu acesso foi recusado. Entre em contato com a administracao.', code='acesso_recusado')

    def _resolver_username(self, identificador):
        identificador = (identificador or '').strip()
        if not identificador:
            return identificador

        if '@' in identificador:
            user = User.objects.filter(email__iexact=identificador).only('username').first()
            if user:
                return user.username
            return identificador

        digitos = re.sub(r'\D', '', identificador)
        if not digitos:
            return identificador

        candidatos = {digitos, f'+{digitos}'}
        perfis = UsuarioPerfil.objects.filter(telefone_contato__in=candidatos).select_related('user')
        total = perfis.count()
        if total > 1:
            raise ValidationError('Nao foi possivel autenticar por telefone. Entre com e-mail ou contate o administrador.')
        if total == 1:
            perfil = perfis.first()
            if perfil:
                return perfil.user.username

        return identificador

    def clean(self):
        identificador = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if identificador is not None and password:
            try:
                username_resolvido = self._resolver_username(identificador)
            except ValidationError as exc:
                self.add_error('username', exc)
                return self.cleaned_data

            self.user_cache = authenticate(self.request, username=username_resolvido, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class CadastroUsuarioForm(forms.ModelForm):
    email = forms.EmailField(label='E-mail')
    first_name = forms.CharField(label='Nome', max_length=150)
    last_name = forms.CharField(label='Sobrenome', max_length=150)
    telefone_contato = forms.CharField(label='Telefone para contato', max_length=20)
    password1 = forms.CharField(label='Senha', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmar senha', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            raise ValidationError('Informe um e-mail valido.')
        if User.objects.filter(username=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Ja existe um usuario com este e-mail.')
        return email

    def clean_telefone_contato(self):
        telefone = (self.cleaned_data.get('telefone_contato') or '').strip()
        if not telefone:
            raise ValidationError('Informe um telefone para contato.')

        # Aceita +, espaco, parenteses e hifen no input, mas salva apenas + e digitos.
        digits = re.sub(r'\D', '', telefone)
        if len(digits) < 10 or len(digits) > 15:
            raise ValidationError('Telefone invalido. Informe entre 10 e 15 digitos.')

        candidatos = {digits, f'+{digits}'}
        if UsuarioPerfil.objects.filter(telefone_contato__in=candidatos).exists():
            raise ValidationError('Ja existe um usuario cadastrado com este telefone.')

        return f'+{digits}'

    def clean_password1(self):
        password = self.cleaned_data.get('password1') or ''
        if len(password) < 4 or len(password) > 8:
            raise ValidationError('A senha deve ter entre 4 e 8 caracteres.')
        return password

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'As senhas nao coincidem.')

        return cleaned_data

    def save(self, commit=True):
        email = self.cleaned_data['email']
        user = User(
            username=email,
            email=email,
            first_name=self.cleaned_data['first_name'].strip(),
            last_name=self.cleaned_data['last_name'].strip(),
            is_active=True,
        )
        user.set_password(self.cleaned_data['password1'])

        if commit:
            user.save()
            perfil, _ = UsuarioPerfil.objects.get_or_create(user=user)
            perfil.telefone_contato = self.cleaned_data['telefone_contato']
            perfil.tipo_acesso = 'comum'
            perfil.situacao_acesso = 'pendente'
            perfil.save()

        return user
