"""
EatPrime · Aplicador de dados coletados pela extensão do Claude no navegador
-----------------------------------------------------------------------------
Merge não-destrutivo: pega os dados do payload DADOS_NAVEGADOR abaixo e aplica
no restaurantes_dados.json, baixa as fotos de Unsplash/Pexels pra fotos/ e
preserva campos existentes (endereço, descrição, prato, tag, cuisine, área).

Uso:
    python aplicar_dados_navegador.py
    python aplicar_dados_navegador.py --dry-run    # mostra o que mudaria, não salva
    python aplicar_dados_navegador.py --sem-fotos  # só merge do JSON, não baixa

Idempotente: pode rodar várias vezes sem quebrar nada.
"""

import json
import sys
import datetime
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    print("[ERRO] Falta 'requests'. Rode:  pip install requests")
    sys.exit(1)


ROOT = Path(__file__).parent
ARQUIVO_JSON = ROOT / "restaurantes_dados.json"
PASTA_FOTOS = ROOT / "fotos"

# Foto do Ancho Di Tullio veio do Pexels (Unsplash null). Override manual.
FOTO_OVERRIDE_POR_ID = {
    6: {
        "url": "https://images.pexels.com/photos/36782574/pexels-photo-36782574/free-photo-of-grilled-ribeye-steak-on-wooden-cutting-board.jpeg?w=1200",
        "credito": {
            "autor": "Mohamed Olwy",
            "fonte": "Pexels",
            "url": "https://www.pexels.com/photo/grilled-ribeye-steak-on-wooden-cutting-board-36782574/",
        },
    },
}


# =============================================================================
# PAYLOAD — devolvido pela extensão do Claude no navegador
# =============================================================================

DADOS_NAVEGADOR = {
  "dados": [
    {
      "id": 1,
      "nome": "Gran Steak",
      "google_rating": 4.8,
      "google_reviews": 5437,
      "google_maps_uri": "https://www.google.com/maps/place/Gran+Steak/@-21.1946873,-47.8114582,17z/data=!3m1!4b1!4m6!3m5!1s0x94b9bed96fa264a3:0x40ea9153e2d0cb6a!8m2!3d-21.1946873!4d-47.8088833!16s%2Fg%2F11bxdvf9td",
      "whatsapp": "551639119009",
      "whatsapp_verificado": True,
      "foto_url_unsplash": "https://images.unsplash.com/photo-1558030077-82dd9347c407",
      "foto_credito_autor": "Emerson Vieira",
      "foto_credito_pagina": "https://unsplash.com/pt-br/fotografias/pessoa-fazendo-churrasco-de-carne-_aR4l6fj6wQ",
      "observacao": "WhatsApp usa número fixo (16) 3911-9009 via WhatsApp Business, confirmado por link wa.me/551639119009 no Instagram oficial @gransteakribeirao."
    },
    {
      "id": 2,
      "nome": "Varanda da Picanha",
      "google_rating": 4.7,
      "google_reviews": 3461,
      "google_maps_uri": "https://www.google.com/maps/place/Varanda+da+Picanha/@-21.1792346,-47.8037398,17z/data=!3m1!4b1!4m6!3m5!1s0x94b9bf1d1c3e2425:0xc78935c94cc048a7!8m2!3d-21.1792346!4d-47.8011649!16s%2Fg%2F11bbrlc7l0",
      "whatsapp": "5516982194644",
      "whatsapp_verificado": True,
      "foto_url_unsplash": "https://images.unsplash.com/photo-1600891964092-4316c288032e",
      "foto_credito_autor": "Justus Menke",
      "foto_credito_pagina": "https://unsplash.com/pt-br/fotografias/bolo-de-chocolate-marrom-e-preto-62XLglIrTJc",
      "observacao": None
    },
    {
      "id": 3,
      "nome": "Latulia Restaurante e Costelaria",
      "google_rating": None,
      "google_reviews": None,
      "google_maps_uri": "https://www.google.com/maps/place/Latulia+Restaurante+e+Costelaria/@-21.2023905,-47.8101123,17z/data=!3m1!4b1!4m6!3m5!1s0x94b9bed6c7794097:0x8b6ffaeba7925651!8m2!3d-21.2023905!4d-47.8075374!16s%2Fg%2F1q5gpzl_c",
      "whatsapp": "5516982386530",
      "whatsapp_verificado": True,
      "foto_url_unsplash": "https://images.unsplash.com/photo-1558030137-a56c1b004fa3",
      "foto_credito_autor": "Alexandru-Bogdan Ghita",
      "foto_credito_pagina": "https://unsplash.com/pt-br/fotografias/costela-assada-com-tomates-fatiados-e-batatas-UeYkqQh4PoI",
      "observacao": "Ficha no Google Maps não exibe rating/estrelas nem contagem de avaliações."
    },
    {
      "id": 4,
      "nome": "Amici Di Tullio",
      "google_rating": 4.7,
      "google_reviews": 1236,
      "google_maps_uri": "https://www.google.com/maps/place/Amici+Di+Tullio/@-21.19041,-47.8106302,17z/data=!3m1!4b1!4m6!3m5!1s0x94b9bede0b0167b1:0xfef9d3ce41e9027e!8m2!3d-21.19041!4d-47.8080553!16s%2Fg%2F11b7g0db8y",
      "whatsapp": None,
      "whatsapp_verificado": False,
      "foto_url_unsplash": "https://images.unsplash.com/photo-1744406475841-dfc235e6ecb0",
      "foto_credito_autor": "Meg von Haartman",
      "foto_credito_pagina": "https://unsplash.com/pt-br/fotografias/prato-de-massa-com-molho-ervas-e-enfeite-q2F-xP_CrwA",
      "observacao": "Sem celular WhatsApp. Grupo Di Tullio usa fixo (16) 3235-9610."
    },
    {
      "id": 5,
      "nome": "La Cucina di Tullio Santini",
      "google_rating": 4.7,
      "google_reviews": 1122,
      "google_maps_uri": "https://www.google.com/maps/place/La+Cucina+di+Tullio+Santini/@-21.1941976,-47.8045445,17z/data=!3m1!4b1!4m6!3m5!1s0x94b9bf276d5860f1:0x422c29698723552a!8m2!3d-21.1941976!4d-47.8019696!16s%2Fg%2F1q69jn23n",
      "whatsapp": None,
      "whatsapp_verificado": False,
      "foto_url_unsplash": "https://images.unsplash.com/photo-1640193881544-e8b70488db0d",
      "foto_credito_autor": "Jonathan Borba",
      "foto_credito_pagina": "https://unsplash.com/pt-br/fotografias/comida-cozida-na-placa-de-ceramica-branca-x_ObRUc51S0",
      "observacao": "Sem celular WhatsApp. Telefone fixo: (16) 3623-6361."
    },
    {
      "id": 6,
      "nome": "Restaurante Ancho Di Tullio",
      "google_rating": 4.6,
      "google_reviews": 467,
      "google_maps_uri": "https://www.google.com/maps/place/Restaurante+Ancho+Di+Tullio/@-21.210892,-47.8136745,17z/data=!3m1!4b1!4m6!3m5!1s0x94b9b9298749d3a9:0x7fdd088d4fe1caa7!8m2!3d-21.210892!4d-47.8110996!16s%2Fg%2F11h10d_m3",
      "whatsapp": None,
      "whatsapp_verificado": False,
      "foto_url_unsplash": None,
      "foto_credito_autor": "Mohamed Olwy",
      "foto_credito_pagina": "https://www.pexels.com/photo/grilled-ribeye-steak-on-wooden-cutting-board-36782574/",
      "observacao": "Foto via Pexels. Sem WhatsApp celular; fixo (16) 3610-9794."
    },
    {
      "id": 7,
      "nome": "Restaurante Bello Di Tullio",
      "google_rating": 4.6,
      "google_reviews": 912,
      "google_maps_uri": "https://www.google.com/maps/place/Restaurante+Bello+Di+Tullio/@-21.2110336,-47.8136506,17z/data=!3m1!4b1!4m6!3m5!1s0x94b9b92d19867343:0xf2ae9bec6a9bf997!8m2!3d-21.2110336!4d-47.8110757!16s%2Fg%2F11c3_9mnmz",
      "whatsapp": None,
      "whatsapp_verificado": False,
      "foto_url_unsplash": "https://images.unsplash.com/photo-1626299748494-939f18cf52be",
      "foto_credito_autor": "Bruna Branco",
      "foto_credito_pagina": "https://unsplash.com/pt-br/fotografias/macarrao-no-prato-com-garfo-t8hTmte4O_g",
      "observacao": "Sem celular WhatsApp; fixo (16) 3610-4249."
    },
    {
      "id": 8,
      "nome": "Rubinho Bar e Restaurante",
      "google_rating": 4.7,
      "google_reviews": 847,
      "google_maps_uri": "https://www.google.com/maps/place/Rubinho+Bar+e+Restaurante/@-21.1836884,-47.7946091,17z/data=!3m1!4b1!4m6!3m5!1s0x94b9bf17c1f8539d:0x805d228c77644155!8m2!3d-21.1836884!4d-47.7920342!16s%2Fg%2F11ggvtq2x0",
      "whatsapp": None,
      "whatsapp_verificado": False,
      "foto_url_unsplash": "https://images.unsplash.com/photo-1535424921017-85119f91e5a1",
      "foto_credito_autor": "Karolina Grabowska",
      "foto_credito_pagina": "https://unsplash.com/pt-br/fotografias/peixe-grelhado-com-salada-de-legumes-no-prato-de-ceramica-branca-N8-bMqUMS8g",
      "observacao": "Rubinho usa fixo como WA Business. Retornado null."
    },
    {
      "id": 9,
      "nome": "Picanha e Peixe na Brasa",
      "google_rating": 4.8,
      "google_reviews": 534,
      "google_maps_uri": "https://www.google.com/maps/place/Picanha+e+Peixe+na+Brasa+%7C+Restaurante+em+Ribeir%C3%A3o+Preto/@-21.1803076,-47.7931558,17z/data=!3m1!4b1!4m6!3m5!1s0x94b9bf57a73ef747:0x6702a27cbf124e38!8m2!3d-21.1803076!4d-47.7905809!16s%2Fg%2F11f6g2yc08",
      "whatsapp": None,
      "whatsapp_verificado": False,
      "foto_url_unsplash": "https://images.unsplash.com/photo-1765894711192-d35787eee3b6",
      "foto_credito_autor": "Feyza Yıldırım",
      "foto_credito_pagina": "https://unsplash.com/pt-br/fotografias/um-prato-de-comida-com-carne-e-brocolis-HhEfe0DeMiA",
      "observacao": "Usa fixo como WA Business. Retornado null."
    },
    {
      "id": 10,
      "nome": "MadreMia Restaurante",
      "google_rating": 4.8,
      "google_reviews": 306,
      "google_maps_uri": "https://www.google.com/maps/place/MadreMia+Restaurante/@-21.1917244,-47.8061022,17z/data=!3m1!4b1!4m6!3m5!1s0x94b9bf747cb9f9e1:0x2cd82b66e88f8736!8m2!3d-21.1917244!4d-47.8035273!16s%2Fg%2F11t_rws7r7",
      "whatsapp": "5516996126790",
      "whatsapp_verificado": True,
      "foto_url_unsplash": "https://images.unsplash.com/photo-1765100778802-f684a4b7fd20",
      "foto_credito_autor": "Krisztina Papp",
      "foto_credito_pagina": "https://unsplash.com/pt-br/fotografias/prato-de-macarrao-lnWeBWM7__U",
      "observacao": None
    }
  ]
}


# =============================================================================
# HELPERS
# =============================================================================

def log(msg, tipo="info"):
    # ASCII-safe pra evitar UnicodeEncodeError no terminal Windows cp1252
    prefixos = {"info": "[.]", "ok": "[OK]", "erro": "[X]", "aviso": "[!]", "diff": "[~]"}
    try:
        print(f"{prefixos.get(tipo, '[.]')} {msg}", flush=True)
    except UnicodeEncodeError:
        print(f"{prefixos.get(tipo, '[.]')} {msg.encode('ascii', 'replace').decode('ascii')}", flush=True)


def normalizar_url_unsplash(url):
    """Unsplash aceita parâmetros pra downscale. Mantém peso razoável."""
    if not url:
        return None
    if "unsplash.com" in url and "?" not in url:
        return url + "?w=1200&q=80&auto=format&fit=crop"
    return url


def baixar_imagem(url, destino):
    r = requests.get(url, timeout=30, stream=True,
                     headers={"User-Agent": "Mozilla/5.0 EatPrime-fetch"})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    with open(destino, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return destino.stat().st_size


def montar_url_foto(dado, rid):
    """Escolhe foto do override (Pexels) se houver, senão Unsplash normalizado."""
    override = FOTO_OVERRIDE_POR_ID.get(rid)
    if override:
        return override["url"], override["credito"]
    url = normalizar_url_unsplash(dado.get("foto_url_unsplash"))
    if not url:
        return None, None
    credito = {
        "autor": dado.get("foto_credito_autor"),
        "fonte": "Unsplash",
        "url": dado.get("foto_credito_pagina"),
    }
    return url, credito


# =============================================================================
# MERGE
# =============================================================================

def merge_restaurante(atual, payload, baixou_foto):
    """Aplica dados do payload sobre o registro atual, preservando campos locais."""
    novo = dict(atual)
    diffs = []

    def set_se_mudou(chave, novo_valor):
        antigo = atual.get(chave)
        if antigo != novo_valor:
            diffs.append(f"{chave}: {antigo!r} -> {novo_valor!r}")
        novo[chave] = novo_valor

    # Rating e Maps vêm sempre do payload (dados públicos frescos)
    set_se_mudou("google_rating", payload.get("google_rating"))
    set_se_mudou("google_reviews", payload.get("google_reviews"))
    set_se_mudou("google_maps_uri", payload.get("google_maps_uri"))

    # WhatsApp: só substitui se o payload trouxe um novo. Se payload vier null,
    # preserva o seed — o botão WA só aparece com whatsapp_verificado=True de toda forma.
    wa_payload = payload.get("whatsapp")
    if wa_payload:
        set_se_mudou("whatsapp", wa_payload)
        set_se_mudou("whatsapp_verificado", bool(payload.get("whatsapp_verificado")))
    else:
        # Payload não confirmou WA. Marca como não verificado pra botão sumir.
        if atual.get("whatsapp_verificado"):
            diffs.append(f"whatsapp_verificado: True -> False (payload nao confirmou)")
        novo["whatsapp_verificado"] = False

    # Crédito da foto (novo campo, sempre escreve)
    if baixou_foto and baixou_foto.get("credito"):
        novo["foto_credito"] = baixou_foto["credito"]

    # Observação do levantamento (opcional, bom ter no registro)
    obs = payload.get("observacao")
    if obs:
        novo["_observacao_levantamento"] = obs

    return novo, diffs


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Aplica dados coletados pela extensão do Claude")
    parser.add_argument("--dry-run", action="store_true", help="Mostra diff, não salva")
    parser.add_argument("--sem-fotos", action="store_true", help="Pula download de fotos")
    args = parser.parse_args()

    if not ARQUIVO_JSON.exists():
        log(f"JSON não encontrado: {ARQUIVO_JSON}", "erro")
        sys.exit(1)

    with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
        atual = json.load(f)

    por_id_atual = {r["id"]: r for r in atual.get("restaurantes", [])}
    por_id_payload = {r["id"]: r for r in DADOS_NAVEGADOR["dados"]}

    PASTA_FOTOS.mkdir(exist_ok=True)
    resultado = []
    total_diffs = 0
    fotos_ok = 0
    fotos_fail = 0

    for rid in sorted(por_id_atual.keys()):
        atual_r = por_id_atual[rid]
        payload_r = por_id_payload.get(rid)
        log(f"[{rid:02d}] {atual_r['nome']}", "info")

        if not payload_r:
            log(f"     sem dados do navegador — preservando seed", "aviso")
            resultado.append(atual_r)
            continue

        # --- FOTO ---
        baixou = None
        foto_url, credito = montar_url_foto(payload_r, rid)
        if foto_url and not args.sem_fotos:
            destino = PASTA_FOTOS / f"rest_{rid:02d}_foto_1.jpg"
            try:
                if args.dry_run:
                    log(f"     [dry-run] baixaria: {foto_url}", "info")
                else:
                    tam = baixar_imagem(foto_url, destino)
                    log(f"     foto salva: {destino.name} ({tam // 1024} KB, crédito: {credito['autor']} / {credito['fonte']})", "ok")
                    fotos_ok += 1
                baixou = {"credito": credito}
            except Exception as e:
                log(f"     erro baixando foto: {e}", "erro")
                fotos_fail += 1

        # --- MERGE ---
        novo, diffs = merge_restaurante(atual_r, payload_r, baixou)
        for d in diffs:
            log(f"     ~ {d}", "diff")
        total_diffs += len(diffs)
        resultado.append(novo)

    # --- SALVAR ---
    if args.dry_run:
        print()
        log(f"[dry-run] {total_diffs} diffs detectados. Nada foi escrito.", "aviso")
        return

    saida = {
        "versao": "1.1.0-navegador",
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "fonte": "Extensão do Claude no navegador (Google Maps + Instagram + Unsplash/Pexels)",
        "cidade": atual.get("cidade", "Ribeirão Preto - SP"),
        "restaurantes": resultado,
    }
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    print()
    log(f"JSON salvo: {ARQUIVO_JSON}", "ok")
    log(f"Diffs aplicados: {total_diffs}", "info")
    if not args.sem_fotos:
        log(f"Fotos baixadas: {fotos_ok} OK / {fotos_fail} falhas", "info")


if __name__ == "__main__":
    main()
