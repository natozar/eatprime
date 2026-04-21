"""
EatPrime · Agente Prospector (CLI, Gemini)
------------------------------------------
Descobre restaurantes premium novos em Ribeirão Preto/SP usando:
  1. Google Places API (New) — Text Search com várias queries curadas
  2. Filtros de qualidade: rating >= 4.3, userRatingCount >= 150, priceLevel >= 3
  3. Gemini (gratuito via AI Studio) — classifica `tag`, sugere `prato`, escreve `desc`

Saída: candidatos.json (pra você revisar manualmente antes de publicar).

Uso:
    export GOOGLE_PLACES_API_KEY="AIza..."
    export GEMINI_API_KEY="AIza..."          # https://aistudio.google.com/app/apikey
    python agente_prospector.py
    python agente_prospector.py --max 20 --min-rating 4.4

IMPORTANTE:
  - Não baixa fotos do Google (ToS). Usa placeholder Unsplash/Pexels.
  - Não publica nada. Apenas gera candidatos.json pra revisão.
  - Pula restaurantes já presentes em restaurantes_dados.json (match por nome).
"""

import os
import sys
import json
import time
import argparse
import datetime
from pathlib import Path

# Windows: força UTF-8 no stdout/stderr pra não travar em caracteres como ≥, ·, ★
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import requests
except ImportError:
    print("[ERRO] pip install requests")
    sys.exit(1)


# =============================================================================
# CONFIG
# =============================================================================

BASE_DIR = Path(__file__).parent
ARQUIVO_EXISTENTES = BASE_DIR / "restaurantes_dados.json"
ARQUIVO_SAIDA = BASE_DIR / "candidatos.json"


ARQUIVO_ENV = BASE_DIR / ".env.local"


def carregar_env_local():
    """Lê .env.local (já no .gitignore) e injeta em os.environ."""
    if not ARQUIVO_ENV.exists():
        return
    for linha in ARQUIVO_ENV.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if chave and chave not in os.environ:
            os.environ[chave] = valor


def salvar_em_env_local(pares):
    """Grava/atualiza chaves no .env.local. Mantém chaves existentes."""
    existente = {}
    if ARQUIVO_ENV.exists():
        for linha in ARQUIVO_ENV.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, v = linha.split("=", 1)
            existente[k.strip()] = v.strip().strip('"').strip("'")
    existente.update(pares)
    linhas = ["# EatPrime — chaves locais (gerado pelo agente_prospector). NÃO comitar."]
    for k, v in existente.items():
        linhas.append(f"{k}={v}")
    ARQUIVO_ENV.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def pedir_e_salvar_chaves():
    """Se faltar alguma chave em os.environ, pergunta no terminal e salva."""
    novos = {}
    if not os.environ.get("GEMINI_API_KEY"):
        print("[·] GEMINI_API_KEY não encontrada.")
        print("    Pegue em https://aistudio.google.com/app/apikey (gratuita)")
        chave = input("    Cole a chave Gemini aqui: ").strip()
        if chave:
            os.environ["GEMINI_API_KEY"] = chave
            novos["GEMINI_API_KEY"] = chave
    if not os.environ.get("GOOGLE_PLACES_API_KEY"):
        print("[·] GOOGLE_PLACES_API_KEY não encontrada.")
        chave = input("    Cole a chave Google Places aqui: ").strip()
        if chave:
            os.environ["GOOGLE_PLACES_API_KEY"] = chave
            novos["GOOGLE_PLACES_API_KEY"] = chave
    if novos:
        salvar_em_env_local(novos)
        print(f"[✓] Chaves salvas em {ARQUIVO_ENV.name} (ignorado pelo git).")
        print()


carregar_env_local()

PLACES_BASE = "https://places.googleapis.com/v1"
PLACES_SEARCH = f"{PLACES_BASE}/places:searchText"

# Campos pedidos — Places API cobra por FieldMask, então só o necessário
FIELDS_SEARCH = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.rating,places.userRatingCount,places.priceLevel,"
    "places.googleMapsUri,places.internationalPhoneNumber,"
    "places.primaryTypeDisplayName,places.editorialSummary"
)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")  # free tier
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Queries pra ampliar o funil — termos naturais (Places é literal, evita "premium"/"fine dining")
QUERIES_PROSPECCAO = [
    "steakhouse Ribeirão Preto",
    "churrascaria Ribeirão Preto",
    "restaurante italiano Ribeirão Preto",
    "cantina italiana Ribeirão Preto",
    "restaurante de peixe Ribeirão Preto",
    "frutos do mar Ribeirão Preto",
    "restaurante japonês Ribeirão Preto",
    "sushi Ribeirão Preto",
    "restaurante francês Ribeirão Preto",
    "restaurante contemporâneo Ribeirão Preto",
    "costelaria Ribeirão Preto",
    "bistrô Ribeirão Preto",
]


# =============================================================================
# LOG
# =============================================================================

def log(msg, tipo="info"):
    prefixos = {"info": "[·]", "ok": "[✓]", "erro": "[✗]", "aviso": "[!]", "ia": "[🧠]"}
    print(f"{prefixos.get(tipo, '[·]')} {msg}", flush=True)


# =============================================================================
# GOOGLE PLACES
# =============================================================================

def buscar_places(api_key, query, max_resultados=20):
    """Text Search — retorna até N places matching a query."""
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELDS_SEARCH,
    }
    payload = {
        "textQuery": query,
        "languageCode": "pt-BR",
        "regionCode": "BR",
        "maxResultCount": max_resultados,
    }
    r = requests.post(PLACES_SEARCH, headers=headers, json=payload, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Places HTTP {r.status_code}: {r.text[:300]}")
    return r.json().get("places", [])


# Places API retorna priceLevel como enum string; mapeia pra inteiro
MAPA_PRICE_LEVEL = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


def passa_filtro(place, min_rating, min_reviews, min_price):
    rating = place.get("rating") or 0
    reviews = place.get("userRatingCount") or 0
    price_raw = place.get("priceLevel")
    price = MAPA_PRICE_LEVEL.get(price_raw, 0) if isinstance(price_raw, str) else (price_raw or 0)

    if rating < min_rating:
        return False, f"rating {rating} < {min_rating}"
    if reviews < min_reviews:
        return False, f"reviews {reviews} < {min_reviews}"
    # priceLevel é opt-in — se Google não retornar, damos o benefício da dúvida
    if price_raw is not None and price < min_price:
        return False, f"price {price} < {min_price}"

    # Precisa ser em Ribeirão Preto
    endereco = (place.get("formattedAddress") or "").lower()
    if "ribeirão preto" not in endereco and "ribeirao preto" not in endereco:
        return False, "fora de Ribeirão Preto"

    return True, "ok"


# =============================================================================
# GEMINI (classificação e descrição)
# =============================================================================

PROMPT_DESCOBERTA = """Você é um crítico gastronômico especializado em Ribeirão Preto/SP. Conhece profundamente a cena premium da cidade: Jardim Sumaré, Jardim Canadá, Jardim Paulista, Jardim América, Jardim São Luiz, Centro, Vila Seixas, Ribeirânia, Alto da Boa Vista.

Liste restaurantes PREMIUM em Ribeirão Preto que se encaixam na curadoria de um app chamado EatPrime (foco: steakhouses, italianos, peixarias finas, cozinha contemporânea/autoral, francesa, japonesa de alto nível).

CRITÉRIOS DE SELEÇÃO:
- Ticket médio acima da média da cidade (premium, não casual)
- Reconhecimento local (revistas, prêmios, boca a boca de público exigente)
- Qualidade consistente, não rede/franquia
- Preferir casas com identidade própria e chef/proprietário identificável

EXCLUIR da lista (JÁ ESTÃO CATALOGADOS):
{ja_catalogados}

Responda APENAS com JSON válido (sem markdown, sem ```), como uma lista de objetos:

[
  {{
    "nome": "Nome exato do restaurante",
    "area": "Bairro/região",
    "endereco_hint": "Rua e número se souber, senão só bairro",
    "tag": "Carnes|Italiana|Peixes|Japonesa|Francesa|Contemporânea|Brasileira",
    "cuisine": "Tipo específico",
    "prato": "Prato assinatura provável",
    "desc": "Descrição sensorial do prato em 2-4 linhas, PT-BR, linguagem refinada sem clichês",
    "confianca": "alta|média|baixa"
  }}
]

Retorne até 20 restaurantes, ordenados por confiança (mais alta primeiro). Se tiver dúvida se um restaurante existe, marque "baixa". Qualidade importa mais que quantidade — prefira 8 certos a 20 duvidosos."""


PROMPT_GEMINI = """Você é um crítico gastronômico do interior paulista, escrevendo para um app premium de curadoria de restaurantes em Ribeirão Preto/SP chamado EatPrime.

Analise o restaurante abaixo e responda APENAS em JSON válido (sem markdown, sem ```json), com os seguintes campos:

- "tag": uma de ["Carnes", "Italiana", "Peixes", "Japonesa", "Francesa", "Contemporânea", "Brasileira"]
- "cuisine": tipo específico (ex: "Steakhouse", "Trattoria", "Omakase", "Bistrô", "Cozinha de autor")
- "prato": nome de UM prato assinatura provável — escolha algo icônico, sofisticado, coerente com a cozinha (ex: "Ossobuco com Polenta", "Wagyu A5 Grelhado", "Robalo ao Sal Grosso")
- "desc": uma descrição sensorial do prato em UMA frase longa (2 a 4 linhas). Em PT-BR. Linguagem refinada, evocativa, sem clichês como "experiência única". Foque em ingredientes, técnica, textura, aroma.
- "area": bairro/região principal em Ribeirão Preto, extraído do endereço (ex: "Jardim Sumaré")
- "publicar": true se você recomenda publicar no EatPrime (requer: premium, rating >= 4.3, coerente com a curadoria de cortes nobres, massas italianas, peixes finos ou cozinha autoral); false caso contrário
- "motivo_exclusao": string curta explicando por que NÃO publicar (só se publicar=false; se publicar=true, use string vazia "")

DADOS DO RESTAURANTE:
"""


def descobrir_via_gemini(api_key, ja_catalogados):
    """Modo sem Places: pede pro Gemini listar restaurantes premium direto."""
    lista = "\n".join(f"- {n}" for n in sorted(ja_catalogados))
    prompt = PROMPT_DESCOBERTA.format(ja_catalogados=lista or "(nenhum)")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }
    url = f"{GEMINI_URL}?key={api_key}"
    r = requests.post(url, json=payload, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
    dados = r.json()
    texto = dados["candidates"][0]["content"]["parts"][0]["text"].strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto.startswith("json"):
            texto = texto[4:].strip()
    return json.loads(texto)


def chamar_gemini(api_key, texto_restaurante):
    """Chama Gemini e parseia o JSON retornado."""
    payload = {
        "contents": [{
            "parts": [{"text": PROMPT_GEMINI + texto_restaurante}]
        }],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
        },
    }
    url = f"{GEMINI_URL}?key={api_key}"
    r = requests.post(url, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
    dados = r.json()
    try:
        texto = dados["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Resposta Gemini sem texto: {json.dumps(dados)[:300]}")
    # Às vezes Gemini embrulha em ```json ... ``` mesmo com responseMimeType
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto.startswith("json"):
            texto = texto[4:].strip()
    return json.loads(texto)


# =============================================================================
# EXISTENTES (evitar duplicar)
# =============================================================================

def carregar_existentes():
    if not ARQUIVO_EXISTENTES.exists():
        return set()
    try:
        with open(ARQUIVO_EXISTENTES, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return {r["nome"].strip().lower() for r in dados.get("restaurantes", [])}
    except Exception:
        return set()


# =============================================================================
# PIPELINE
# =============================================================================

def texto_do_place(place):
    """Monta um bloco de texto sobre o restaurante pra enviar ao Gemini."""
    nome = (place.get("displayName") or {}).get("text", "")
    ed = place.get("formattedAddress", "")
    rating = place.get("rating")
    reviews = place.get("userRatingCount")
    tipo = (place.get("primaryTypeDisplayName") or {}).get("text", "")
    resumo = (place.get("editorialSummary") or {}).get("text", "")
    price = place.get("priceLevel", "")

    linhas = [
        f"Nome: {nome}",
        f"Endereço: {ed}",
        f"Tipo (Google): {tipo}",
        f"Rating: {rating} ({reviews} avaliações)",
        f"Nível de preço: {price}",
    ]
    if resumo:
        linhas.append(f"Resumo do Google: {resumo}")
    return "\n".join(linhas)


def prospectar_gemini_only(gemini_key, args):
    """Descoberta sem Places API — Gemini lista direto o que conhece."""
    existentes_set = carregar_existentes()
    log(f"Já catalogados: {len(existentes_set)}", "info")
    log("Perguntando ao Gemini por restaurantes premium de Ribeirão Preto...", "ia")

    try:
        lista = descobrir_via_gemini(gemini_key, existentes_set)
    except Exception as e:
        log(f"Gemini falhou: {e}", "erro")
        return [], []

    log(f"Gemini retornou {len(lista)} sugestões", "ok")

    candidatos = []
    descartados = []
    for item in lista:
        nome = (item.get("nome") or "").strip()
        if not nome:
            continue
        if nome.lower() in existentes_set:
            descartados.append({"nome": nome, "motivo": "já catalogado"})
            continue
        if item.get("confianca") == "baixa":
            descartados.append({"nome": nome, "motivo": "confiança baixa (Gemini)"})
            continue
        candidatos.append({
            "nome": nome,
            "endereco": item.get("endereco_hint", ""),
            "area": item.get("area", ""),
            "prato": item.get("prato", ""),
            "tag": item.get("tag", ""),
            "cuisine": item.get("cuisine", ""),
            "desc": item.get("desc", ""),
            "whatsapp": "",
            "whatsapp_verificado": False,
            "google_rating": None,
            "google_reviews": None,
            "google_maps_uri": None,
            "telefone_google": "",
            "fotos": [],
            "_origem": {
                "fonte": "gemini-only",
                "confianca": item.get("confianca"),
                "descoberto_em": datetime.datetime.now().isoformat(timespec="seconds"),
            },
        })
        log(f"  ✓ {nome} — {item.get('tag')} · {item.get('cuisine')} · conf={item.get('confianca')}", "ok")

        if len(candidatos) >= args.max:
            break

    return candidatos, descartados


def prospectar(places_key, gemini_key, args):
    existentes = carregar_existentes()
    log(f"Já catalogados: {len(existentes)}", "info")

    vistos = set()
    candidatos = []
    descartados = []

    for i, query in enumerate(QUERIES_PROSPECCAO, start=1):
        log(f"[{i}/{len(QUERIES_PROSPECCAO)}] Query: \"{query}\"", "info")
        try:
            places = buscar_places(places_key, query, max_resultados=args.por_query)
        except Exception as e:
            log(f"  Falhou: {e}", "erro")
            continue

        log(f"  Retornou {len(places)} places", "ok")
        if places:
            primeiro = (places[0].get("displayName") or {}).get("text", "?")
            rating0 = places[0].get("rating")
            reviews0 = places[0].get("userRatingCount")
            price0 = places[0].get("priceLevel")
            log(f"  1º: {primeiro} · ★{rating0} · {reviews0} reviews · price={price0}", "info")

        for place in places:
            if len(candidatos) >= args.max:
                break
            nome_raw = (place.get("displayName") or {}).get("text", "")
            nome = nome_raw.strip().lower()
            if not nome or nome in vistos:
                continue
            vistos.add(nome)

            if nome in existentes:
                descartados.append({"nome": nome_raw, "motivo": "já catalogado"})
                continue

            ok, motivo = passa_filtro(place, args.min_rating, args.min_reviews, args.min_price)
            if not ok:
                log(f"    ✗ {nome_raw}: {motivo}", "aviso")
                descartados.append({"nome": nome_raw, "motivo": motivo})
                continue

            # Chama Gemini pra classificar e enriquecer
            log(f"  → Gemini: {nome_raw}", "ia")
            try:
                analise = chamar_gemini(gemini_key, texto_do_place(place))
                time.sleep(0.6)  # respira pra free tier (limite por minuto)
            except Exception as e:
                log(f"    IA falhou: {e}", "aviso")
                descartados.append({"nome": nome_raw, "motivo": f"IA falhou: {e}"})
                continue

            if not analise.get("publicar"):
                descartados.append({
                    "nome": nome_raw,
                    "motivo": f"IA descartou: {analise.get('motivo_exclusao', 'sem motivo')}",
                })
                continue

            # Monta o candidato no schema do EatPrime
            candidato = {
                "nome": nome_raw,
                "endereco": place.get("formattedAddress", ""),
                "area": analise.get("area", ""),
                "prato": analise.get("prato", ""),
                "tag": analise.get("tag", ""),
                "cuisine": analise.get("cuisine", ""),
                "desc": analise.get("desc", ""),
                "whatsapp": "",  # preencher manualmente depois
                "whatsapp_verificado": False,
                "google_rating": place.get("rating"),
                "google_reviews": place.get("userRatingCount"),
                "google_maps_uri": place.get("googleMapsUri"),
                "telefone_google": place.get("internationalPhoneNumber", ""),
                "fotos": [],  # placeholder — preencher com Unsplash/Pexels depois
                "_origem": {
                    "query": query,
                    "place_id": place.get("id"),
                    "descoberto_em": datetime.datetime.now().isoformat(timespec="seconds"),
                },
            }
            candidatos.append(candidato)
            log(f"    ✓ Candidato: {nome_raw} — {candidato['tag']} · {candidato['prato']}", "ok")

        if len(candidatos) >= args.max:
            log(f"Limite de {args.max} candidatos atingido, parando.", "info")
            break
        time.sleep(0.5)

    return candidatos, descartados


def salvar(candidatos, descartados):
    saida = {
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "fonte": "Agente Prospector — Google Places + Gemini",
        "cidade": "Ribeirão Preto - SP",
        "total_candidatos": len(candidatos),
        "total_descartados": len(descartados),
        "candidatos": candidatos,
        "descartados": descartados,
    }
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)
    log(f"Salvo: {ARQUIVO_SAIDA}", "ok")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="EatPrime — Agente Prospector (Gemini)")
    parser.add_argument("--max", type=int, default=15, help="Máximo de candidatos (default 15)")
    parser.add_argument("--por-query", type=int, default=10, help="Places por query (default 10)")
    parser.add_argument("--min-rating", type=float, default=4.3)
    parser.add_argument("--min-reviews", type=int, default=150)
    parser.add_argument("--min-price", type=int, default=3, help="1=barato, 4=muito caro")
    parser.add_argument("--sem-places", action="store_true",
                        help="Pula Google Places — usa só Gemini pra descobrir (útil se Places API não está habilitada)")
    args = parser.parse_args()

    # Se faltar Gemini, pergunta e salva em .env.local (Places é opcional)
    if not os.environ.get("GEMINI_API_KEY"):
        pedir_e_salvar_chaves()

    places_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        log("GEMINI_API_KEY é obrigatória. Abortando.", "erro")
        sys.exit(1)

    # Se --sem-places ou se não houver chave Places, vai direto pro modo Gemini-only
    if args.sem_places or not places_key:
        log("Modo: Gemini-only (sem Google Places)", "info")
        print()
        candidatos, descartados = prospectar_gemini_only(gemini_key, args)
        print()
        log(f"Candidatos: {len(candidatos)}  ·  Descartados: {len(descartados)}", "ok")
        salvar(candidatos, descartados)
        print()
        log("Próximo passo: revisar candidatos.json à mão.", "info")
        log("Depois rode agente_publicador.py pra merge no restaurantes_dados.json.", "info")
        return

    log(f"Filtros: rating≥{args.min_rating} · reviews≥{args.min_reviews} · price≥{args.min_price}", "info")
    log(f"Queries: {len(QUERIES_PROSPECCAO)} · Max candidatos: {args.max}", "info")
    print()

    candidatos, descartados = prospectar(places_key, gemini_key, args)

    print()
    log(f"Candidatos aprovados: {len(candidatos)}", "ok")
    log(f"Descartados: {len(descartados)}", "info")
    salvar(candidatos, descartados)

    print()
    log("Próximo passo: revisar candidatos.json à mão.", "info")
    log("Depois rode agente_publicador.py pra merge no restaurantes_dados.json.", "info")


if __name__ == "__main__":
    main()
