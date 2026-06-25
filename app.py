"""
Backend de Persistência — Trabalho Final
========================================
Endpoints:
  GET  /carregar          → busca da API do Mercado Livre e retorna os dados
  POST /salvar/<formato>  → grava em disco: dados.json / dados.csv / dados.pkl
  GET  /offline           → lê do arquivo mais recente (sem internet)
  GET  /comparar          → tamanho (KB) + tempo de salvar/carregar de cada formato
  GET  /inspecionar       → trecho legível (texto) ou hexdump (binário)
  GET  /status            → health-check do servidor

Formatos suportados:
  Texto  → JSON  (json.dump / json.load)
  Texto  → CSV   (csv.DictWriter / csv.DictReader)
  Binário → Pickle (pickle.dump / pickle.load)
"""

import csv
import io
import json
import os
import pickle
import struct
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # permite chamadas do frontend Next.js em porta diferente

# ─── Diretório de dados ───────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "dados"
DATA_DIR.mkdir(exist_ok=True)

JSON_PATH   = DATA_DIR / "dados.json"
CSV_PATH    = DATA_DIR / "dados.csv"
PICKLE_PATH = DATA_DIR / "dados.pkl"

# ─── API do Mercado Livre ─────────────────────────────────────────────────────
ML_API = "https://api.mercadolivre.com.br/sites/MLB/search"

# Dados mock usados quando a API falhar
MOCK_PRODUCTS = [
    {"id": "1",  "title": "Notebook Dell Inspiron 15",     "price": 3499.99, "sold_quantity": 150, "available_quantity": 25},
    {"id": "2",  "title": "Notebook Lenovo IdeaPad 3",     "price": 2899.00, "sold_quantity": 320, "available_quantity": 40},
    {"id": "3",  "title": "MacBook Air M2",                "price": 9999.00, "sold_quantity": 85,  "available_quantity": 12},
    {"id": "4",  "title": "Notebook ASUS Vivobook",        "price": 2599.99, "sold_quantity": 200, "available_quantity": 55},
    {"id": "5",  "title": "HP Pavilion Gaming",            "price": 4299.00, "sold_quantity": 110, "available_quantity": 18},
    {"id": "6",  "title": "Acer Aspire 5",                 "price": 2199.00, "sold_quantity": 450, "available_quantity": 80},
    {"id": "7",  "title": "Samsung Book",                  "price": 2799.99, "sold_quantity": 95,  "available_quantity": 30},
    {"id": "8",  "title": "Notebook Positivo Motion",      "price": 1599.00, "sold_quantity": 600, "available_quantity": 100},
    {"id": "9",  "title": "MacBook Pro 14 M3",             "price": 18999.00,"sold_quantity": 42,  "available_quantity": 8},
    {"id": "10", "title": "Notebook Vaio FE14",            "price": 3199.00, "sold_quantity": 75,  "available_quantity": 22},
    {"id": "11", "title": "Dell G15 Gaming",               "price": 5499.00, "sold_quantity": 130, "available_quantity": 15},
    {"id": "12", "title": "Lenovo Legion 5",               "price": 6999.00, "sold_quantity": 88,  "available_quantity": 10},
    {"id": "13", "title": "ASUS ROG Strix",                "price": 8499.00, "sold_quantity": 55,  "available_quantity": 7},
    {"id": "14", "title": "HP Envy x360",                  "price": 4599.00, "sold_quantity": 140, "available_quantity": 28},
    {"id": "15", "title": "Acer Nitro 5",                  "price": 4199.00, "sold_quantity": 220, "available_quantity": 35},
    {"id": "16", "title": "MSI Modern 14",                 "price": 3799.00, "sold_quantity": 65,  "available_quantity": 20},
    {"id": "17", "title": "Notebook Multilaser Legacy",    "price": 1299.00, "sold_quantity": 800, "available_quantity": 150},
    {"id": "18", "title": "ThinkPad E14",                  "price": 4899.00, "sold_quantity": 95,  "available_quantity": 14},
    {"id": "19", "title": "MacBook Pro 16 M3 Max",         "price": 29999.00,"sold_quantity": 18,  "available_quantity": 3},
    {"id": "20", "title": "Surface Laptop 5",              "price": 7499.00, "sold_quantity": 48,  "available_quantity": 9},
    {"id": "21", "title": "Notebook Compaq Presario",      "price": 1899.00, "sold_quantity": 350, "available_quantity": 60},
    {"id": "22", "title": "ASUS Zenbook 14",               "price": 5999.00, "sold_quantity": 72,  "available_quantity": 16},
    {"id": "23", "title": "HP Victus Gaming",              "price": 4799.00, "sold_quantity": 105, "available_quantity": 19},
    {"id": "24", "title": "Lenovo Yoga 7i",                "price": 5499.00, "sold_quantity": 62,  "available_quantity": 11},
    {"id": "25", "title": "Dell XPS 13",                   "price": 8999.00, "sold_quantity": 38,  "available_quantity": 6},
    {"id": "26", "title": "Samsung Galaxy Book3",          "price": 4299.00, "sold_quantity": 82,  "available_quantity": 17},
    {"id": "27", "title": "Acer Swift 3",                  "price": 3599.00, "sold_quantity": 115, "available_quantity": 24},
    {"id": "28", "title": "HP 250 G9",                     "price": 2299.00, "sold_quantity": 280, "available_quantity": 45},
    {"id": "29", "title": "Lenovo V15",                    "price": 2099.00, "sold_quantity": 195, "available_quantity": 38},
    {"id": "30", "title": "ASUS TUF Gaming",               "price": 5299.00, "sold_quantity": 160, "available_quantity": 21},
]


# ─── Helpers de I/O ──────────────────────────────────────────────────────────

def _save_json(products: list[dict]) -> float:
    """Grava em JSON e retorna o tempo em ms."""
    t0 = time.perf_counter()
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    return round((time.perf_counter() - t0) * 1000, 2)


def _load_json() -> tuple[list[dict], float]:
    """Lê do JSON e retorna (produtos, tempo_ms)."""
    t0 = time.perf_counter()
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data, round((time.perf_counter() - t0) * 1000, 2)


def _save_csv(products: list[dict]) -> float:
    """Grava em CSV e retorna o tempo em ms."""
    campos = ["id", "title", "price", "sold_quantity", "available_quantity"]
    t0 = time.perf_counter()
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(products)
    return round((time.perf_counter() - t0) * 1000, 2)


def _load_csv() -> tuple[list[dict], float]:
    """Lê do CSV e retorna (produtos, tempo_ms)."""
    t0 = time.perf_counter()
    with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        data = []
        for row in reader:
            data.append({
                "id": row["id"],
                "title": row["title"],
                "price": float(row["price"]),
                "sold_quantity": int(row["sold_quantity"]),
                "available_quantity": int(row["available_quantity"]),
            })
    return data, round((time.perf_counter() - t0) * 1000, 2)


def _save_pickle(products: list[dict]) -> float:
    """Grava em Pickle e retorna o tempo em ms."""
    t0 = time.perf_counter()
    with open(PICKLE_PATH, "wb") as f:
        pickle.dump(products, f)
    return round((time.perf_counter() - t0) * 1000, 2)


def _load_pickle() -> tuple[list[dict], float]:
    """Lê do Pickle e retorna (produtos, tempo_ms)."""
    t0 = time.perf_counter()
    with open(PICKLE_PATH, "rb") as f:
        data = pickle.load(f)
    return data, round((time.perf_counter() - t0) * 1000, 2)


def _hexdump(path: Path, max_bytes: int = 256) -> str:
    """Gera um hexdump legível dos primeiros `max_bytes` do arquivo."""
    with open(path, "rb") as f:
        raw = f.read(max_bytes)

    lines = []
    for i in range(0, len(raw), 16):
        chunk = raw[i : i + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08x}  {hex_part:<47}  |{ascii_part}|")

    truncated = len(raw) == max_bytes
    if truncated:
        lines.append(f"\n... (exibindo apenas os primeiros {max_bytes} bytes)")
    return "\n".join(lines)


def _size_kb(path: Path) -> float:
    """Retorna o tamanho do arquivo em KB com 2 casas decimais."""
    if not path.exists():
        return 0.0
    return round(path.stat().st_size / 1024, 2)


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.route("/status")
def status():
    """Health-check — usado pelo frontend para exibir o badge Online/Offline."""
    return jsonify({"status": "online"})


@app.route("/carregar")
def carregar():
    """
    Busca até 50 produtos da API do Mercado Livre (notebooks) e retorna ao
    frontend. Caso a API falhe, usa os dados mock para garantir funcionamento
    offline durante apresentações.
    """
    products = []
    origin = "API Mercado Livre"

    try:
        resp = requests.get(
            ML_API,
            params={"q": "notebook", "limit": 50},
            timeout=8,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        products = [
            {
                "id": str(item.get("id", "")),
                "title": item.get("title", ""),
                "price": float(item.get("price", 0)),
                "sold_quantity": int(item.get("sold_quantity", 0)),
                "available_quantity": int(item.get("available_quantity", 0)),
            }
            for item in results
        ]
        if not products:
            raise ValueError("API retornou lista vazia")
    except Exception as exc:
        app.logger.warning("API Mercado Livre indisponível: %s — usando mock", exc)
        products = MOCK_PRODUCTS
        origin = "API Mercado Livre (mock)"

    return jsonify(
        {
            "products": products,
            "origin": origin,
            "count": len(products),
            "status": "online",
        }
    )


@app.route("/salvar/<formato>", methods=["POST"])
def salvar(formato: str):
    """
    Recebe { "products": [...] } e grava em disco no formato solicitado.
    Formatos aceitos: json | csv | pickle
    """
    body = request.get_json(silent=True) or {}
    products = body.get("products", [])

    if not products:
        return jsonify({"success": False, "message": "Nenhum produto recebido.", "format": formato}), 400

    try:
        if formato == "json":
            ms = _save_json(products)
            msg = f"JSON salvo em {JSON_PATH.name} ({_size_kb(JSON_PATH)} KB) em {ms} ms."
        elif formato == "csv":
            ms = _save_csv(products)
            msg = f"CSV salvo em {CSV_PATH.name} ({_size_kb(CSV_PATH)} KB) em {ms} ms."
        elif formato == "pickle":
            ms = _save_pickle(products)
            msg = f"Pickle salvo em {PICKLE_PATH.name} ({_size_kb(PICKLE_PATH)} KB) em {ms} ms."
        else:
            return jsonify({"success": False, "message": f"Formato desconhecido: {formato}", "format": formato}), 400

        return jsonify({"success": True, "message": msg, "format": formato})

    except Exception as exc:
        return jsonify({"success": False, "message": str(exc), "format": formato}), 500


@app.route("/offline")
def offline():
    """
    Carrega dados do disco sem chamar a API.
    Prioridade: JSON → CSV → Pickle.
    Retorna 404 se nenhum arquivo existir ainda.
    """
    # Tenta cada formato na ordem de prioridade
    loaders = [
        (JSON_PATH,   _load_json,   "Arquivo JSON"),
        (CSV_PATH,    _load_csv,    "Arquivo CSV"),
        (PICKLE_PATH, _load_pickle, "Arquivo Pickle"),
    ]

    for path, loader, origin_label in loaders:
        if path.exists():
            try:
                products, _ = loader()
                return jsonify(
                    {
                        "products": products,
                        "origin": origin_label,
                        "count": len(products),
                        "status": "online",
                    }
                )
            except Exception as exc:
                app.logger.warning("Erro ao ler %s: %s", path, exc)
                continue  # tenta o próximo formato

    return jsonify({"error": "Nenhum arquivo salvo encontrado."}), 404


@app.route("/comparar")
def comparar():
    """
    Para cada formato existente em disco, mede:
      - tamanho do arquivo (KB)
      - tempo de salvar (ms) — regrava o arquivo atual para medir
      - tempo de carregar (ms)
    Formatos sem arquivo retornam zeros.
    """
    # Carrega o dataset de referência (prefere JSON, depois CSV, depois Pickle, depois mock)
    reference: list[dict] = []
    for path, loader in [(JSON_PATH, _load_json), (CSV_PATH, _load_csv), (PICKLE_PATH, _load_pickle)]:
        if path.exists():
            try:
                reference, _ = loader()
                break
            except Exception:
                continue
    if not reference:
        reference = MOCK_PRODUCTS

    rows = []

    # ── JSON ──────────────────────────────────────────────────────────────────
    save_ms_json = _save_json(reference)
    _, load_ms_json = _load_json()
    rows.append({
        "format": "JSON",
        "sizeKb": _size_kb(JSON_PATH),
        "saveMs": save_ms_json,
        "loadMs": load_ms_json,
    })

    # ── CSV ───────────────────────────────────────────────────────────────────
    save_ms_csv = _save_csv(reference)
    _, load_ms_csv = _load_csv()
    rows.append({
        "format": "CSV",
        "sizeKb": _size_kb(CSV_PATH),
        "saveMs": save_ms_csv,
        "loadMs": load_ms_csv,
    })

    # ── Pickle ────────────────────────────────────────────────────────────────
    save_ms_pkl = _save_pickle(reference)
    _, load_ms_pkl = _load_pickle()
    rows.append({
        "format": "Pickle",
        "sizeKb": _size_kb(PICKLE_PATH),
        "saveMs": save_ms_pkl,
        "loadMs": load_ms_pkl,
    })

    return jsonify({"rows": rows})


@app.route("/inspecionar")
def inspecionar():
    """
    Retorna um trecho do arquivo para visualização didática:
      - JSON / CSV → primeiras linhas como texto (legível)
      - Pickle     → hexdump (ilegível = binário)
    Query param: ?formato=json|csv|pickle
    """
    formato = request.args.get("formato", "json").lower()

    if formato == "json":
        if not JSON_PATH.exists():
            return jsonify({"error": "Arquivo JSON não encontrado."}), 404
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            linhas = f.readlines()[:40]
        content = "".join(linhas)
        return jsonify({"format": "json", "content": content, "binary": False})

    elif formato == "csv":
        if not CSV_PATH.exists():
            return jsonify({"error": "Arquivo CSV não encontrado."}), 404
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            linhas = f.readlines()[:20]
        content = "".join(linhas)
        return jsonify({"format": "csv", "content": content, "binary": False})

    elif formato == "pickle":
        if not PICKLE_PATH.exists():
            return jsonify({"error": "Arquivo Pickle não encontrado."}), 404
        content = _hexdump(PICKLE_PATH)
        return jsonify({"format": "pickle", "content": content, "binary": True})

    else:
        return jsonify({"error": f"Formato desconhecido: {formato}"}), 400


# ─── Inicialização ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
