from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('consumo', '0008_usuarioperfil_uniq_telefone_contato_nao_vazio'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX IF NOT EXISTS auth_user_email_ci_unique_idx "
                "ON auth_user (LOWER(email)) "
                "WHERE email IS NOT NULL AND email <> '';"
            ),
            reverse_sql="DROP INDEX IF EXISTS auth_user_email_ci_unique_idx;",
        ),
    ]
