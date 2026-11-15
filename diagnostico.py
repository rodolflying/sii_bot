"""
Diagnóstico de solo lectura de la situación de una empresa en el SII.

  python diagnostico.py

Abre Chrome con un perfil propio (.perfil_sii), inicia sesión con USER_NAME_SPA y PASSWORD_SPA del .env
(si no están, espera a que entres a mano) y recorre Mi SII y las consultas de estado: anotaciones,
visitas, F22, F29, término de giro, Registro de Compras y Ventas, notificaciones.
Solo navega a páginas: no hace clic en nada fuera del login, así que no declara, paga ni envía nada.

Por cada página guarda en diagnostico/<fecha>/ el texto visible, una captura y los JSON que el SII
le manda a la página (ahí vienen los datos de las apps nuevas), más un indice.md para revisar.
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

APP = Path(__file__).resolve().parent
PERFIL = APP / ".perfil_sii"  # tu sesión del SII: no copiar ni compartir
SALIDA = APP / "diagnostico" / datetime.now().strftime("%Y-%m-%d_%H%M")
LOGIN = "https://zeusr.sii.cl//AUT2000/InicioAutenticacion/IngresoRutClave.html?https://misiir.sii.cl/cgi_misii/siihome.cgi"
MI_SII = "https://misiir.sii.cl/cgi_misii/siihome.cgi"
MAX_PAGINAS = 60
PAUSA = 3

# Puntos de partida conocidos; el resto se descubre desde los menús
INICIOS = [
    MI_SII,
    "https://www.sii.cl/servicios_online/",
    "https://www4.sii.cl/consultaestadof22ui/",
    "https://www4.sii.cl/sifmConsultaInternet/index.html?dest=cifxx&form=29",
    "https://www4.sii.cl/rfiInternet/consulta/index.html#rfiSelFormularioPeriodo",
    "https://www4.sii.cl/consdcvinternetui/",
]
INTERES = re.compile(r"anotaci|visita|t[ée]rmino de giro|continuidad|cese|estado de (la )?declaraci|formulario 22|"
                     r"\bf22\b|consulta integral|f29|compras y ventas|declaraciones? juradas?|notificaci|situaci[óo]n tributaria|"
                     r"carpeta tributaria|r[ée]gimen|datos personales|timbraje|folios|giros|deuda|mandat|domicilio|"
                     r"representante|socios|peticiones administrativas|observ", re.I)
# Nada que pueda cambiar algo: aunque solo se navega, mejor ni entrar a estas páginas
EVITAR = re.compile(r"pagar|\bpago\b|enviar|firmar|cerrar sesi|salir|rectific|\bdeclarar\b|eliminar|anular|"
                    r"solicitar|modificar|actualizar", re.I)


def nombre(url: str, i: int) -> str:
    p = urlparse(url)
    return f"{i:02d}_{re.sub(r'[^a-zA-Z0-9]+', '_', p.netloc.split('.')[0] + p.path + p.fragment)[:70]}"


def sesion_iniciada(page) -> bool:
    return "AUT2000" not in page.url and "sii.cl" in page.url


def entrar(page):
    page.goto(LOGIN)
    page.wait_for_load_state("networkidle")
    if sesion_iniciada(page):
        return print("Sesión ya iniciada.")
    env = dotenv_values(APP / ".env")
    if env.get("USER_NAME_SPA") and env.get("PASSWORD_SPA"):
        page.fill("#rutcntr", env["USER_NAME_SPA"])
        page.fill("#clave", env["PASSWORD_SPA"])
        page.click("#bt_ingresar")
    else:
        print("No hay credenciales en .env: inicia sesión en la ventana de Chrome (tienes 3 minutos).")
    page.wait_for_url(lambda u: "AUT2000" not in u, timeout=180_000)
    page.wait_for_load_state("networkidle")
    print("Sesión iniciada.")


def enlaces(page) -> list[tuple[str, str]]:
    salida = []
    for a in page.query_selector_all("a[href]"):
        href, texto = a.get_attribute("href") or "", (a.inner_text() or "").strip()
        url = page.evaluate("h => new URL(h, location.href).href", href) if not href.startswith("javascript") else ""
        if ".sii.cl" in urlparse(url).netloc and INTERES.search(texto + " " + url) and not EVITAR.search(texto):
            salida.append((url, re.sub(r"\s+", " ", texto)[:80]))
    return salida


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PERFIL, channel="chrome", headless=False,
                                                   viewport={"width": 1366, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        respuestas = []

        def guardar_json(resp):
            try:
                if ".sii.cl" in resp.url and resp.request.resource_type in ("xhr", "fetch"):
                    cuerpo = resp.text()
                    if cuerpo.lstrip()[:1] in ("{", "["):
                        respuestas.append({"url": resp.url, "metodo": resp.request.method, "cuerpo": cuerpo})
            except Exception:
                pass

        page.on("response", guardar_json)
        entrar(page)

        cola = [(u, "inicio") for u in INICIOS]
        vistos, indice = set(), []
        while cola and len(vistos) < MAX_PAGINAS:
            url, origen = cola.pop(0)
            clave = url.split("?")[0] if "#" not in url else url
            if clave in vistos:
                continue
            vistos.add(clave)
            i = len(vistos)
            respuestas.clear()
            try:
                page.goto(url, timeout=45_000)
                page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception as e:
                print(f"[{i}] no cargó {url}: {str(e)[:80]}")
            time.sleep(PAUSA)  # las apps del SII terminan de pintar después del networkidle
            base = SALIDA / nombre(url, i)
            texto = page.inner_text("body") if page.query_selector("body") else ""
            base.with_suffix(".txt").write_text(f"URL: {page.url}\nTítulo: {page.title()}\n\n{texto}", encoding="utf-8")
            page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
            if respuestas:
                base.with_suffix(".json").write_text(json.dumps(respuestas, ensure_ascii=False, indent=1), encoding="utf-8")
            nuevos = [(u, t) for u, t in enlaces(page) if u not in vistos]
            cola += nuevos
            resumen = re.sub(r"\s+", " ", texto)[:250]  # Python 3.10 no acepta \ dentro de un f-string
            indice.append(f"- **{page.title() or '(sin título)'}** · desde «{origen}» · {page.url}\n"
                          f"  `{base.name}` · {len(texto)} caracteres · {len(respuestas)} JSON\n"
                          f"  > {resumen}")
            print(f"[{i}] {page.title()[:60]} · {len(respuestas)} JSON · +{len(nuevos)} enlaces")
        ctx.close()

    (SALIDA / "indice.md").write_text(f"# Diagnóstico SII {SALIDA.name}\n\n" + "\n".join(indice), encoding="utf-8")
    print(f"\nListo: {len(vistos)} páginas en {SALIDA}")


if __name__ == "__main__":
    main()
