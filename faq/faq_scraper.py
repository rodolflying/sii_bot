"""
Preguntas frecuentes del SII → base de conocimiento local.

  python faq_scraper.py bajar     recorre www.sii.cl/preguntas_frecuentes desde los menús principales (1 página/s)
  python faq_scraper.py exportar  arma faq_sii.md, una sección por categoría, para leer o pasarle a un LLM

Guarda cada página cruda en paginas/ y cada pregunta en faq_sii.jsonl. Lo ya bajado se salta,
así que se puede cortar y retomar. Solo páginas públicas: no usa sesión ni clave.
"""
import json
import os
import re
import sys
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

BASE = os.path.dirname(os.path.abspath(__file__))
PAGINAS = os.path.join(BASE, "paginas")
JSONL = os.path.join(BASE, "faq_sii.jsonl")
MD = os.path.join(BASE, "faq_sii.md")
RAIZ = "https://www.sii.cl/preguntas_frecuentes/"
INICIOS = [RAIZ + "preguntasfrecuentes.htm", RAIZ + "otros.html"]
PAUSA = 1.0


def local(url: str) -> str:
    return os.path.join(PAGINAS, urlparse(url).path.removeprefix("/preguntas_frecuentes/").replace("/", "__"))


def bajar_pagina(sesion: requests.Session, url: str) -> str | None:
    archivo = local(url)
    if os.path.exists(archivo):
        with open(archivo, encoding="utf-8") as f:
            return f.read()
    time.sleep(PAUSA)
    r = sesion.get(url, timeout=30)
    if r.status_code != 200:
        print(f"  {r.status_code} {url}")
        return None
    html = r.content.decode("utf-8", errors="replace")  # el SII escribe los acentos como entidades HTML
    with open(archivo, "w", encoding="utf-8") as f:
        f.write(html)
    return html


def enlaces(url: str, html: str) -> list[str]:
    salida = []
    # el menú principal navega con onclick="window.location='...'" en vez de href
    for a in re.findall(r"""(?:href=|location(?:\.href)?\s*=\s*)\\?['"]([^'"#\\]+)\\?['"]""", html):
        destino = urljoin(url, a).split("#")[0]
        if destino.startswith(RAIZ) and destino.endswith((".htm", ".html")):
            salida.append(destino)
    return salida


def pregunta(url: str, html: str) -> dict | None:
    sopa = BeautifulSoup(html, "html.parser")
    titulo = sopa.find(id="div-pregunta")
    if not titulo:
        return None  # es un menú, no una pregunta

    def texto(id_):
        nodo = sopa.find(id=id_)
        return nodo.get_text(" ", strip=True) if nodo else ""

    rastro = [a.get_text(strip=True) for a in sopa.select("#div-rastro a")][1:]  # sin "Menú Principal"
    respuesta = sopa.find(id="div-respuesta")
    for br in respuesta.find_all("br"):
        br.replace_with("\n")
    for bloque in respuesta.find_all(["p", "li", "div", "tr", "h3", "h4", "h5", "table"]):
        bloque.append("\n")  # un párrafo o viñeta por línea, aunque traiga negritas adentro
    for li in respuesta.find_all("li"):
        li.insert(0, "- ")
    lineas = (re.sub(r"[ \t\xa0]+", " ", l).strip() for l in respuesta.get_text("").split("\n"))
    fuentes = re.search(r"despliegaFuentesLi\('(.*?)'\)", html)
    normativa = BeautifulSoup(fuentes.group(1), "html.parser").get_text() if fuentes else ""
    return {
        "id": texto("div-id").removeprefix("ID:").strip(),
        "url": url,
        "categoria": rastro[0] if rastro else "",
        "subtema": " / ".join(rastro[1:]),
        "pregunta": titulo.get_text(" ", strip=True),
        "creada": texto("div-fec-creacion").split(":")[-1].strip(),
        "actualizada": texto("div-fec-actualizacion").split(":")[-1].strip(),
        "respuesta": "\n".join(l for l in lineas if l and l != "-"),
        "normativa": [n.strip() for n in normativa.split("/") if n.strip()],
    }


def bajar(_):
    os.makedirs(PAGINAS, exist_ok=True)
    sesion = requests.Session()
    sesion.headers["User-Agent"] = "Mozilla/5.0 (consulta de preguntas frecuentes, 1 pag/s)"
    vistos, cola, preguntas = set(INICIOS), deque(INICIOS), {}
    while cola:
        url = cola.popleft()
        html = bajar_pagina(sesion, url)
        if not html:
            continue
        p = pregunta(url, html)
        if p:
            preguntas[p["url"]] = p
            if len(preguntas) % 50 == 0:
                print(f"{len(preguntas)} preguntas · {len(cola)} páginas en cola")
        for destino in enlaces(url, html):
            if destino not in vistos:
                vistos.add(destino)
                cola.append(destino)
    with open(JSONL, "w", encoding="utf-8") as f:
        for p in sorted(preguntas.values(), key=lambda p: (p["categoria"], p["subtema"], p["id"])):
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"Listo: {len(preguntas)} preguntas de {len(vistos)} páginas → {JSONL}")


def exportar(_):
    with open(JSONL, encoding="utf-8") as f:
        preguntas = [json.loads(l) for l in f]
    lineas, categoria, subtema = [f"# Preguntas frecuentes del SII ({len(preguntas)})", ""], None, None
    for p in preguntas:
        if p["categoria"] != categoria:
            categoria, subtema = p["categoria"], None
            lineas += [f"## {categoria}", ""]
        if p["subtema"] != subtema:
            subtema = p["subtema"]
            lineas += [f"### {subtema}", ""]
        lineas += [f"#### {p['pregunta']}", "",
                   f"<sub>{p['id']} · actualizada {p['actualizada']} · {p['url']}</sub>", "", p["respuesta"], ""]
        if p["normativa"]:
            lineas += ["Normativa: " + "; ".join(p["normativa"]), ""]
    with open(MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    print(f"{MD}: {len(preguntas)} preguntas")


if __name__ == "__main__":
    comandos = {"bajar": bajar, "exportar": exportar}
    if len(sys.argv) != 2 or sys.argv[1] not in comandos:
        sys.exit(__doc__)
    comandos[sys.argv[1]](sys.argv)
