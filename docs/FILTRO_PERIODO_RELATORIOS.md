# Filtro de Período nos Relatórios (PDF e Excel)

## Resumo

Os relatórios de exportação (PDF e Excel) agora respeitam o filtro de período selecionado na página de gráficos. Isso garante que o conteúdo exportado seja consistente com o que é visualizado na tela.

## Alterações Realizadas

### 1. Exportação PDF (`exportar_graficos_consumo_pdf`)

**Modificações:**
- ✅ Implementada mesma lógica de filtro de período da view `graficos_consumo`
- ✅ Suporte para 6 tipos de período:
  - Últimos 7 dias
  - Últimos 15 dias
  - Últimos 30 dias
  - Mês Atual
  - Ano Atual
  - Período Personalizado
- ✅ Cálculo de consumo diário baseado no período filtrado
- ✅ Cálculo de consumo por período (manhã/tarde) baseado no filtro
- ✅ Top 10 lotes calculado para o período selecionado
- ✅ Título do relatório atualizado para incluir o período (ex: "Últimos 7 dias")
- ✅ Gráficos atualizados com títulos dinâmicos

**Seções do PDF:**
- 📊 Resumo Geral (com período selecionado)
- 📈 Gráfico de Consumo Diário (período filtrado)
- 🏆 Top 10 Lotes com Maior Consumo (período filtrado)
- 🥧 Distribuição de Consumo por Período (manhã/tarde no período filtrado)

### 2. Exportação Excel (`exportar_graficos_consumo_excel`)

**Modificações:**
- ✅ Implementada mesma lógica de filtro de período
- ✅ Suporte para os mesmos 6 tipos de período
- ✅ Cálculo de consumo diário baseado no período filtrado
- ✅ Cálculo de consumo por período (manhã/tarde) baseado no filtro
- ✅ Top 10 lotes calculado para o período selecionado
- ✅ Título do relatório atualizado para incluir o período

**Abas do Excel:**
1. **Resumo**
   - Indicadores gerais do período
   - Período selecionado
   - Consumo total, manhã e tarde
   - Hidrômetros e lotes ativos

2. **Consumo Diário** (substituiu "Consumo Mensal")
   - Dados diários do período filtrado
   - Gráfico de linha mostrando evolução diária
   - Adaptável a qualquer período

3. **Top 10 Lotes**
   - Ranking dos lotes com maior consumo no período
   - Gráfico de barras
   - Dados exportáveis

4. **Consumo por Período**
   - Comparação manhã vs tarde
   - Gráfico de pizza
   - Percentuais

### 3. Template HTML (`graficos_consumo.html`)

**Modificações:**
- ✅ Links de exportação agora incluem parâmetros GET do filtro
- ✅ Usando `{{ request.GET.urlencode }}` para preservar filtros
- ✅ PDF e Excel recebem automaticamente:
  - `periodo` (7dias, 15dias, 30dias, mes_atual, ano_atual, personalizado)
  - `data_inicio` (quando período personalizado)
  - `data_fim` (quando período personalizado)

## Como Usar

### 1. Na Interface Web

1. Acesse: http://127.0.0.1:8000/graficos/
2. Selecione o período desejado no filtro
3. Visualize os gráficos atualizados
4. Clique em "📄 Baixar PDF" ou "📊 Baixar Excel"
5. O relatório será gerado com os mesmos dados exibidos na tela

### 2. URLs de Exemplo

**Últimos 7 dias:**
```
http://127.0.0.1:8000/graficos/pdf/?periodo=7dias
http://127.0.0.1:8000/graficos/excel/?periodo=7dias
```

**Mês Atual:**
```
http://127.0.0.1:8000/graficos/pdf/?periodo=mes_atual
http://127.0.0.1:8000/graficos/excel/?periodo=mes_atual
```

**Período Personalizado:**
```
http://127.0.0.1:8000/graficos/pdf/?periodo=personalizado&data_inicio=2026-01-01&data_fim=2026-01-15
http://127.0.0.1:8000/graficos/excel/?periodo=personalizado&data_inicio=2026-01-01&data_fim=2026-01-15
```

## Vantagens

✅ **Consistência**: Relatórios sempre refletem o que está na tela
✅ **Flexibilidade**: Exporte qualquer período desejado
✅ **Praticidade**: Não precisa selecionar período novamente ao exportar
✅ **Rastreabilidade**: Título do relatório indica claramente o período analisado
✅ **Análise Personalizada**: Compare diferentes períodos exportando múltiplos relatórios

## Observações Técnicas

### Lógica de Período
- O período é processado da mesma forma na tela e nos relatórios
- Datas futuras são automaticamente limitadas ao dia atual
- Período padrão: últimos 30 dias (quando não especificado)

### Cálculo de Consumo
- **Consumo Diário**: Diferença entre leituras do mesmo dia
- **Consumo Manhã/Tarde**: Separado por campo `periodo` da leitura
- **Top 10 Lotes**: Soma do consumo de todos os hidrômetros do lote no período

### Formato dos Dados
- **Datas**: dd/mm/YYYY
- **Valores**: Litros (L) com separador de milhares
- **Precisão**: 2 casas decimais para valores fracionários

## Próximos Passos Sugeridos

1. ✅ Testar exportação com diferentes períodos
2. ✅ Verificar se gráficos estão sendo gerados corretamente
3. ✅ Validar cálculos em períodos personalizados
4. ⚠️ Considerar adicionar filtro de período também nos gráficos por lote

## Arquivos Modificados

1. `consumo/views.py`:
   - `exportar_graficos_consumo_pdf()` - Linhas ~672-1030
   - `exportar_graficos_consumo_excel()` - Linhas ~1030-1360

2. `templates/consumo/graficos_consumo.html`:
   - Links de exportação - Linhas 17-22

## Compatibilidade

- ✅ Django 4.x
- ✅ Python 3.13
- ✅ ReportLab (PDF)
- ✅ openpyxl (Excel)
- ✅ Matplotlib (Gráficos PDF)
- ✅ Todos os navegadores modernos

---

**Data de Implementação:** 26 de janeiro de 2026
**Desenvolvido por:** GitHub Copilot com Claude Sonnet 4.5
