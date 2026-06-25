# Visualizador de Algoritmos + Persistência de Dados

Projeto full-stack acadêmico que combina **visualização interativa de algoritmos de ordenação e busca** com uma camada de **persistência de dados em múltiplos formatos**, consumindo a API pública do Mercado Livre.

---

## Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [API Utilizada](#api-utilizada)
- [Formatos de Persistência Implementados](#formatos-de-persistência-implementados)
- [Comparação: Tamanho × Tempo](#comparação-tamanho--tempo)
- [Por que cada formato se comporta assim?](#por-que-cada-formato-se-comporta-assim)
- [Conclusão — Qual formato ganhou?](#conclusão--qual-formato-ganhou)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Como Rodar](#como-rodar)
- [Endpoints da API (Backend)](#endpoints-da-api-backend)
- [Tecnologias](#tecnologias)

---

## Visão Geral

O projeto é dividido em duas partes independentes que se comunicam via HTTP:

| Parte | Tecnologia | Porta padrão |
|---|---|---|
| **Frontend** | Next.js 16 + React 19 + TypeScript | `3000` |
| **Backend** | Python 3 + Flask | `5000` |

O frontend exibe visualizações animadas de algoritmos clássicos (Bubble Sort, Merge Sort, Quick Sort, Heap Sort, Insertion Sort, Selection Sort, Busca Linear e Busca Binária) e uma aba dedicada à persistência, onde o usuário pode:

- Buscar produtos de notebooks na API do Mercado Livre
- Salvar o dataset em disco em qualquer um dos quatro formatos
- Comparar tamanho de arquivo e tempo de I/O entre os formatos
- Inspecionar o conteúdo bruto de cada arquivo (texto legível ou hexdump binário)
- Recarregar os dados do disco sem conexão com a internet (modo offline)

---

## Arquitetura

```
┌──────────────────────────────────────────┐
│         Frontend — Next.js :3000         │
│                                          │
│  ┌─────────────┐   ┌──────────────────┐  │
│  │ Algoritmos  │   │ PersistenceSection│  │
│  │ (Sort/Search│   │  usePersistence  │  │
│  │  visualizer)│   │  persistenceSvc  │  │
│  └─────────────┘   └────────┬─────────┘  │
└───────────────────────────── │ ──────────┘
                               │ fetch (HTTP)
┌──────────────────────────────▼──────────┐
│          Backend — Flask :5000          │
│                                         │
│  GET  /carregar   →  Mercado Livre API  │
│  POST /salvar/<fmt>  →  Disco           │
│  GET  /offline    →  Disco              │
│  GET  /comparar   →  Métricas I/O       │
│  GET  /inspecionar →  Preview arquivo   │
│  GET  /status     →  Health-check       │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │          dados/                  │   │
│  │  dados.json  dados.csv           │   │
│  │  dados.pkl   dados.bin           │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
            │
            │ requests
            ▼
┌─────────────────────────────┐
│  API Mercado Livre (pública) │
│  /sites/MLB/search?q=notebook│
└─────────────────────────────┘
```

---

## API Utilizada

### Mercado Livre — API Pública

**Base URL:** `https://api.mercadolivre.com.br`

**Endpoint consumido:**
```
GET /sites/MLB/search?q=notebook&limit=50
```

**Autenticação:** Nenhuma. O endpoint de busca é público e não exige token.

**Campos extraídos de cada item:**

| Campo retornado pela API | Tipo | Descrição |
|---|---|---|
| `id` | `string` | Identificador único do produto no ML |
| `title` | `string` | Nome completo do produto |
| `price` | `float` | Preço atual em BRL |
| `sold_quantity` | `int` | Total de unidades vendidas |
| `available_quantity` | `int` | Estoque disponível |

**Resposta esperada (resumida):**
```json
{
  "results": [
    {
      "id": "MLB123456789",
      "title": "Notebook Dell Inspiron 15",
      "price": 3499.99,
      "sold_quantity": 150,
      "available_quantity": 25
    }
  ]
}
```

**Fallback offline:** Caso a API esteja indisponível (timeout de 8 s ou erro HTTP), o backend retorna automaticamente um dataset mock com 30 produtos pré-definidos, garantindo funcionamento completo em ambientes sem internet.

---

## Formatos de Persistência Implementados

O backend implementa quatro formatos de serialização, agrupados em **texto** e **binário**:

### 1. JSON — `json.dump` / `json.load`

```python
with open("dados.json", "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)
```

- Formato de texto estruturado, amplamente adotado em APIs REST
- Hierárquico e completamente legível em qualquer editor
- Suporta os tipos Python nativos: `str`, `float`, `int`, `list`, `dict`
- **Maior arquivo** do grupo: as chaves (`"id"`, `"title"`, `"price"`, etc.) são repetidas em cada objeto da lista

**Exemplo de saída:**
```json
[
  {
    "id": "MLB123",
    "title": "Notebook Dell Inspiron 15",
    "price": 3499.99,
    "sold_quantity": 150,
    "available_quantity": 25
  }
]
```

---

### 2. CSV — `csv.DictWriter` / `csv.DictReader`

```python
writer = csv.DictWriter(f, fieldnames=["id","title","price","sold_quantity","available_quantity"])
writer.writeheader()
writer.writerows(products)
```

- Formato tabular, linha por linha, separado por vírgula
- Compatível com Excel, LibreOffice Calc e qualquer ferramenta de dados
- **Mais compacto que JSON** para dados tabulares simples porque as chaves aparecem apenas uma vez (no cabeçalho), não se repetem em cada linha
- Requer conversão de tipos na leitura (`float(row["price"])`, `int(row["sold_quantity"])`)

**Exemplo de saída:**
```
id,title,price,sold_quantity,available_quantity
MLB123,Notebook Dell Inspiron 15,3499.99,150,25
MLB124,Notebook Lenovo IdeaPad 3,2899.0,320,40
```

---

### 3. Pickle — `pickle.dump` / `pickle.load`

```python
with open("dados.pkl", "wb") as f:
    pickle.dump(products, f)
```

- Formato **binário nativo do Python**
- Serializa qualquer objeto Python sem configuração adicional
- **Mais rápido em I/O**: não há conversão de texto, encoding ou parsing de estrutura
- **Não portável**: arquivos `.pkl` só podem ser lidos por Python; diferentes versões do Python podem gerar arquivos incompatíveis

**Trecho hexdump (ilegível diretamente):**
```
00000000  80 05 95 2c 04 00 00 00  00 00 00 5d 94 28 7d 94  |...,.........].(}.|
00000010  28 8c 02 69 64 94 8c 03  31 32 33 94 8c 05 74 69  |(..id...123...ti|
```

---

### 4. Struct Binário — `struct.pack` / `struct.unpack`

```python
import struct

HEADER = struct.Struct(">I")       # número de produtos (big-endian uint32)
RECORD = struct.Struct(">IffII")   # id_num, price, sold_qty, avail_qty

with open("dados.bin", "wb") as f:
    f.write(HEADER.pack(len(products)))
    for p in products:
        title_bytes = p["title"].encode("utf-8")
        f.write(RECORD.pack(
            int(p["id"]) if p["id"].isdigit() else 0,
            float(p["price"]),
            int(p["sold_quantity"]),
            int(p["available_quantity"]),
        ))
        f.write(struct.pack(">H", len(title_bytes)))  # 2 bytes para tamanho do título
        f.write(title_bytes)
```

- Formato **binário de baixo nível**, com tamanho de registro fixo para campos numéricos
- Produz o **menor arquivo** para dados predominantemente numéricos
- Controle total sobre o layout de bytes (endianness, precisão dos floats)
- Leitura é mais rápida que JSON/CSV por não precisar de parsing, mas mais lenta que Pickle por precisar desempacotar campo a campo
- **Não portável** entre linguagens sem documentação explícita do schema

---

## Comparação: Tamanho × Tempo

Os valores abaixo foram medidos com o dataset de 30 produtos (valores representativos — variam conforme hardware e SO):

| Formato | Tamanho (KB) | Tempo salvar (ms) | Tempo carregar (ms) |
|---|---|---|---|
| **JSON** | ~5.5 | ~0.8 | ~0.6 |
| **CSV** | ~2.2 | ~0.5 | ~0.7 |
| **Pickle** | ~2.8 | ~0.3 | ~0.2 |
| **Struct Binário** | ~1.8 | ~0.6 | ~0.5 |

> Tempos medidos com `time.perf_counter()` diretamente no backend Flask. Em datasets maiores (centenas de milhares de registros), as diferenças tornam-se muito mais pronunciadas.

---

## Por que cada formato se comporta assim?

### Por que JSON é o maior?

Cada objeto da lista repete todas as chaves:

```
{"id": "1", "title": "...", "price": 3499.99, "sold_quantity": 150, "available_quantity": 25}
{"id": "2", "title": "...", "price": 2899.00, "sold_quantity": 320, "available_quantity": 40}
```

Para 30 produtos com 5 campos, as chaves sozinhas somam cerca de **1.5 KB extras** que não carregam nenhum dado real. Além disso, números são serializados como texto (`3499.99` → 7 bytes), enquanto em binário um `float32` ocupa sempre 4 bytes.

### Por que CSV é mais compacto que JSON?

As chaves aparecem **uma única vez** no cabeçalho. Cada linha seguinte contém apenas os valores, separados por vírgula — sem delimitadores de objeto, sem aspas obrigatórias em campos numéricos.

### Por que Pickle é o mais rápido?

Pickle serializa o grafo de objetos Python diretamente em bytecode, sem nenhuma conversão de texto. Não há:
- encoding/decoding UTF-8 por caractere
- tokenização de JSON (abrir `{`, ler chave, ler `:`, ler valor...)
- conversão de strings para `float`/`int` na leitura

O resultado é **menos instruções de CPU** em ambas as direções, especialmente na leitura.

### Por que Struct Binário é o menor mas não o mais rápido?

O Struct produz o arquivo mais enxuto porque cada campo numérico ocupa exatamente o espaço que seu tipo exige (`float32` = 4 bytes, `uint32` = 4 bytes). Porém, a leitura exige um loop explícito que chama `struct.unpack` campo a campo para cada produto, o que é mais lento do que o `pickle.load`, que desserializa o objeto inteiro de uma vez. O Struct brilha em cenários de **acesso aleatório** — saltar direto para o registro N sem ler o arquivo inteiro — algo que Pickle não suporta.

---

## Conclusão — Qual formato ganhou?

Não existe um vencedor absoluto; cada formato é ótimo para um cenário diferente:

| Objetivo | Formato recomendado | Motivo |
|---|---|---|
| **Menor arquivo em disco** | Struct Binário | Layout fixo por campo, sem overhead de chaves ou delimitadores |
| **I/O mais rápido (salvar e carregar)** | Pickle | Serialização direta do grafo Python, sem parsing |
| **Melhor portabilidade** | JSON | Qualquer linguagem, qualquer editor, qualquer API REST lê JSON |
| **Compatibilidade com planilhas/Excel** | CSV | Aberto diretamente no Excel, LibreOffice, pandas |
| **Controle fino de bytes / acesso aleatório** | Struct Binário | Permite calcular o offset do registro N e pular direto |
| **Legibilidade humana** | JSON ou CSV | Ambos são editáveis em qualquer editor de texto |

**Resumo executivo:**
- Use **JSON** quando os dados precisam cruzar fronteiras (entre sistemas, linguagens ou APIs).
- Use **CSV** quando a audiência final é uma planilha ou ferramenta de análise.
- Use **Pickle** quando velocidade de cache importa e o consumidor é sempre Python.
- Use **Struct Binário** quando espaço em disco é crítico ou você precisa de acesso aleatório a registros.

---

## Estrutura do Projeto

```
projeto/
│
├── backend/                        # Servidor Flask (Python)
│   ├── app.py                      # Todos os endpoints e helpers de I/O
│   ├── requirements.txt            # Dependências Python
│   └── dados/                      # Criado automaticamente ao salvar
│       ├── dados.json
│       ├── dados.csv
│       ├── dados.pkl
│       └── dados.bin
│
└── frontend/                       # App Next.js (TypeScript)
    ├── app/
    │   ├── layout.tsx
    │   └── page.tsx
    ├── algorithms/                 # Implementações puras dos algoritmos
    │   ├── bubbleSort.ts
    │   ├── mergeSort.ts
    │   ├── quickSort.ts
    │   ├── heapSort.ts
    │   ├── insertionSort.ts
    │   ├── selectionSort.ts
    │   ├── binarySearch.ts
    │   ├── linearSearch.ts
    │   └── types.ts
    ├── components/
    │   ├── PersistenceSection.tsx  # Aba de persistência
    │   ├── SortingVisualizer.tsx
    │   ├── SearchSection.tsx
    │   ├── PerformanceComparison.tsx
    │   └── ui/                     # Componentes shadcn/ui
    ├── hooks/
    │   └── usePersistence.ts       # Hook que gerencia estado de persistência
    └── services/
        ├── api.ts
        └── persistenceService.ts   # Todas as chamadas HTTP ao backend
```

---

## Como Rodar

### Pré-requisitos

- Python 3.10+
- Node.js 18+ e pnpm (ou npm/yarn)

---

### Backend

```bash
cd backend

# 1. Criar e ativar ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Iniciar o servidor
python app.py
```

O servidor sobe em `http://localhost:5000`.

**Dependências Python (`requirements.txt`):**
```
flask==3.1.0
flask-cors==5.0.1
requests==2.32.3
```

> Os módulos `json`, `csv`, `pickle` e `struct` são da biblioteca padrão do Python — nenhuma instalação adicional necessária.

---

### Frontend

```bash
cd frontend

# 1. Instalar dependências
pnpm install          # ou: npm install

# 2. (Opcional) Configurar a URL do backend
# Crie um arquivo .env.local com:
# NEXT_PUBLIC_PERSISTENCE_API_URL=http://localhost:5000

# 3. Iniciar em modo desenvolvimento
pnpm dev
```

Acesse `http://localhost:3000`.

Para build de produção:
```bash
pnpm build && pnpm start
```

---

## Endpoints da API (Backend)

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/status` | Health-check. Retorna `{"status": "online"}` |
| `GET` | `/carregar` | Busca até 50 notebooks na API do Mercado Livre. Fallback para mock se indisponível. |
| `POST` | `/salvar/<formato>` | Persiste `{ "products": [...] }` em disco. Aceita: `json`, `csv`, `pickle`, `binary` |
| `GET` | `/offline` | Carrega do disco sem chamar a API. Prioridade: JSON → CSV → Pickle → Struct |
| `GET` | `/comparar` | Retorna tamanho (KB), tempo de salvar (ms) e tempo de carregar (ms) por formato |
| `GET` | `/inspecionar?formato=<fmt>` | Trecho legível (JSON/CSV) ou hexdump (Pickle/Struct) do arquivo salvo |

**Exemplo de resposta de `/comparar`:**
```json
{
  "rows": [
    { "format": "JSON",   "sizeKb": 5.52, "saveMs": 0.82, "loadMs": 0.61 },
    { "format": "CSV",    "sizeKb": 2.18, "saveMs": 0.51, "loadMs": 0.69 },
    { "format": "Pickle", "sizeKb": 2.79, "saveMs": 0.31, "loadMs": 0.19 },
    { "format": "Binary", "sizeKb": 1.83, "saveMs": 0.63, "loadMs": 0.52 }
  ]
}
```

---

## Tecnologias

### Backend
| Pacote | Versão | Uso |
|---|---|---|
| Python | 3.10+ | Linguagem |
| Flask | 3.1.0 | Servidor HTTP |
| flask-cors | 5.0.1 | Habilita CORS para o frontend |
| requests | 2.32.3 | Consumo da API do Mercado Livre |
| json | stdlib | Serialização JSON |
| csv | stdlib | Serialização CSV |
| pickle | stdlib | Serialização binária Python |
| struct | stdlib | Serialização binária de baixo nível |

### Frontend
| Pacote | Versão | Uso |
|---|---|---|
| Next.js | 16.2.6 | Framework React (App Router) |
| React | 19 | UI |
| TypeScript | 5.7.3 | Tipagem estática |
| Tailwind CSS | 4.2.0 | Estilização |
| shadcn/ui + Radix UI | — | Componentes acessíveis |
| Recharts | 2.15.0 | Gráficos de comparação |
| Lucide React | 0.564.0 | Ícones |

---

## Licença

Projeto acadêmico. Uso livre para fins educacionais.
