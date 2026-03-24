from django.conf import settings


def app_version_context(request):
    is_admin_user = False
    tipo_acesso = ''

    if getattr(request, 'user', None) and request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            is_admin_user = True
            tipo_acesso = 'administracao'
        else:
            perfil = getattr(request.user, 'perfil', None)
            if perfil:
                tipo_acesso = perfil.tipo_acesso
                is_admin_user = perfil.tipo_acesso == 'administracao'

    return {
        'app_version': getattr(settings, 'APP_VERSION', '1.0.0'),
        'is_admin_user': is_admin_user,
        'tipo_acesso_usuario': tipo_acesso,
    }
