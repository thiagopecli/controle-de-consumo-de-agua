# 📥 Exportação de Relatórios de Consumo

Este documento descreve a funcionalidade de exportação de relatórios de consumo de água em diferentes formatos.

## 📋 Visão Geral

O sistema permite exportar relatórios completos de consumo de água tanto do condomínio inteiro quanto de lotes específicos. Os relatórios podem ser baixados em dois formatos:

- **📄 PDF**: Ideal para apresentações e visualização
- **📊 Excel**: Ideal para análise de dados e manipulação

## 🎯 Funcionalidades

### 1. Relatório do Condomínio

**Localização**: Página de Gráficos de Consumo (`/graficos/`)

**Botões disponíveis**:
- 🔴 **Baixar PDF**: Gera relatório em PDF
- 🟢 **Baixar Excel**: Gera planilha Excel com gráficos

**Conteúdo incluído**:
- ✅ Resumo geral do consumo
- ✅ Consumo total do ano
- ✅ Consumo por período (manhã/tarde)
- ✅ Consumo mensal (todos os meses do ano)
- ✅ Top 10 lotes com maior consumo
- ✅ Número de hidrômetros e lotes ativos

### 2. Relatório de Lote Específico

**Localização**: Página de Gráficos do Lote (`/lotes/<id>/graficos/`)

**Botões disponíveis**:
- 🔴 **Baixar PDF**: Gera relatório em PDF do lote
- 🟢 **Baixar Excel**: Gera planilha Excel do lote com gráficos

**Conteúdo incluído**:
- ✅ Informações do lote (número, tipo)
- ✅ Consumo total do ano do lote
- ✅ Consumo por período (manhã/tarde)
- ✅ Consumo mensal do lote
- ✅ Número de hidrômetros ativos do lote

## 📄 Formato PDF

### Características
- **Layout**: Paisagem (A4)
- **Estrutura**: Tabelas organizadas com cores
- **Estilo**: Profissional e legível
- **Nome do arquivo**: `relatorio_consumo_condominio_AAAAMMDD.pdf` ou `relatorio_lote_XXX_AAAAMMDD.pdf`

### Elementos incluídos
1. **Cabeçalho**: Título e data de geração
2. **Resumo Geral**: Cards com informações principais
3. **Tabela de Consumo Mensal**: Todos os meses do ano
4. **Top 10 Lotes** (apenas no relatório do condomínio)

### Cores utilizadas
- 🔵 Azul (`#3498db`): Cabeçalhos principais
- 🟢 Verde (`#27ae60`): Dados mensais
- 🔴 Vermelho (`#e74c3c`): Top 10 lotes

## 📊 Formato Excel

### Características
- **Formato**: `.xlsx` (Excel 2007+)
- **Abas múltiplas**: Dados organizados por categoria
- **Gráficos integrados**: Visualizações automáticas
- **Nome do arquivo**: `relatorio_consumo_condominio_AAAAMMDD.xlsx` ou `relatorio_lote_XXX_AAAAMMDD.xlsx`

### Abas do Relatório do Condomínio

#### 1. **Aba "Resumo"**
- Consumo total do ano
- Consumo por período (manhã/tarde)
- Número de hidrômetros ativos
- Número de lotes ativos

#### 2. **Aba "Consumo Mensal"**
- Tabela com dados mensais
- 📊 Gráfico de barras do consumo mensal

#### 3. **Aba "Top 10 Lotes"**
- Posição, lote, tipo e consumo
- 📊 Gráfico de barras dos top 10

#### 4. **Aba "Consumo por Período"**
- Dados de manhã e tarde
- 📊 Gráfico de pizza da distribuição

### Abas do Relatório do Lote

#### 1. **Aba "Resumo"**
- Informações do lote
- Consumo total do ano
- Consumo por período

#### 2. **Aba "Consumo Mensal"**
- Dados mensais do lote
- 📊 Gráfico de linha do consumo mensal

#### 3. **Aba "Consumo por Período"**
- Dados de manhã e tarde
- 📊 Gráfico de pizza da distribuição

## 🎨 Interface

### Botões de Exportação

Os botões estão localizados no cabeçalho das páginas de gráficos:

```
┌─────────────────────────────────────────────────────┐
│  📊 Gráficos de Consumo                             │
│                                                     │
│  [🔴 Baixar PDF] [🟢 Baixar Excel] [← Voltar]     │
└─────────────────────────────────────────────────────┘
```

### Cores dos Botões
- **PDF**: Vermelho (`#e74c3c`)
- **Excel**: Verde (`#27ae60`)
- **Voltar**: Cinza (padrão secundário)

## 🔧 Implementação Técnica

### Bibliotecas Utilizadas

#### ReportLab (PDF)
```python
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
```

#### openpyxl (Excel)
```python
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.chart import BarChart, PieChart, LineChart, Reference
```

### Endpoints da API

#### Relatório do Condomínio
- **PDF**: `GET /graficos/exportar/pdf/`
- **Excel**: `GET /graficos/exportar/excel/`

#### Relatório do Lote
- **PDF**: `GET /lotes/<id>/graficos/exportar/pdf/`
- **Excel**: `GET /lotes/<id>/graficos/exportar/excel/`

### Views Implementadas

```python
# Condomínio
exportar_graficos_consumo_pdf(request)
exportar_graficos_consumo_excel(request)

# Lote específico
exportar_graficos_lote_pdf(request, lote_id)
exportar_graficos_lote_excel(request, lote_id)
```

## 💡 Casos de Uso

### 1. Apresentação para Moradores
- **Formato recomendado**: PDF
- **Relatório**: Condomínio completo
- **Uso**: Projetar em reuniões, compartilhar por e-mail

### 2. Análise de Consumo Individual
- **Formato recomendado**: Excel
- **Relatório**: Lote específico
- **Uso**: Acompanhamento mensal, comparação de períodos

### 3. Relatório Gerencial
- **Formato recomendado**: Excel
- **Relatório**: Condomínio completo
- **Uso**: Análise de dados, identificação de outliers

### 4. Comprovante de Consumo
- **Formato recomendado**: PDF
- **Relatório**: Lote específico
- **Uso**: Documentação oficial, registros

## 📝 Observações Importantes

### Dados Incluídos
- ✅ Apenas hidrômetros **ativos** são considerados
- ✅ Dados são calculados em **tempo real**
- ✅ Período de análise: **Ano atual completo**
- ✅ Consumo em **Litros** (convertido de m³)

### Limitações
- ⚠️ Relatórios são gerados sob demanda (não salvos)
- ⚠️ Tempo de geração depende da quantidade de dados
- ⚠️ Lotes sem hidrômetros ativos retornam erro 404

### Performance
- 📊 Otimizado para até 320 hidrômetros
- 📊 Consultas ao banco de dados são minimizadas
- 📊 Cálculos são feitos de forma eficiente

## 🚀 Como Usar

### Passo 1: Acessar a Página de Gráficos
1. Entre no sistema
2. Navegue para **Gráficos de Consumo** ou **Gráficos de Lote**

### Passo 2: Escolher o Formato
1. Clique em **Baixar PDF** para relatório em PDF
2. Clique em **Baixar Excel** para planilha Excel

### Passo 3: Salvar o Arquivo
1. O navegador iniciará o download automaticamente
2. Escolha onde salvar o arquivo
3. Abra com o programa apropriado (Adobe Reader, Excel, etc.)

## 🔄 Atualizações Futuras

Possíveis melhorias planejadas:
- [ ] Filtro de período customizado
- [ ] Comparação entre anos
- [ ] Gráficos mais detalhados no PDF
- [ ] Exportação em formato CSV
- [ ] Agendamento de relatórios automáticos
- [ ] Envio por e-mail

## 📞 Suporte

Para dúvidas ou problemas com a exportação de relatórios, consulte:
- [README.md](../README.md) - Documentação principal
- [GUIA_USO_GRAFICOS.md](GUIA_USO_GRAFICOS.md) - Guia de uso dos gráficos
- [API.md](API.md) - Documentação da API
