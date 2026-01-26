# Teste do Filtro de Período

O filtro de período foi implementado com as seguintes opções:

## Opções de Filtro

1. **Últimos 7 dias** - Exibe consumo dos últimos 7 dias
2. **Últimos 15 dias** - Exibe consumo dos últimos 15 dias
3. **Últimos 30 dias** - Exibe consumo dos últimos 30 dias (padrão)
4. **Mês Atual** - Exibe consumo do dia 1 do mês atual até hoje
5. **Ano Atual** - Exibe consumo do dia 1 de janeiro até hoje
6. **Período Personalizado** - Permite selecionar data de início e fim

## Como Usar

1. Acesse a página de gráficos: http://127.0.0.1:8000/graficos/
2. No topo da página, você verá o filtro "🔍 Filtrar Período"
3. Selecione o período desejado no dropdown
4. Para períodos pré-definidos (7, 15, 30 dias, mês ou ano), a página será atualizada automaticamente
5. Para período personalizado:
   - Selecione "Período Personalizado"
   - Escolha a data de início e data de fim
   - Clique no botão "🔍 Filtrar"

## Funcionalidades

- ✅ Filtro dinâmico com seleção de período
- ✅ Auto-submit para períodos pré-definidos
- ✅ Campos de data aparecem apenas quando "Período Personalizado" é selecionado
- ✅ Validação de datas (não permite datas futuras)
- ✅ Atualização automática de todos os gráficos e cards de resumo
- ✅ Label do período é atualizado automaticamente
- ✅ Exportação PDF/Excel considera o período filtrado

## Exemplo de URLs

- Últimos 7 dias: `http://127.0.0.1:8000/graficos/?periodo=7dias`
- Últimos 15 dias: `http://127.0.0.1:8000/graficos/?periodo=15dias`
- Últimos 30 dias: `http://127.0.0.1:8000/graficos/?periodo=30dias`
- Mês Atual: `http://127.0.0.1:8000/graficos/?periodo=mes_atual`
- Ano Atual: `http://127.0.0.1:8000/graficos/?periodo=ano_atual`
- Personalizado: `http://127.0.0.1:8000/graficos/?periodo=personalizado&data_inicio=2026-01-01&data_fim=2026-01-15`
