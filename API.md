# 🔌 Documentação da API REST

## Base URL

```
http://localhost:8000/api/
```

## Autenticação

Por padrão, a API está aberta para desenvolvimento. Para produção, considere adicionar autenticação JWT.

## Endpoints Disponíveis

### 📍 Lotes

#### Listar todos os lotes
```http
GET /api/lotes/
```

**Resposta:**
```json
{
  "count": 320,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "numero": "1",
      "tipo": "residencial",
      "endereco": "Rua 1, Casa 1",
      "ativo": true,
      "total_hidrometros": 1,
      "criado_em": "2026-01-20T10:00:00Z",
      "atualizado_em": "2026-01-20T10:00:00Z"
    }
  ]
}
```

#### Criar novo lote
```http
POST /api/lotes/
Content-Type: application/json

{
  "numero": "999",
  "tipo": "residencial",
  "endereco": "Rua Nova, 123",
  "ativo": true
}
```

#### Obter detalhes de um lote
```http
GET /api/lotes/{id}/
```

#### Atualizar lote
```http
PUT /api/lotes/{id}/
Content-Type: application/json

{
  "numero": "999",
  "tipo": "residencial",
  "endereco": "Rua Nova, 123 - Atualizada",
  "ativo": true
}
```

#### Deletar lote
```http
DELETE /api/lotes/{id}/
```

#### Obter hidrômetros de um lote
```http
GET /api/lotes/{id}/hidrometros/
```

#### Obter consumo total de um lote
```http
GET /api/lotes/{id}/consumo_total/?data_inicio=2026-01-01&data_fim=2026-01-31
```

**Resposta:**
```json
{
  "lote": "1",
  "periodo": "2026-01-01 a 2026-01-31",
  "consumo_total_m3": 45.678
}
```

---

### 🔧 Hidrômetros

#### Listar todos os hidrômetros
```http
GET /api/hidrometros/
```

**Parâmetros de Query:**
- `lote` - Filtrar por ID do lote
- `ativo` - Filtrar por status (true/false)

**Exemplos:**
```http
GET /api/hidrometros/?lote=1
GET /api/hidrometros/?ativo=true
GET /api/hidrometros/?lote=1&ativo=true
```

**Resposta:**
```json
{
  "count": 320,
  "results": [
    {
      "id": 1,
      "numero": "H0001",
      "lote": 1,
      "lote_numero": "1",
      "localizacao": "Entrada principal",
      "data_instalacao": "2025-12-01",
      "ativo": true,
      "consumo_diario": 2.5,
      "observacoes": null,
      "criado_em": "2026-01-20T10:00:00Z",
      "atualizado_em": "2026-01-20T10:00:00Z"
    }
  ]
}
```

#### Criar novo hidrômetro
```http
POST /api/hidrometros/
Content-Type: application/json

{
  "numero": "H9999",
  "lote": 1,
  "localizacao": "Lateral direita",
  "data_instalacao": "2026-01-20",
  "ativo": true,
  "observacoes": "Hidrômetro novo"
}
```

#### Obter detalhes de um hidrômetro
```http
GET /api/hidrometros/{id}/
```

#### Obter leituras de um hidrômetro por período
```http
GET /api/hidrometros/{id}/leituras_periodo/?data_inicio=2026-01-01&data_fim=2026-01-31
```

**Resposta:**
```json
[
  {
    "id": 1,
    "hidrometro": 1,
    "hidrometro_numero": "H0001",
    "lote_numero": "1",
    "leitura": "125.450",
    "data_leitura": "2026-01-20T08:00:00Z",
    "periodo": "manha",
    "responsavel": "João Silva",
    "consumo_desde_ultima": 2.5,
    "observacoes": null,
    "foto": null
  }
]
```

#### Obter estatísticas de um hidrômetro
```http
GET /api/hidrometros/{id}/estatisticas/?dias=30
```

**Resposta:**
```json
{
  "hidrometro": "H0001",
  "periodo_dias": 30,
  "total_leituras": 60,
  "consumo_total_m3": 75.450,
  "consumo_medio_dia_m3": 2.515,
  "primeira_leitura": "100.000",
  "ultima_leitura": "175.450"
}
```

---

### 📊 Leituras

#### Listar todas as leituras
```http
GET /api/leituras/
```

**Parâmetros de Query:**
- `hidrometro` - Filtrar por ID do hidrômetro
- `data_inicio` - Data inicial (formato: YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS)
- `data_fim` - Data final
- `periodo` - Filtrar por período (manha/tarde)

**Exemplos:**
```http
GET /api/leituras/?hidrometro=1
GET /api/leituras/?data_inicio=2026-01-01&data_fim=2026-01-31
GET /api/leituras/?periodo=manha
GET /api/leituras/?hidrometro=1&periodo=manha&data_inicio=2026-01-01
```

**Resposta:**
```json
{
  "count": 140,
  "results": [
    {
      "id": 1,
      "hidrometro": 1,
      "hidrometro_numero": "H0001",
      "lote_numero": "1",
      "leitura": "125.450",
      "data_leitura": "2026-01-20T08:00:00Z",
      "periodo": "manha",
      "responsavel": "João Silva",
      "consumo_desde_ultima": 2.5,
      "observacoes": "Leitura normal",
      "foto": null,
      "criado_em": "2026-01-20T08:05:00Z",
      "atualizado_em": "2026-01-20T08:05:00Z"
    }
  ]
}
```

#### Criar nova leitura
```http
POST /api/leituras/
Content-Type: application/json

{
  "hidrometro": 1,
  "leitura": 125.450,
  "data_leitura": "2026-01-20T08:00:00",
  "periodo": "manha",
  "responsavel": "João Silva",
  "observacoes": "Leitura normal"
}
```

**Validações:**
- A leitura não pode ser menor que a última leitura registrada
- Os campos `hidrometro`, `leitura`, `data_leitura` e `periodo` são obrigatórios
- O período deve ser "manha" ou "tarde"

#### Criar leitura com foto
```http
POST /api/leituras/
Content-Type: multipart/form-data

hidrometro=1
leitura=125.450
data_leitura=2026-01-20T08:00:00
periodo=manha
responsavel=João Silva
foto=[arquivo de imagem]
```

#### Obter detalhes de uma leitura
```http
GET /api/leituras/{id}/
```

#### Atualizar leitura
```http
PUT /api/leituras/{id}/
Content-Type: application/json

{
  "hidrometro": 1,
  "leitura": 125.450,
  "data_leitura": "2026-01-20T08:00:00",
  "periodo": "manha",
  "responsavel": "João Silva",
  "observacoes": "Leitura atualizada"
}
```

#### Deletar leitura
```http
DELETE /api/leituras/{id}/
```

#### Obter últimas leituras de todos os hidrômetros
```http
GET /api/leituras/ultimas_leituras/
```

**Resposta:**
```json
[
  {
    "hidrometro": "H0001",
    "lote": "1",
    "leitura": 125.450,
    "data_leitura": "2026-01-20T17:00:00Z",
    "periodo": "tarde"
  },
  {
    "hidrometro": "H0002",
    "lote": "2",
    "leitura": 98.750,
    "data_leitura": "2026-01-20T17:00:00Z",
    "periodo": "tarde"
  }
]
```

#### Criar múltiplas leituras
```http
POST /api/leituras/leitura_em_lote/
Content-Type: application/json

{
  "leituras": [
    {
      "hidrometro": 1,
      "leitura": 125.450,
      "data_leitura": "2026-01-20T08:00:00",
      "periodo": "manha",
      "responsavel": "João Silva"
    },
    {
      "hidrometro": 2,
      "leitura": 98.750,
      "data_leitura": "2026-01-20T08:00:00",
      "periodo": "manha",
      "responsavel": "João Silva"
    }
  ]
}
```

**Resposta:**
```json
{
  "criadas": 2,
  "erros": 0,
  "leituras_criadas": [
    {
      "id": 1,
      "hidrometro": 1,
      "leitura": "125.450",
      "data_leitura": "2026-01-20T08:00:00Z",
      "periodo": "manha"
    },
    {
      "id": 2,
      "hidrometro": 2,
      "leitura": "98.750",
      "data_leitura": "2026-01-20T08:00:00Z",
      "periodo": "manha"
    }
  ],
  "leituras_com_erro": []
}
```

---

## 📝 Códigos de Status HTTP

- `200 OK` - Requisição bem-sucedida
- `201 Created` - Recurso criado com sucesso
- `204 No Content` - Recurso deletado com sucesso
- `400 Bad Request` - Dados inválidos
- `404 Not Found` - Recurso não encontrado
- `500 Internal Server Error` - Erro no servidor

## 🔍 Filtros e Busca

### Busca por texto
Adicione `?search=termo` para buscar em campos específicos:

```http
GET /api/lotes/?search=1
GET /api/hidrometros/?search=H0001
GET /api/leituras/?search=João
```

### Ordenação
Adicione `?ordering=campo` para ordenar resultados:

```http
GET /api/lotes/?ordering=numero
GET /api/lotes/?ordering=-numero  # Ordem decrescente
GET /api/hidrometros/?ordering=data_instalacao
GET /api/leituras/?ordering=-data_leitura
```

### Paginação
Por padrão, a API retorna 100 itens por página. Use `?page=` para navegar:

```http
GET /api/leituras/?page=2
GET /api/hidrometros/?page=3
```

## 📊 Formatos de Data

Use o formato ISO 8601 para datas:

- **Data:** `YYYY-MM-DD` (ex: `2026-01-20`)
- **Data e Hora:** `YYYY-MM-DDTHH:MM:SS` (ex: `2026-01-20T08:30:00`)
- **Com Timezone:** `YYYY-MM-DDTHH:MM:SS+00:00` (ex: `2026-01-20T08:30:00-03:00`)

## 💡 Exemplos Práticos

### Registrar leitura da manhã
```bash
curl -X POST http://localhost:8000/api/leituras/ \
  -H "Content-Type: application/json" \
  -d '{
    "hidrometro": 1,
    "leitura": 125.450,
    "data_leitura": "2026-01-20T08:00:00",
    "periodo": "manha",
    "responsavel": "João Silva"
  }'
```

### Obter consumo de um hidrômetro nos últimos 30 dias
```bash
curl http://localhost:8000/api/hidrometros/1/estatisticas/?dias=30
```

### Listar leituras de hoje
```bash
curl "http://localhost:8000/api/leituras/?data_inicio=2026-01-20T00:00:00&data_fim=2026-01-20T23:59:59"
```

### Buscar hidrômetros de um lote específico
```bash
curl http://localhost:8000/api/hidrometros/?lote=1
```

## 🔒 Considerações de Segurança

Para produção, considere:

1. Adicionar autenticação JWT
2. Configurar CORS adequadamente
3. Limitar taxa de requisições (rate limiting)
4. Usar HTTPS
5. Validar todos os inputs
6. Implementar logs de auditoria

## 📚 Navegador da API

Acesse http://localhost:8000/api/ no navegador para uma interface interativa onde você pode:

- Explorar todos os endpoints
- Testar requisições
- Ver documentação automática
- Visualizar schemas de dados

---

**Documentação da API - v1.0.0**
