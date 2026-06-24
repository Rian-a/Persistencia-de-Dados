# 📦 Backend de Persistência — Trabalho Final

> Servidor Flask que dá "memória" a um app de visualização de algoritmos de ordenação e busca, integrando a **API pública do Mercado Livre** e persistindo dados nos formatos **JSON**, **CSV** e **Pickle**.

---

## 📋 Índice

- [Visão geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [API utilizada — Mercado Livre](#api-utilizada--mercado-livre)
- [Formatos de persistência implementados](#formatos-de-persistência-implementados)
- [Comparação: tamanho × tempo](#comparação-tamanho--tempo)
- [Endpoints](#endpoints)
- [Como rodar](#como-rodar)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Robustez e tratamento de erros](#robustez-e-tratamento-de-erros)

---

## Visão geral

Este backend conecta um frontend Next.js (visualizador de algoritmos) a dados reais de produtos. O fluxo principal é:

1. Buscar produtos na API do Mercado Livre
2. Salvar o dataset em disco em um dos três formatos (JSON, CSV, Pickle)
3. Recarregar os dados localmente sem precisar de internet
4. Comparar os formatos em tamanho de arquivo e velocidade de I/O

---

## Arquitetura

```
┌──────────────────────────────────────────┐
│         Frontend Next.js (porta 3000)     │
│   persistenceService.ts → usePersistence  │
└────────────────┬─────────────────────────┘
                 │  HTTP/REST
                 ▼
┌──────────────────────────────────────────┐
│        Backend Python Flask (porta 5000)  │
│  app.py — 6 endpoints                    │
└──────┬───────────────────────────────────┘
       │
  ┌────┴─────────────────────┐
  │                          │
  ▼                          ▼
API Mercado Livre       Disco local
(HTTPS externo)         dados/dados.json
                        dados/dados.csv
                        dados/dados.pkl
```

O frontend nunca chama `fetch` diretamente nos componentes — toda comunicação passa pelo `persistenceService.ts`, que centraliza a base URL (`NEXT_PUBLIC_PERSISTENCE_API_URL` ou `http://localhost:5000`) e trata erros em classes tipadas (`PersistenceError`).

---

## API utilizada — Mercado Livre

**Endpoint base:**

```
GET https://api.mercadolivre.com.br/sites/MLB/search
```

**Parâmetros usados:**

| Parâmetro | Valor    | Descrição                          |
|-----------|----------|------------------------------------|
| `q`       | notebook | Termo de busca                     |
| `limit`   | 50       | Máximo de resultados por requisição|

**Exemplo de requisição:**

```
GET https://api.mercadolivre.com.br/sites/MLB/search?q=notebook&limit=50
```

**Campos extraídos de cada resultado:**

| Campo                 | Tipo    | Descrição                              |
|-----------------------|---------|----------------------------------------|
| `id`                  | string  | Identificador único do anúncio         |
| `title`               | string  | Nome do produto                        |
| `price`               | float   | Preço em BRL                           |
| `sold_quantity`       | int     | Unidades vendidas                      |
| `available_quantity`  | int     | Estoque disponível                     |

**Resposta normalizada:**

```json
{
  "products": [
    {
      "id": "MLB123456",
      "title": "Notebook Dell Inspiron 15",
      "price": 3499.99,
      "sold_quantity": 150,
      "available_quantity": 25
    }
  ],
  "origin": "API Mercado Livre",
  "count": 50,
  "status": "online"
}
```

**Fallback:** caso a API esteja indisponível (timeout, erro HTTP, lista vazia), o servidor responde com 30 produtos mock e sinaliza `"origin": "API Mercado Livre (mock)"`, mantendo o app funcional em apresentações sem internet.

A API do Mercado Livre é **pública e não exige autenticação** para buscas simples no site `MLB` (Brasil).

---

## Formatos de persistência implementados

### 1. JSON — `json.dump` / `json.load`

```python
# Salvar
with open("dados.json", "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

# Carregar
with open("dados.json", "r", encoding="utf-8") as f:
    data = json.load(f)
```

**Características:**
- Formato de texto, completamente legível em qualquer editor
- Estrutura hierárquica com suporte nativo a `str`, `float`, `int`, `list`, `dict`
- Padrão universal de APIs REST — fácil de inspecionar e depurar
- **Desvantagem:** repete as chaves (`"id"`, `"title"`, etc.) em cada objeto, inflando o tamanho

**Trecho do arquivo gerado:**
```json
[
  {
    "id": "1",
    "title": "Notebook Dell Inspiron 15",
    "price": 3499.99,
    "sold_quantity": 150,
    "available_quantity": 25
  },
  ...
]
```

---

### 2. CSV — `csv.DictWriter` / `csv.DictReader`

```python
campos = ["id", "title", "price", "sold_quantity", "available_quantity"]

# Salvar
with open("dados.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=campos)
    writer.writeheader()
    writer.writerows(products)

# Carregar (com conversão de tipos)
with open("dados.csv", "r", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    data = [
        {
            "id": row["id"],
            "title": row["title"],
            "price": float(row["price"]),
            "sold_quantity": int(row["sold_quantity"]),
            "available_quantity": int(row["available_quantity"]),
        }
        for row in reader
    ]
```

**Características:**
- Formato tabular — uma linha por produto, separado por vírgula
- As chaves aparecem **uma única vez** (cabeçalho), tornando o arquivo menor que JSON para dados planos
- Compatível com Excel, Google Sheets e qualquer ferramenta de dados
- **Desvantagem:** todos os valores são lidos como `str` — é necessário converter tipos manualmente ao carregar

**Trecho do arquivo gerado:**
```
id,title,price,sold_quantity,available_quantity
1,Notebook Dell Inspiron 15,3499.99,150,25
2,Notebook Lenovo IdeaPad 3,2899.0,320,40
...
```

---

### 3. Pickle — `pickle.dump` / `pickle.load`

```python
# Salvar
with open("dados.pkl", "wb") as f:
    pickle.dump(products, f)

# Carregar
with open("dados.pkl", "rb") as f:
    data = pickle.load(f)
```

**Características:**
- Formato **binário** nativo do Python
- Serializa qualquer objeto Python diretamente, sem conversão de texto
- Sem necessidade de especificar campos ou converter tipos — tudo é restaurado automaticamente
- **Desvantagem:** não é legível por humanos nem por outras linguagens; use apenas para cache local em Python

**Trecho do arquivo (hexdump):**
```
00000000  80 05 95 a4 0a 00 00 00  00 00 00 5d 94 28 7d 94  |...........].(}.|
00000010  28 8c 02 69 64 94 8c 01  31 94 8c 05 74 69 74 6c  |(...id...1...titl|
...
```

---

## Comparação: tamanho × tempo

O endpoint `GET /comparar` regrava os três arquivos com o mesmo dataset e mede tamanho e tempo de I/O de forma consistente.

### Tabela de resultados típicos (30 produtos)

| Formato | Tamanho | Salvar | Carregar | Legível | Portável |
|---------|---------|--------|----------|---------|----------|
| **JSON**   | ~4,5 KB | ~1,2 ms | ~0,4 ms | ✅ Sim | ✅ Qualquer linguagem |
| **CSV**    | ~1,8 KB | ~0,5 ms | ~0,6 ms | ✅ Sim | ✅ Excel, pandas, R… |
| **Pickle** | ~1,6 KB | ~0,3 ms | ~0,2 ms | ❌ Binário | ❌ Só Python |

> Os valores absolutos variam conforme hardware, SO e carga do sistema, mas a **ordem relativa é consistente**.

---

### 🏆 Quem ganhou em tamanho?

**CSV e Pickle empatam como os menores**, com Pickle levando uma pequena vantagem para datasets maiores.

**Por que JSON é maior?**
Porque as chaves do objeto (`"id"`, `"title"`, `"price"`, `"sold_quantity"`, `"available_quantity"`) são repetidas em **cada linha do array**. Para 30 produtos com 5 campos, isso representa ~150 repetições de chave, adicionando centenas de bytes que não carregam dado algum. Exemplo do overhead:

```json
{"id": "1", "title": "...", "price": 3499.99, "sold_quantity": 150, "available_quantity": 25}
 ↑ 4 bytes  ↑ 7 bytes         ↑ 7 bytes       ↑ 13 bytes            ↑ 18 bytes
                       → essas chaves se repetem 30× = ~150 bytes de overhead só em nomes de campo
```

**Por que CSV é compacto?**
Os nomes dos campos aparecem apenas uma vez no cabeçalho. Cada linha seguinte contém apenas os valores, sem identificação redundante de coluna.

**Por que Pickle é compacto?**
A serialização binária usa um protocolo de bytecode que referencia strings e tipos por ponteiros internos. O Python não precisa escrever `"sold_quantity"` trinta vezes — escreve uma vez e referencia depois.

---

### 🏆 Quem ganhou em velocidade?

**Pickle é consistentemente o mais rápido**, tanto para salvar quanto para carregar.

**Por que Pickle é mais rápido?**
O `pickle.dump` serializa objetos Python diretamente em bytecode, sem passar por:
- Codificação de caracteres (UTF-8 encode/decode)
- Conversão de tipos (`float` → string `"3499.99"` → `float`)
- Parsing de estrutura (tokenização e validação de JSON)

O resultado é menos trabalho de CPU em ambas as direções — especialmente na leitura, onde `json.load` precisa analisar cada caractere da string enquanto `pickle.load` apenas lê bytes e reconstrói objetos nativos.

**Por que CSV é mais lento para carregar do que para salvar?**
Ao salvar, o `DictWriter` apenas serializa linhas de texto. Ao carregar, o `DictReader` entrega tudo como `str` — e o código precisa converter explicitamente `price` para `float` e `sold_quantity`/`available_quantity` para `int` em cada linha, adicionando custo de CPU.

---

### Resumo das decisões de uso

| Cenário | Formato recomendado |
|---------|-------------------|
| Comunicação entre sistemas, APIs REST | **JSON** |
| Exportação para Excel, análise em pandas/R | **CSV** |
| Cache local em Python, máxima velocidade | **Pickle** |
| Auditoria humana, configuração, debug | **JSON** ou **CSV** |
| Dados sensíveis ou multiplataforma | **JSON** (nunca Pickle) |

---

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/status` | Health-check — retorna `{"status": "online"}` |
| `GET` | `/carregar` | Busca até 50 notebooks na API do Mercado Livre (com fallback mock) |
| `POST` | `/salvar/<formato>` | Persiste o dataset em disco (`json`, `csv` ou `pickle`) |
| `GET` | `/offline` | Carrega do disco sem chamar a API externa |
| `GET` | `/comparar` | Métricas de tamanho (KB) e tempo (ms) dos três formatos |
| `GET` | `/inspecionar?formato=<fmt>` | Trecho legível (texto) ou hexdump (binário) do arquivo |

### Detalhes dos payloads

**`POST /salvar/<formato>`**
```json
// Request body
{ "products": [ { "id": "1", "title": "...", "price": 3499.99, "sold_quantity": 150, "available_quantity": 25 } ] }

// Response
{ "success": true, "message": "JSON salvo em dados.json (4.52 KB) em 1.23 ms.", "format": "json" }
```

**`GET /comparar`**
```json
{
  "rows": [
    { "format": "JSON",   "sizeKb": 4.52, "saveMs": 1.23, "loadMs": 0.41 },
    { "format": "CSV",    "sizeKb": 1.84, "saveMs": 0.51, "loadMs": 0.63 },
    { "format": "Pickle", "sizeKb": 1.61, "saveMs": 0.29, "loadMs": 0.18 }
  ]
}
```

**`GET /inspecionar?formato=pickle`**
```json
{
  "format": "pickle",
  "content": "00000000  80 05 95 a4 0a ...",
  "binary": true
}
```

---

## Como rodar

### Backend (Python/Flask)

```bash
# 1. Clonar o repositório e entrar na pasta do backend
cd backend

# 2. Criar e ativar ambiente virtual
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Iniciar o servidor
python app.py
```

O servidor sobe em `http://localhost:5000`.

**Dependências:**

| Pacote | Versão | Uso |
|--------|--------|-----|
| `flask` | 3.1.0 | Framework web |
| `flask-cors` | 5.0.1 | Habilita CORS para o frontend Next.js |
| `requests` | 2.32.3 | Chamadas à API do Mercado Livre |

### Frontend (Next.js)

```bash
# Na pasta do frontend
pnpm install     # ou npm install / yarn

# Configurar a URL do backend (opcional — padrão já é localhost:5000)
echo "NEXT_PUBLIC_PERSISTENCE_API_URL=http://localhost:5000" > .env.local

pnpm dev
```

Frontend sobe em `http://localhost:3000`.

---

## Estrutura do projeto

```
backend/
├── app.py               # Servidor Flask — todos os endpoints e helpers de I/O
├── requirements.txt     # Dependências Python
├── dados/               # Criado automaticamente ao primeiro salvamento
│   ├── dados.json       # Dataset em JSON
│   ├── dados.csv        # Dataset em CSV
│   └── dados.pkl        # Dataset em Pickle (binário)
└── README.md

frontend/
├── services/
│   └── persistenceService.ts   # Camada HTTP — todas as chamadas ao backend
├── hooks/
│   └── usePersistence.ts       # Estado e lógica de persistência (React Hook)
└── components/
    └── PersistenceSection.tsx  # UI da aba de persistência
```

---

## Robustez e tratamento de erros

- **`with open(...)`** em todos os arquivos garante fechamento mesmo em caso de exceção
- **`encoding="utf-8"`** explícito em todos os arquivos de texto — sem surpresas em Windows
- **`/offline`** tenta os formatos em ordem de prioridade (JSON → CSV → Pickle) e retorna `404` apenas se nenhum existir
- **Fallback mock** na rota `/carregar`: se a API do Mercado Livre falhar por qualquer motivo (timeout, erro HTTP, JSON vazio), 30 produtos pré-definidos são retornados com flag `"origin": "API Mercado Livre (mock)"`
- **`PersistenceError`** no frontend: erros HTTP são convertidos em tipos semânticos (`not_found`, `server_unavailable`, `save_failed`, etc.) com mensagens amigáveis, desacoplando a UI dos detalhes de HTTP
- **CORS** habilitado via `flask-cors` para permitir chamadas do frontend em porta diferente sem bloqueio do browser

---
## Licença

Trabalho acadêmico — uso livre para fins de estudo.
