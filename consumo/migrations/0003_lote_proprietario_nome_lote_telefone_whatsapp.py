from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consumo', '0002_alter_leitura_leitura_alter_lote_tipo'),
    ]

    operations = [
        migrations.AddField(
            model_name='lote',
            name='proprietario_nome',
            field=models.CharField(blank=True, max_length=120, null=True, verbose_name='Nome do Proprietário'),
        ),
        migrations.AddField(
            model_name='lote',
            name='telefone_whatsapp',
            field=models.CharField(blank=True, help_text='Formato: +55DDDNUMERO (apenas dígitos com +, sem espaços)', max_length=20, null=True, verbose_name='WhatsApp do Proprietário'),
        ),
    ]
