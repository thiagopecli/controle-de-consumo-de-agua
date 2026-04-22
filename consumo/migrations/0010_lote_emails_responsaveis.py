from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consumo', '0009_auth_user_email_ci_unique_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='lote',
            name='email_responsavel',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='E-mail do Responsável 1'),
        ),
        migrations.AddField(
            model_name='lote',
            name='email_responsavel_2',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='E-mail do Responsável 2'),
        ),
    ]
