# Generated migration to populate numero_sequencia field

from django.db import migrations


def populate_numero_sequencia(apps, schema_editor):
    """Extrai o número inteiro do campo 'numero' e popula 'numero_sequencia'"""
    Lote = apps.get_model('consumo', 'Lote')
    
    lotes_para_atualizar = []
    
    for lote in Lote.objects.all():
        try:
            # Tenta converter o número para inteiro
            numero_int = int(lote.numero)
            lote.numero_sequencia = numero_int
        except (ValueError, TypeError):
            # Se não conseguir converter, deixa o valor padrão (0)
            lote.numero_sequencia = 0
        
        lotes_para_atualizar.append(lote)
    
    # Atualiza todos de uma vez (mais eficiente)
    Lote.objects.bulk_update(lotes_para_atualizar, ['numero_sequencia'], batch_size=1000)


def reverse_populate(apps, schema_editor):
    """Reverte a população do campo numero_sequencia"""
    Lote = apps.get_model('consumo', 'Lote')
    Lote.objects.all().update(numero_sequencia=0)


class Migration(migrations.Migration):

    dependencies = [
        ('consumo', '0011_alter_lote_options_lote_numero_sequencia'),
    ]

    operations = [
        migrations.RunPython(populate_numero_sequencia, reverse_populate),
    ]

