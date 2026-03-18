from django.conf import settings


def app_version_context(request):
    return {
        'app_version': getattr(settings, 'APP_VERSION', '1.0.0')
    }
