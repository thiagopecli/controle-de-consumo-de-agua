from rest_framework import serializers
from .models import Lote, Hidrometro, Leitura


class LoteSerializer(serializers.ModelSerializer):
    total_hidrometros = serializers.SerializerMethodField()
    
    class Meta:
        model = Lote
        fields = '__all__'
    
    def get_total_hidrometros(self, obj):
        return obj.hidrometros.filter(ativo=True).count()


class HidrometroSerializer(serializers.ModelSerializer):
    lote_numero = serializers.CharField(source='lote.numero', read_only=True)
    consumo_diario = serializers.SerializerMethodField()
    consumo_diario_litros = serializers.SerializerMethodField()
    
    class Meta:
        model = Hidrometro
        fields = '__all__'
    
    def get_consumo_diario(self, obj):
        return float(obj.consumo_diario_atual())
    
    def get_consumo_diario_litros(self, obj):
        return float(obj.consumo_diario_atual_litros())


class LeituraSerializer(serializers.ModelSerializer):
    hidrometro_numero = serializers.CharField(source='hidrometro.numero', read_only=True)
    lote_numero = serializers.CharField(source='hidrometro.lote.numero', read_only=True)
    consumo_desde_ultima = serializers.SerializerMethodField()
    consumo_desde_ultima_litros = serializers.SerializerMethodField()
    
    class Meta:
        model = Leitura
        fields = '__all__'
    
    def get_consumo_desde_ultima(self, obj):
        return float(obj.consumo_desde_ultima_leitura())
    
    def get_consumo_desde_ultima_litros(self, obj):
        return float(obj.consumo_desde_ultima_leitura_litros())


class LeituraCreateSerializer(serializers.ModelSerializer):
    """Serializer otimizado para criação de leituras"""
    
    class Meta:
        model = Leitura
        fields = ['hidrometro', 'leitura', 'data_leitura', 'periodo', 'responsavel', 'observacoes', 'foto']
    
    def validate(self, data):
        # Validar se a leitura não é menor que a última leitura
        hidrometro = data.get('hidrometro')
        leitura_atual = data.get('leitura')
        
        ultima_leitura = Leitura.objects.filter(
            hidrometro=hidrometro
        ).order_by('-data_leitura').first()
        
        if ultima_leitura and leitura_atual < ultima_leitura.leitura:
            raise serializers.ValidationError(
                f"A leitura não pode ser menor que a última leitura registrada ({ultima_leitura.leitura}m³)"
            )
        
        return data
