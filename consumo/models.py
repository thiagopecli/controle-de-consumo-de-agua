from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Lote(models.Model):
    """Modelo para representar um lote residencial"""
    TIPO_CHOICES = [
        ('residencial', 'Residencial'),
        ('administracao', 'Uso do Condomínio'),
    ]
    
    numero = models.CharField(
        max_length=10,
        unique=True,
        verbose_name='Número do Lote',
        help_text='Número identificador do lote'
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='residencial',
        verbose_name='Tipo'
    )
    endereco = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Endereço'
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativo'
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em'
    )

    class Meta:
        verbose_name = 'Lote'
        verbose_name_plural = 'Lotes'
        ordering = ['numero']

    def __str__(self):
        return f"Lote {self.numero} - {self.get_tipo_display()}"


class Hidrometro(models.Model):
    """Modelo para representar um hidrômetro"""
    numero = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Número do Hidrômetro',
        help_text='Número serial do hidrômetro'
    )
    lote = models.ForeignKey(
        Lote,
        on_delete=models.CASCADE,
        related_name='hidrometros',
        verbose_name='Lote'
    )
    localizacao = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Localização',
        help_text='Descrição da localização física do hidrômetro'
    )
    data_instalacao = models.DateField(
        verbose_name='Data de Instalação'
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativo'
    )
    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observações'
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em'
    )

    class Meta:
        verbose_name = 'Hidrômetro'
        verbose_name_plural = 'Hidrômetros'
        ordering = ['numero']

    def __str__(self):
        return f"Hidrômetro {self.numero} - {self.lote}"

    def consumo_diario_atual(self):
        """Retorna o consumo do dia atual em m³"""
        from django.utils import timezone
        hoje = timezone.now().date()
        leituras_hoje = self.leituras.filter(data_leitura__date=hoje).order_by('data_leitura')
        
        if leituras_hoje.count() >= 2:
            primeira = leituras_hoje.first()
            ultima = leituras_hoje.last()
            return ultima.leitura - primeira.leitura
        return 0
    
    def consumo_diario_atual_litros(self):
        """Retorna o consumo do dia atual em litros"""
        consumo_m3 = self.consumo_diario_atual()
        return float(consumo_m3) * 1000


class Leitura(models.Model):
    """Modelo para representar uma leitura de hidrômetro"""
    PERIODO_CHOICES = [
        ('manha', 'Manhã'),
        ('tarde', 'Tarde'),
    ]
    
    hidrometro = models.ForeignKey(
        Hidrometro,
        on_delete=models.CASCADE,
        related_name='leituras',
        verbose_name='Hidrômetro'
    )
    leitura = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        validators=[MinValueValidator(0), MaxValueValidator(99999.999)],
        verbose_name='Leitura (m³)',
        help_text='Valor da leitura em metros cúbicos (máximo: 99999.999)'
    )
    data_leitura = models.DateTimeField(
        verbose_name='Data e Hora da Leitura'
    )
    periodo = models.CharField(
        max_length=10,
        choices=PERIODO_CHOICES,
        verbose_name='Período'
    )
    responsavel = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Responsável pela Leitura'
    )
    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observações'
    )
    foto = models.ImageField(
        upload_to='leituras/%Y/%m/%d/',
        blank=True,
        null=True,
        verbose_name='Foto da Leitura'
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em'
    )

    class Meta:
        verbose_name = 'Leitura'
        verbose_name_plural = 'Leituras'
        ordering = ['-data_leitura']
        unique_together = ['hidrometro', 'data_leitura', 'periodo']

    def __str__(self):
        return f"{self.hidrometro} - {self.data_leitura.strftime('%d/%m/%Y %H:%M')} - {self.leitura}m³"

    def consumo_desde_ultima_leitura(self):
        """Calcula o consumo desde a última leitura em m³"""
        leitura_anterior = Leitura.objects.filter(
            hidrometro=self.hidrometro,
            data_leitura__lt=self.data_leitura
        ).order_by('-data_leitura').first()
        
        if leitura_anterior:
            return self.leitura - leitura_anterior.leitura
        return 0
    
    def consumo_desde_ultima_leitura_litros(self):
        """Calcula o consumo desde a última leitura em litros"""
        consumo_m3 = self.consumo_desde_ultima_leitura()
        return float(consumo_m3) * 1000

