from django.db import migrations, models
import re


def separar_telefones_legados(apps, schema_editor):
    Lote = apps.get_model('consumo', 'Lote')

    for lote in Lote.objects.all().only('id', 'telefone_whatsapp', 'telefone_whatsapp_2'):
        valor = (lote.telefone_whatsapp or '').strip()
        if not valor:
            continue

        partes = [item.strip() for item in re.split(r'[;,]', valor) if item.strip()]
        if not partes:
            continue

        telefone_1 = partes[0][:20]
        telefone_2 = partes[1][:20] if len(partes) > 1 else (lote.telefone_whatsapp_2 or '').strip()[:20]

        alterou = False
        if lote.telefone_whatsapp != telefone_1:
            lote.telefone_whatsapp = telefone_1
            alterou = True
        if telefone_2 and lote.telefone_whatsapp_2 != telefone_2:
            lote.telefone_whatsapp_2 = telefone_2
            alterou = True

        if alterou:
            lote.save(update_fields=['telefone_whatsapp', 'telefone_whatsapp_2'])


class Migration(migrations.Migration):

    dependencies = [
        ('consumo', '0004_alter_lote_telefone_whatsapp'),
    ]

    operations = [
        migrations.AddField(
            model_name='lote',
            name='telefone_whatsapp_2',
            field=models.CharField(
                blank=True,
                help_text='Opcional. Formato: +55DDDNUMERO (apenas dígitos com +, sem espaços)',
                max_length=20,
                null=True,
                verbose_name='WhatsApp do Proprietário 2',
            ),
        ),
        migrations.AlterField(
            model_name='lote',
            name='telefone_whatsapp',
            field=models.CharField(
                blank=True,
                help_text='Formato: +55DDDNUMERO (apenas dígitos com +, sem espaços)',
                max_length=20,
                null=True,
                verbose_name='WhatsApp do Proprietário 1',
            ),
        ),
        migrations.RunPython(separar_telefones_legados, migrations.RunPython.noop),
    ]
