"""
EatPrime · Agente Publicador (CLI)
----------------------------------
Lê candidatos.json (gerado por agente_prospector.py), pergunta 1 a 1 se
você aprova, e integra os aprovados em restaurantes_dados.json.

Por padrão NÃO faz commit/push — só mexe no JSON. Com --commit, faz
commit local e pergunta se quer dar push.

Uso:
    python agente_publicador.py
    python agente_publicador.py --auto-aprovar      # publica tudo sem perguntar (cuidado)
    python agente_publicador.py --commit            # cria commit local depois
"""

import os
import sys
import json
import argparse
import datetime
import subprocess
from pathlib import Path

# Windows: força UTF-8 no stdout/stderr
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).parent
ARQUIVO_CANDIDATOS = BASE_DIR / "candidatos.json"
ARQUIVO_DADOS = BASE_DIR / "restaurantes_dados.json"


def carregar_env_local():
    """Lê .env.local (já no .gitignore) e injeta em os.environ."""
    arquivo = BASE_DIR / ".env.local"
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if chave and chave not in os.environ:
            os.environ[chave] = valor


carregar_env_local()


# =============================================================================
# PLACEHOLDERS DE FOTO (Unsplash / Pexels)
# =============================================================================
# Fotos livres de licença comercial, com crédito devido no JSON. Trocar
# depois pela foto oficial do restaurante quando o dono autorizar.

PLACEHOLDERS_POR_TAG = {
    "Carnes": {
        "url": "https://images.unsplash.com/photo-1544025162-d76694265947?w=1200&q=80",
        "credito": {"autor": "Emerson Vieira", "fonte": "Unsplash"},
    },
    "Italiana": {
        "url": "https://images.unsplash.com/photo-1551183053-bf91a1d81141?w=1200&q=80",
        "credito": {"autor": "Eaters Collective", "fonte": "Unsplash"},
    },
    "Peixes": {
        "url": "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=1200&q=80",
        "credito": {"autor": "Jakub Kapusnak", "fonte": "Unsplash"},
    },
    "Japonesa": {
        "url": "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=1200&q=80",
        "credito": {"autor": "Riccardo Bergamini", "fonte": "Unsplash"},
    },
    "Francesa": {
        "url": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=1200&q=80",
        "credito": {"autor": "Louis Hansel", "fonte": "Unsplash"},
    },
    "Contemporânea": {
        "url": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?w=1200&q=80",
        "credito": {"autor": "Jay Wennington", "fonte": "Unsplash"},
    },
    "Brasileira": {
        "url": "https://images.unsplash.com/photo-1555126634-323283e090fa?w=1200&q=80",
        "credito": {"autor": "Jonathan Borba", "fonte": "Unsplash"},
    },
}
PLACEHOLDER_DEFAULT = PLACEHOLDERS_POR_TAG["Contemporânea"]


def log(msg, tipo="info"):
    prefixos = {"info": "[·]", "ok": "[✓]", "erro": "[✗]", "aviso": "[!]"}
    print(f"{prefixos.get(tipo, '[·]')} {msg}", flush=True)


def pergunta(prompt):
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return "n"


# =============================================================================
# PIPELINE
# =============================================================================

def carregar_json(arquivo):
    if not arquivo.exists():
        log(f"Arquivo não encontrado: {arquivo}", "erro")
        sys.exit(1)
    with open(arquivo, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_json(arquivo, dados):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def proximo_id(restaurantes):
    if not restaurantes:
        return 1
    return max(r.get("id", 0) for r in restaurantes) + 1


def integrar_candidato(candidato, novo_id):
    """Converte um candidato em entrada pronta pro restaurantes_dados.json."""
    tag = candidato.get("tag", "Contemporânea")
    placeholder = PLACEHOLDERS_POR_TAG.get(tag, PLACEHOLDER_DEFAULT)

    entrada = {
        "id": novo_id,
        "nome": candidato["nome"],
        "endereco": candidato.get("endereco", ""),
        "area": candidato.get("area", ""),
        "prato": candidato.get("prato", ""),
        "tag": tag,
        "cuisine": candidato.get("cuisine", ""),
        "desc": candidato.get("desc", ""),
        "whatsapp": candidato.get("whatsapp", ""),
        "whatsapp_verificado": False,  # sempre falso até rodar testar_links.py
        "google_rating": candidato.get("google_rating"),
        "google_reviews": candidato.get("google_reviews"),
        "google_maps_uri": candidato.get("google_maps_uri"),
        "fotos": [placeholder["url"]],
        "foto_credito": {
            **placeholder["credito"],
            "url": placeholder["url"],
            "observacao": "Placeholder — trocar por foto oficial do restaurante quando autorizado.",
        },
        "_origem_prospector": candidato.get("_origem"),
        "_publicado_em": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    return entrada


def revisar(candidatos, auto):
    """Percorre candidatos e pergunta aprovação — retorna lista aprovada."""
    aprovados = []
    for i, c in enumerate(candidatos, start=1):
        print()
        print("=" * 72)
        print(f"[{i}/{len(candidatos)}] {c['nome']}")
        print(f"    {c.get('endereco', '')}")
        print(f"    ★ {c.get('google_rating')} ({c.get('google_reviews')} avaliações)")
        print(f"    Tag: {c.get('tag')} · Cozinha: {c.get('cuisine')}")
        print(f"    Prato sugerido: {c.get('prato')}")
        print(f"    Descrição IA:")
        print(f"      {c.get('desc', '')}")
        if c.get("google_maps_uri"):
            print(f"    Maps: {c['google_maps_uri']}")

        if auto:
            aprovados.append(c)
            log("Auto-aprovado.", "ok")
            continue

        resp = pergunta("    Publicar? [s/N/q=sair] ")
        if resp == "q":
            break
        if resp in ("s", "sim", "y", "yes"):
            aprovados.append(c)
            log("Aprovado.", "ok")
        else:
            log("Pulado.", "info")
    return aprovados


def git_commit(mensagem):
    try:
        subprocess.run(["git", "add", "restaurantes_dados.json"], cwd=BASE_DIR, check=True)
        subprocess.run(["git", "commit", "-m", mensagem], cwd=BASE_DIR, check=True)
        log(f"Commit criado: {mensagem}", "ok")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Commit falhou: {e}", "erro")
        return False


def git_push():
    try:
        subprocess.run(["git", "push"], cwd=BASE_DIR, check=True)
        log("Push enviado.", "ok")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Push falhou: {e}", "erro")
        return False


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="EatPrime — Agente Publicador")
    parser.add_argument("--auto-aprovar", action="store_true",
                        help="Publica todos os candidatos sem perguntar")
    parser.add_argument("--commit", action="store_true",
                        help="Cria commit git local após merge")
    args = parser.parse_args()

    candidatos_full = carregar_json(ARQUIVO_CANDIDATOS)
    candidatos = candidatos_full.get("candidatos", [])
    if not candidatos:
        log("Nenhum candidato no candidatos.json. Rode agente_prospector.py primeiro.", "aviso")
        sys.exit(0)

    log(f"Candidatos a revisar: {len(candidatos)}", "info")

    dados = carregar_json(ARQUIVO_DADOS)
    restaurantes = dados.get("restaurantes", [])
    nomes_existentes = {r["nome"].strip().lower() for r in restaurantes}

    # Filtra antes de revisar — evita mostrar duplicatas que sobraram
    candidatos = [c for c in candidatos if c["nome"].strip().lower() not in nomes_existentes]
    if not candidatos:
        log("Todos os candidatos já estão em restaurantes_dados.json.", "info")
        sys.exit(0)

    aprovados = revisar(candidatos, auto=args.auto_aprovar)
    if not aprovados:
        log("Nenhum aprovado. Nada a fazer.", "info")
        sys.exit(0)

    print()
    log(f"Integrando {len(aprovados)} aprovado(s)...", "info")
    novo_id = proximo_id(restaurantes)
    for c in aprovados:
        entrada = integrar_candidato(c, novo_id)
        restaurantes.append(entrada)
        log(f"  + #{novo_id} {entrada['nome']}", "ok")
        novo_id += 1

    dados["restaurantes"] = restaurantes
    dados["gerado_em"] = datetime.datetime.now().isoformat(timespec="seconds")
    salvar_json(ARQUIVO_DADOS, dados)
    log(f"Atualizado: {ARQUIVO_DADOS}", "ok")

    # Lembrete de próximos passos manuais
    print()
    log("REVISAR À MÃO:", "aviso")
    log("  1. whatsapp dos novos restaurantes (vazio — preencher e rodar testar_links.py)", "info")
    log("  2. fotos — trocar placeholder Unsplash por foto oficial quando autorizado", "info")
    log("  3. bump CACHE_VERSION em sw.js pra usuários receberem a atualização", "info")

    if args.commit:
        print()
        nomes = ", ".join(c["nome"] for c in aprovados[:3])
        if len(aprovados) > 3:
            nomes += f" (+{len(aprovados)-3})"
        mensagem = f"feat(dados): adiciona {len(aprovados)} restaurante(s) via prospector — {nomes}"
        if git_commit(mensagem):
            resp = pergunta("Fazer push agora? [s/N] ")
            if resp in ("s", "sim", "y", "yes"):
                git_push()


if __name__ == "__main__":
    main()
