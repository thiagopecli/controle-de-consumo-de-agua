import os
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.utils import timezone
from django.test import RequestFactory
from consumo.views import exportar_graficos_consumo_pdf # Ajuste 'consumo' se o nome do seu app for diferente

class Command(BaseCommand):
    help = 'Gera o PDF geral do condomínio e envia para a administração.'

    def handle(self, *args, **options):
        # 1. Definir o período exato (16 do mês passado ao 15 do mês atual)
        # Como o cron roda dia 16, 'hoje' será dia 16.
        hoje = timezone.localdate()
        data_fim = hoje - timedelta(days=1) # Retorna para o dia 15
        
        # Volta 1 mês para achar o dia 16 anterior (tratando a virada de ano)
        if data_fim.month == 1:
            data_inicio = data_fim.replace(year=data_fim.year - 1, month=12, day=16)
        else:
            data_inicio = data_fim.replace(month=data_fim.month - 1, day=16)

        self.stdout.write(f"Gerando relatório de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}...")

        # 2. Simular uma requisição web na sua rota de PDF (burlar o botão)
        factory = RequestFactory()
        url = f'/graficos/exportar/pdf/?periodo=personalizado&data_inicio={data_inicio.strftime("%Y-%m-%d")}&data_fim={data_fim.strftime("%Y-%m-%d")}'
        request = factory.get(url)
        
        # Criar um "usuário fantasma" administrador para passar pelo @admin_required
        class AdminMock:
            is_authenticated = True
            is_staff = True
            is_superuser = True
            perfil = None
        request.user = AdminMock()

        # 3. Chamar a view que você já tem pronta para gerar o PDF
        response = exportar_graficos_consumo_pdf(request)

        if response.status_code != 200:
            self.stderr.write(f"Erro ao gerar PDF: Status {response.status_code}")
            return

        pdf_bytes = response.content

        # 4. Preparar o e-mail
        # Pega os e-mails configurados no Render (pode colocar vários separados por vírgula)
        emails_admin_str = os.environ.get('ADMIN_EMAILS', 'admin@seucondominio.com.br')
        destinatarios = [e.strip() for e in emails_admin_str.split(',') if e.strip()]

        assunto = f"Relatório Geral de Consumo - {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
        mensagem = (
            "Olá Administração,\n\n"
            "Segue em anexo o relatório geral consolidado de consumo de água do condomínio, "
            f"referente ao período de {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}.\n\n"
            "Com este documento, os valores das taxas excedentes já estão prontos para lançamento.\n\n"
            "Atenciosamente,\nSistema de Controle de Água"
        )

        email = EmailMessage(
            subject=assunto,
            body=mensagem,
            from_email=os.environ.get('DEFAULT_FROM_EMAIL'),
            to=destinatarios,
        )
        
        # Anexa o PDF que estava na memória RAM direto no e-mail
        nome_arquivo = f"Relatorio_Geral_Condominio_{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.pdf"
        email.attach(nome_arquivo, pdf_bytes, 'application/pdf')

        # 5. Disparar
        email.send(fail_silently=False)
        self.stdout.write(self.style.SUCCESS(f"Relatório enviado com sucesso para: {', '.join(destinatarios)}"))