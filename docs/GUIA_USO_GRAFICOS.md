# 🎯 Como Usar - Gráficos de Consumo por Lote

## 📍 Localização da Nova Funcionalidade

Quando você clica em "📊 Detalhes" na **Lista de Hidrômetros**, agora será levado para uma página de gráficos do lote completo.

---

## 🚀 Passo a Passo

### 1️⃣ Acesse a Lista de Hidrômetros
- No menu principal, clique em **"Lista de Hidrômetros"**
- OU dirija-se para: `/hidrometros/`

### 2️⃣ Clique no Botão de Detalhes
- Procure pela coluna **"Ações"**
- Clique no botão verde **"📊 Detalhes"**

### 3️⃣ Visualize os Gráficos
Você será levado para uma página com:

```
┌────────────────────────────────────────────────┐
│         GRÁFICOS DO LOTE XXX                   │
│  Tipo: Residencial | Período: Janeiro 2026    │
└────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ Cards de Resumo:                                     │
│  📈 Consumo Total    │ 💧 Hidrômetros Ativos          │
│  X.XXX L             │  #                             │
└──────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐
│  📅 Consumo por Dia  │  │  📈 Consumo Geral    │
│  (Gráfico de Barras) │  │  (Gráfico de Linha)  │
│                      │  │                      │
│  [Barras azuis]      │  │  [Linha verde]       │
│  por dia do mês      │  │  Acumulado do mês    │
└──────────────────────┘  └──────────────────────┘

```

---

## 📊 O Que Cada Gráfico Mostra

### 📅 **Gráfico 1: Consumo por Dia**
- **O quê**: Litros consumidos em cada dia do mês
- **Como ler**: 
  - Quanto mais alta a barra, maior o consumo daquele dia
  - Dias com barras pequenas tiveram pouco consumo
  - Dias em branco = nenhuma leitura registrada
- **Exemplo**: Dia 5 consumiu 150 litros, Dia 10 consumiu 180 litros

### 📈 **Gráfico 2: Consumo Acumulado do Mês**
- **O quê**: Consumo total progressivo desde o dia 1
- **Como ler**:
  - Começa no dia 1 e vai até o dia atual
  - Linha sempre sobe (acumula consumo)
  - Pode ver a tendência geral do mês
- **Exemplo**: 
  - Dia 1: 100 L
  - Dia 2: 230 L (100 + 130)
  - Dia 3: 380 L (230 + 150)


---

## 📱 Visualização em Diferentes Dispositivos

### 💻 Desktop (tela grande)
- Gráficos lado a lado
- Cards de resumo em 4 colunas
- Tabelas lado a lado

### 📱 Smartphone (tela pequena)
- Gráficos um abaixo do outro
- Cards empilhados
- Tabelas com scroll horizontal

### 📲 Tablet
- Layout intermediário
- 2 gráficos por linha quando possível

---

## 🔄 Atualizar os Dados

Os gráficos mostram sempre o **mês atual** (janeiro 2026).

### Para ver gráficos atualizados:
1. Registre novas leituras do hidrômetro
2. Volte para a página de gráficos
3. Os dados atualizarão automaticamente

---

## 💡 Dicas Úteis

### Analisar Consumo Anormalmente Alto
1. Olhe o gráfico diário
2. Identifique qual dia teve maior consumo
3. Clique em "Hidrômetros do Lote" para ver cada equipamento
4. Verifique se há algum problema (vazamento?)


### Entender a Tendência do Mês
1. Observe o gráfico de linha (consumo acumulado)
2. Se subir muito nos primeiros dias = consumo alto
3. Se subir lentamente = consumo moderado

---

## ❓ Perguntas Frequentes

### P: Por que alguns dias não aparecem no gráfico?
**R**: Provavelmente não há leituras registradas naquele dia. A página mostra todos os 31 dias, mas com valor 0 se não houver dados.

### P: Posso ver meses anteriores?
**R**: Atualmente mostra apenas o mês atual (janeiro). Essa funcionalidade pode ser adicionada no futuro.

### P: Os valores estão em litros ou metros cúbicos?
**R**: Sempre em **litros (L)**. A conversão é automática do hidrômetro (que lê em m³).

### P: Qual é a fórmula de cálculo?
**R**: 
- Consumo = (Leitura Final - Leitura Inicial) × 1000
- Exemplo: Se o hidrômetro passou de 10.5 m³ para 10.8 m³ = 0.3 m³ = 300 L

### P: E se não há leituras registradas?
**R**: Aparece a mensagem "Nenhum hidrômetro ativo encontrado para este lote."

---

## 🔗 Navegação Rápida

- **Voltar para Lista de Hidrômetros**: Clique em "← Voltar para Lista"
- **Ver Detalhes de um Hidrometro**: Clique no número do hidrometro na tabela
- **Registrar Nova Leitura**: Menu → "Registrar Leitura"

---

## 🎓 Aprendendo Mais

### Modelo de Dados
- **Lote**: Unidade residencial (tem vários hidrômetros)
- **Hidrometro**: Equipamento que mede consumo (um por lote geralmente)
- **Leitura**: Valor capturado em um momento específico

### Períodos de Leitura
- 🌅 **Manhã**: Leituras feitas pela manhã (tipicamente 6h-12h)
- 🌆 **Tarde**: Leituras feitas à tarde/noite (tipicamente 12h-18h)

---

## 📞 Suporte

Se encontrar problemas:
1. Verifique se há leituras registradas para o lote
2. Tente recarregar a página (F5)
3. Verifique o console do navegador (F12) para erros
4. Contacte o administrador do sistema

---

**Última atualização**: 25 de janeiro de 2026  
**Versão**: 1.0
