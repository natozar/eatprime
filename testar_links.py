"""
EatPrime · Testador rápido dos links de WhatsApp
-------------------------------------------------
Abre cada link de WhatsApp no navegador, um por vez, com pausa entre eles.
Use isso ANTES da demo pra confirmar que todos os números funcionam.

Uso:
    python testar_links.py              # abre todos em sequência, 3s entre cada
    python testar_links.py --lento      # 6s entre cada (pra ter tempo de conferir)
    python testar_links.py --apenas 1,4,7   # só os IDs especificados
"""

import json
import time
import argparse
import webbrowser
import urllib.parse
from pathlib import Path

ARQUIVO_JSON = Path(__file__).parent / "restaurantes_dados.json"


def carregar():
    with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lento", action="store_true", help="6s entre cada link (default 3s)")
    parser.add_argument("--apenas", type=str, default="", help="IDs separados por vírgula, ex: 1,4,7")
    args = parser.parse_args()

    dados = carregar()
    restaurantes = dados.get("restaurantes", [])

    if args.apenas:
        ids = {int(x.strip()) for x in args.apenas.split(",")}
        restaurantes = [r for r in restaurantes if r["id"] in ids]

    pausa = 6 if args.lento else 3

    print(f"Testando {len(restaurantes)} restaurantes. Pausa de {pausa}s entre cada.")
    print("Confirme em cada janela que abre se o WhatsApp do restaurante está correto.")
    print("Ctrl+C pra parar.\n")

    for r in restaurantes:
        if not r.get("whatsapp"):
            print(f"[{r['id']:02d}] {r['nome']} — SEM whatsapp cadastrado")
            continue
        msg = f"Olá! Encontrei vocês pelo EatPrime e gostaria de pedir/reservar o {r['prato']}."
        url = f"https://wa.me/{r['whatsapp']}?text={urllib.parse.quote(msg)}"
        print(f"[{r['id']:02d}] {r['nome']} → {url}")
        webbrowser.open(url)
        time.sleep(pausa)

    print("\nPronto. Marque no JSON os verificados com: whatsapp_verificado: true")


if __name__ == "__main__":
    main()
