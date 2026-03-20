from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consumo', '0003_lote_proprietario_nome_lote_telefone_whatsapp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lote',
            name='telefone_whatsapp',
            field=models.CharField(
                blank=True,
                help_text='Formato: +55DDDNUMERO ou +55DDDNUMERO; +55DDDNUMERO (até 2 números)',
                max_length=50,
                null=True,
                verbose_name='WhatsApp do Proprietário',
            ),
        ),
    ]
