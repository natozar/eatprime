# EatPrime

Curadoria premium dos restaurantes de Ribeirão Preto/SP. PWA estático, sem backend, sem taxas pro restaurante, sem intermediários.

**Status:** protótipo interno. Não indexado publicamente (ver `robots.txt`). Restaurantes listados sem vínculo comercial oficial.

## Stack

- HTML + CSS + JS vanilla em um único `index.html`
- PWA com `manifest.json` e service worker cache-first (`sw.js`)
- Dados em JSON estático (`restaurantes_dados.json`)
- Enriquecimento via Google Places API New (script Python opcional)
- Hospedagem: GitHub Pages

## Rodar local

```bash
python -m http.server 8000
```

Abrir `http://localhost:8000`.

## Guia de uso

Ver [COMO_USAR.md](./COMO_USAR.md) para passo a passo de coleta de dados, fotos, WhatsApp e deploy.

## Contexto

Ver [CLAUDE.md](./CLAUDE.md) para contexto completo do projeto, paleta, regras e prioridades.
