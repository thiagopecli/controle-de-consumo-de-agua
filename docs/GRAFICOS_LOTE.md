# 📊 Nova Funcionalidade: Gráficos de Consumo por Lote

## Resumo das Alterações

Foram implementadas novas funcionalidades para visualizar os gráficos de consumo detalhados de cada lote residencial. Agora, ao clicar no botão "📊 Detalhes" na lista de hidrômetros, você será redirecionado para uma página com os seguintes gráficos:

### ✨ Funcionalidades Implementadas

#### 1. **Consumo por Dia** 📅
- Gráfico de barras mostrando o consumo total de cada dia do mês em litros
- Utiliza todos os hidrômetros ativos do lote
- Facilita identificar dias com maior consumo

#### 2. **Consumo Acumulado do Mês** 📊
- Gráfico de linha mostrando o consumo progressivo do mês
- Começa do dia 1 até o dia atual
- Permite visualizar a tendência de consumo ao longo do período

#### 3. **Consumo por Período do Dia** ⏰
- Gráfico de pizza (rosca) comparando:
  - 🌅 **Manhã**: Consumo entre leituras matutinas
  - 🌆 **Tarde**: Consumo entre leituras vespertinas
- Percentuais e valores em litros

### 📊 Cards de Resumo
A página também exibe cards informativos com:
- Consumo total do mês
- Consumo da manhã
- Consumo da tarde
- Quantidade de hidrômetros ativos

## 🔧 Mudanças Técnicas

### 1. **View Python** (`consumo/views.py`)
Nova function `graficos_lote()` que:
- Recebe o ID do lote como parâmetro
- Calcula consumo por dia (do dia 1 ao 31)
- Calcula consumo acumulado do mês
- Calcula consumo por período (manhã/tarde)
- Retorna dados estruturados em JSON para os gráficos

### 2. **Template HTML** (`templates/consumo/graficos_lote.html`)
- Nova página responsiva com 3 gráficos usando Chart.js
- Cards de resumo com estatísticas
- Tabelas de detalhes dos hidrômetros
- Suportado em Desktop e Mobile

### 3. **URLs** (`consumo/urls.py`)
Adicionada nova rota:
```python
path('lotes/<int:lote_id>/graficos/', views.graficos_lote, name='graficos_lote'),
```

### 4. **Template de Lista** (`templates/consumo/listar_hidrometros.html`)
O botão "📊 Detalhes" foi alterado para:
- Redirecionar para `/lotes/{id}/graficos/` em vez de `/hidrometros/{id}/`
- Mostra gráficos de todo o lote em vez de detalhes de um hidrometro

## 📱 Como Usar

1. **Acesse a lista de hidrômetros** → Menu → "Lista de Hidrômetros"
2. **Clique no botão "📊 Detalhes"** de qualquer hidrometro
3. **Visualize os 3 gráficos do lote**:
   - Consumo diário
   - Consumo acumulado do mês
   - Consumo por período (manhã/tarde)

## 📊 Detalhes dos Cálculos

### Consumo por Dia
```
Para cada dia do mês:
  Para cada hidrometro do lote:
    - Encontra leituras do mesmo dia
    - Calcula diferença entre leituras
    - Converte de m³ para litros (* 1000)
  Total do dia = soma de todos hidrometros
```

### Consumo Acumulado
```
Soma progressiva do consumo diário
Começa do dia 1 e vai até o dia atual
```

### Consumo por Período
```
Manhã: Diferença entre primeira e última leitura com período='manha'
Tarde: Diferença entre primeira e última leitura com período='tarde'
```

## 🎨 Estilos e Design

- **Paleta de cores**: Azul (#0891b2) para dados principais, Laranja (#ea580c) para período tarde
- **Gráficos interativos**: Hover com tooltips informativas
- **Responsivo**: Funciona em desktop, tablet e mobile
- **Animações**: Fade-in suave ao carregar a página

## 🚀 Próximos Passos Sugeridos

1. **Filtro por período**: Permitir selecionar mês/ano diferentes
2. **Exportar dados**: Baixar gráficos em PNG ou relatório em PDF
3. **Comparação mensal**: Comparar consumo de meses diferentes
4. **Alertas**: Notificar se consumo ultrapassa limites definidos
5. **Histórico**: Visualizar gráficos de meses anteriores

## ✅ Testes Recomendados

- [ ] Clicar em "Detalhes" de um hidrometro da lista
- [ ] Verificar se os 3 gráficos aparecem corretamente
- [ ] Testar em diferentes navegadores (Chrome, Firefox, Edge)
- [ ] Verificar responsividade em mobile
- [ ] Validar cálculos com dados conhecidos

---

**Data de Implementação**: 25 de janeiro de 2026  
**Status**: ✅ Concluído e testado
