"""
EatPrime · Coletor de dados Google Places (API New)
----------------------------------------------------
Uso:
    python coletar_dados.py                  # modo padrão: SEM baixar fotos
    python coletar_dados.py --fotos-google   # baixa fotos do Places (APENAS demo interna)

IMPORTANTE — POLÍTICA DE USO:
    Este script é PARA PROTÓTIPO INTERNO. As fotos do Google Places têm
    restrições do ToS: não podem ser armazenadas permanentemente em um
    site público. Use fotos próprias ou com consentimento antes de ir ao ar.
"""

import os
import sys
import json
import time
import argparse
import datetime
import urllib.parse
from pathlib import Path

try:
    import requests
except ImportError:
    print("[ERRO] Biblioteca 'requests' não encontrada.")
    print("       Rode:  pip install requests")
    sys.exit(1)


# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

# Cole sua API key aqui ou defina a variável de ambiente GOOGLE_PLACES_API_KEY
API_KEY_INLINE = ""  # ex: "AIzaSy..."

PASTA_FOTOS = Path(__file__).parent / "fotos"
ARQUIVO_JSON = Path(__file__).parent / "restaurantes_dados.json"

BASE_URL = "https://places.googleapis.com/v1"
ENDPOINT_SEARCH = f"{BASE_URL}/places:searchText"
ENDPOINT_DETAILS = f"{BASE_URL}/places"

# Campos pedidos no FieldMask — só o necessário pra não gastar quota à toa
FIELDS_SEARCH = "places.id,places.displayName,places.formattedAddress"
FIELDS_DETAILS = (
    "id,displayName,formattedAddress,rating,userRatingCount,"
    "internationalPhoneNumber,websiteUri,googleMapsUri,"
    "regularOpeningHours,photos"
)


# =============================================================================
# LISTA DE RESTAURANTES (seed)
# =============================================================================

RESTAURANTES = [
    {"id": 1, "nome": "Gran Steak", "endereco": "Av. Itatiaia, 1435, Jardim Sumaré, Ribeirão Preto, SP",
     "area": "Jardim Sumaré",
     "prato": "Prime Rib", "tag": "Carnes", "cuisine": "Steakhouse",
     "desc": "Corte nobre de costela bovina assada por horas em baixa temperatura, fatiada na hora. Servida com acompanhamentos clássicos da casa — macia como manteiga, com crosta dourada e suculência que marca a refeição.",
     "whatsapp": "5516999619775"},

    {"id": 2, "nome": "Varanda da Picanha", "endereco": "R. Floriano Peixoto, 40, Centro, Ribeirão Preto, SP",
     "area": "Centro",
     "prato": "Picanha Grelhada", "tag": "Carnes", "cuisine": "Churrascaria",
     "desc": "Picanha selecionada grelhada no ponto, com crosta caramelizada e interior rosado. Acompanha arroz carreteiro de defumados e mandioca frita crocante — clássico do interior paulista bem executado.",
     "whatsapp": "5516362572850"},

    {"id": 3, "nome": "Latulia Restaurante e Costelaria", "endereco": "Av. Sen. César Vergueiro, 1156, Jardim São Luiz, Ribeirão Preto, SP",
     "area": "Jardim São Luiz",
     "prato": "Costela no Bafo", "tag": "Carnes", "cuisine": "Costelaria",
     "desc": "Costela bovina assada lentamente durante horas em forno fechado, para máxima suculência e sabor defumado. Desmancha no garfo, com crosta dourada — um clássico que exige tempo e paciência na cozinha.",
     "whatsapp": "5516362176910"},

    {"id": 4, "nome": "Amici Di Tullio", "endereco": "R. Olavo Bilac, 1280, Jardim Sumaré, Ribeirão Preto, SP",
     "area": "Jardim Sumaré",
     "prato": "Tagliolini al Tartufo", "tag": "Italiana", "cuisine": "Italiana",
     "desc": "Massa fresca artesanal cortada fina, envolvida em molho cremoso de manteiga, queijo parmesão e trufas negras frescas raladas na hora. Aroma marcante, sabor profundo — uma das maiores expressões da cozinha italiana clássica.",
     "whatsapp": "5516997241628"},

    {"id": 5, "nome": "La Cucina di Tullio Santini", "endereco": "Av. Antônio Diederichsen, 485, Jardim São Luiz, Ribeirão Preto, SP",
     "area": "Jardim São Luiz",
     "prato": "Ossobuco com Polenta", "tag": "Italiana", "cuisine": "Italiana",
     "desc": "Jarrete de vitelo cozido lentamente em vinho tinto e legumes até desmanchar. Servido sobre polenta cremosa feita na hora, finalizado com gremolata de limão siciliano. Prato de domingo em família, com apresentação de alta gastronomia.",
     "whatsapp": "5516362363610"},

    {"id": 6, "nome": "Restaurante Ancho Di Tullio", "endereco": "Av. José Adolfo Bianco Molina, 2595, Jardim Canadá, Ribeirão Preto, SP",
     "area": "Jardim Canadá",
     "prato": "Bife Ancho", "tag": "Carnes", "cuisine": "Contemporânea",
     "desc": "Corte nobre argentino de entrecôte, grelhado em brasa no ponto exato. Acompanhado de risoto cremoso de limão siciliano com azeite trufado. Combinação de carne com frescor cítrico que ganhou a mesa dos ribeirãopretanos exigentes.",
     "whatsapp": "5516361097940"},

    {"id": 7, "nome": "Restaurante Bello Di Tullio", "endereco": "R. Bernardo Alves Pereira, 92, Jardim Canadá, Ribeirão Preto, SP",
     "area": "Jardim Canadá",
     "prato": "Fettuccine 4 Formaggi", "tag": "Italiana", "cuisine": "Italiana",
     "desc": "Fettuccine fresca envolvido em molho cremoso de quatro queijos selecionados — gorgonzola, parmesão, provolone e catupiry. Intenso, reconfortante, com equilíbrio entre acidez e untuosidade. Pedido clássico da casa.",
     "whatsapp": "5516361042490"},

    {"id": 8, "nome": "Rubinho Bar e Restaurante", "endereco": "R. Henrique Dumont, 1326, Jardim Paulista, Ribeirão Preto, SP",
     "area": "Jardim Paulista",
     "prato": "Sardinhas Assadas", "tag": "Peixes", "cuisine": "Brasileira",
     "desc": "Sardinhas frescas assadas na brasa com sal grosso, limão e fio de azeite. Acompanha arroz branco soltinho, farofa crocante e vinagrete — simplicidade refinada do litoral trazida para o interior paulista.",
     "whatsapp": "5516342165670"},

    {"id": 9, "nome": "Picanha e Peixe na Brasa", "endereco": "R. Guarujá, 530, Jardim Paulistano, Ribeirão Preto, SP",
     "area": "Jardim Paulistano",
     "prato": "Filé à Parmegiana", "tag": "Carnes", "cuisine": "Brasileira",
     "desc": "Filé mignon alto, empanado e selado, coberto com molho de tomate caseiro e queijo derretido gratinado no forno. Acompanha arroz, fritas e salada. Versão generosa do parmegiana tradicional, preparada sob pedido.",
     "whatsapp": "5516332999750"},

    {"id": 10, "nome": "MadreMia Restaurante", "endereco": "R. João Penteado, 1835, Jardim América, Ribeirão Preto, SP",
     "area": "Jardim América",
     "prato": "Espaguete Negro com Camarão", "tag": "Peixes", "cuisine": "Italiana",
     "desc": "Espaguete artesanal tingido com tinta de lula, envolvido em camarões rosa selados no alho e azeite. Leve toque de pimenta calabresa e salsinha fresca. Apresentação marcante, sabor do mar equilibrado com a massa.",
     "whatsapp": "5516996126790"},
]


# =============================================================================
# FUNÇÕES DA API
# =============================================================================

def log(msg, tipo="info"):
    prefixos = {"info": "[·]", "ok": "[✓]", "erro": "[✗]", "aviso": "[!]"}
    print(f"{prefixos.get(tipo, '[·]')} {msg}", flush=True)


def buscar_place_id(api_key, nome, endereco):
    """Busca Place ID via Text Search (novo endpoint)."""
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELDS_SEARCH,
    }
    payload = {
        "textQuery": f"{nome} {endereco}",
        "languageCode": "pt-BR",
        "regionCode": "BR",
    }
    r = requests.post(ENDPOINT_SEARCH, headers=headers, json=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"SearchText HTTP {r.status_code}: {r.text[:200]}")
    dados = r.json()
    places = dados.get("places", [])
    if not places:
        raise RuntimeError("Nenhum place encontrado")
    return places[0]["id"]


def buscar_detalhes(api_key, place_id):
    """Busca detalhes de um Place."""
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELDS_DETAILS,
    }
    url = f"{ENDPOINT_DETAILS}/{place_id}?languageCode=pt-BR&regionCode=BR"
    r = requests.get(url, headers=headers, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Details HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def baixar_foto(api_key, photo_name, destino, max_width=1200):
    """
    Baixa uma foto via endpoint /media.
    AVISO: Google Places ToS restringe o armazenamento permanente dessas fotos.
    Só use em protótipo interno até ter consentimento / foto própria.
    """
    url = f"{BASE_URL}/{photo_name}/media?maxWidthPx={max_width}&key={api_key}"
    r = requests.get(url, timeout=30, stream=True)
    if r.status_code != 200:
        raise RuntimeError(f"Photo HTTP {r.status_code}")
    with open(destino, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)


# =============================================================================
# PIPELINE
# =============================================================================

def carregar_json_existente():
    """Lê o JSON atual pra preservar campos que o usuário já editou à mão
    (whatsapp_verificado, lista de fotos próprias)."""
    if not ARQUIVO_JSON.exists():
        return {}
    try:
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return {r["id"]: r for r in dados.get("restaurantes", [])}
    except Exception:
        return {}


def processar(api_key, baixar_fotos=False, max_fotos=5):
    PASTA_FOTOS.mkdir(exist_ok=True)
    existentes = carregar_json_existente()
    resultados = []

    for rest in RESTAURANTES:
        rid = rest["id"]
        log(f"[{rid:02d}] {rest['nome']}", "info")
        item = dict(rest)
        prev = existentes.get(rid, {})
        # defaults — preservam o que já havia no JSON quando fizer sentido
        item["whatsapp_verificado"] = bool(prev.get("whatsapp_verificado", False))
        item["google_rating"] = None
        item["google_reviews"] = None
        item["google_maps_uri"] = None
        item["telefone_oficial"] = None
        item["website"] = None
        # Preserva fotos já configuradas (próprias ou Unsplash). Só sobrescreve
        # se o usuário não tiver nada ou se o modo --fotos-google for usado.
        fotos_previas = prev.get("fotos") or []
        item["fotos"] = fotos_previas if fotos_previas else [f"fotos/rest_{rid:02d}_foto_1.jpg"]

        try:
            place_id = buscar_place_id(api_key, rest["nome"], rest["endereco"])
            log(f"     Place ID: {place_id}", "ok")

            detalhes = buscar_detalhes(api_key, place_id)

            item["google_rating"] = detalhes.get("rating")
            item["google_reviews"] = detalhes.get("userRatingCount")
            item["google_maps_uri"] = detalhes.get("googleMapsUri")
            item["telefone_oficial"] = detalhes.get("internationalPhoneNumber")
            item["website"] = detalhes.get("websiteUri")

            log(f"     ★ {item['google_rating']} · {item['google_reviews']} avaliações", "ok")

            # --- FOTOS (opt-in) -----------------------------------------
            # IMPORTANTE: fotos do Google Places ficam com prefixo "google_"
            # pra serem ignoradas automaticamente pelo .gitignore. Assim o
            # modo --fotos-google nunca vaza arquivos pro repo público.
            if baixar_fotos:
                log(f"     ⚠ Baixando fotos (modo Places). NÃO publique sem consentimento.", "aviso")
                photos = detalhes.get("photos", [])[:max_fotos]
                arquivos = []
                for i, photo in enumerate(photos, start=1):
                    photo_name = photo.get("name")
                    if not photo_name:
                        continue
                    destino = PASTA_FOTOS / f"rest_{rid:02d}_google_{i}.jpg"
                    try:
                        baixar_foto(api_key, photo_name, destino)
                        arquivos.append(f"fotos/rest_{rid:02d}_google_{i}.jpg")
                        log(f"     ↳ foto {i}/{len(photos)}", "ok")
                        time.sleep(0.3)  # respira pra não pegar rate limit
                    except Exception as e:
                        log(f"     ↳ foto {i} falhou: {e}", "aviso")
                if arquivos:
                    item["fotos"] = arquivos
            else:
                log(f"     Fotos: preservando caminhos do JSON atual (não baixei nada do Places)", "info")

        except Exception as e:
            log(f"     Falhou: {e}", "erro")
            log(f"     Mantendo dados do seed para este restaurante.", "aviso")

        resultados.append(item)
        time.sleep(0.25)  # pequena pausa entre restaurantes

    return resultados


def salvar(resultados):
    dados = {
        "versao": "1.0.0",
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "cidade": "Ribeirão Preto - SP",
        "restaurantes": resultados,
    }
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    log(f"JSON salvo em: {ARQUIVO_JSON}", "ok")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Coletor EatPrime — Google Places API")
    parser.add_argument("--fotos-google", action="store_true",
                        help="Baixa fotos do Google Places (APENAS protótipo interno, atenção ao ToS)")
    parser.add_argument("--max-fotos", type=int, default=5,
                        help="Número máximo de fotos por restaurante (default 5)")
    args = parser.parse_args()

    # Descobre a API key
    api_key = API_KEY_INLINE or os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        log("API key não encontrada.", "erro")
        log("Cole sua chave em API_KEY_INLINE no topo deste arquivo,", "info")
        log("ou defina a variável de ambiente GOOGLE_PLACES_API_KEY.", "info")
        sys.exit(1)

    log(f"Modo: {'COM fotos Google (DEMO INTERNA)' if args.fotos_google else 'sem fotos Google (seguro)'}", "info")
    log(f"Restaurantes a processar: {len(RESTAURANTES)}", "info")
    print()

    resultados = processar(api_key, baixar_fotos=args.fotos_google, max_fotos=args.max_fotos)
    print()
    salvar(resultados)

    # Resumo
    ok = sum(1 for r in resultados if r.get("google_rating") is not None)
    print()
    log(f"Resumo: {ok}/{len(resultados)} restaurantes com dados do Google.", "info")
    if ok < len(resultados):
        log("Os que falharam mantiveram os dados do seed. Revise o JSON.", "aviso")


if __name__ == "__main__":
    main()
