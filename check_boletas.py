"""
Revisa si una fecha específica ya está disponible para comprar boletas
de una película en cinecolombia.com.

Se investigaron dos posibles señales:

1. La API interna `ocapi/v1/film-screening-dates` — DESCARTADA. Devuelve
   el calendario de PROGRAMACIÓN (qué días habrá función), no si ya se
   puede comprar. Se confirmó en vivo: el 30 de julio ya aparecía en esa
   respuesta mientras el date-picker todavía no lo mostraba como opción.
2. El date-picker que el usuario ve y usa para comprar — CONFIRMADA.
   Solo renderiza los días para los que ya se puede comprar boleta. Esta
   es la señal real.

Por eso el script usa un navegador real para cargar la página y lee
directamente los días visibles en el date-picker
(`.v-date-picker-date__day-of-month`). Esto también evita tener que
replicar el token Bearer (expira cada 12h, lo emite auth.moviexchange.com)
o las cookies de Cloudflare (cf_clearance) — el navegador real las
resuelve solo.

Se usa `patchright` (fork de Playwright con parches anti-detección) en
modo *headed* en vez de `playwright` normal: se confirmó en vivo que
Cloudflare bloquea a Playwright headless (detecta `navigator.webdriver`)
mostrando un challenge interactivo que nunca se resuelve solo. Con
patchright + headed sí se pasa. En CI, "headed" corre sobre un display
virtual (xvfb, ver check-boletas.yml).

Antes de que aparezca el date-picker hay que cerrar un modal
obligatorio de selección de ciudad ("Elige tu ciudad"); sin eso el
date-picker nunca se renderiza. Se usa Cali (`CITY`) como ciudad fija.

Notifica por ntfy.sh (y opcionalmente Telegram) solo la PRIMERA vez que
detecta la fecha disponible, usando estado.json para no repetir el aviso.
"""

import json
import os
import sys
import urllib.request

from patchright.sync_api import sync_playwright

# ---- CONFIGURACIÓN ----------------------------------------------------
FILM_URL = "https://www.cinecolombia.com/films/the-odyssey/HO00000386/"
TARGET_DAY = "30"  # día del mes que estamos esperando (jueves 30 de julio)
CITY = "Cali"
DATE_PICKER_SELECTOR = ".v-date-picker-date__day-of-month"
STATE_FILE = "estado.json"

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")  # ej: cineco-odyssey-xy7k2 (secreto)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
# ------------------------------------------------------------------------


def get_available_days() -> list[str]:
    """Abre la página de la película y devuelve los días visibles en el date-picker."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        try:
            page.goto(FILM_URL, wait_until="domcontentloaded", timeout=30000)

            # Banner de cookies: si aparece, puede tapar el dropdown de ciudad.
            try:
                page.get_by_text("Aceptar", exact=True).click(timeout=5000)
            except Exception:
                pass

            # Modal obligatorio "Elige tu ciudad": sin cerrarlo, el date-picker
            # nunca se renderiza.
            page.get_by_text("Seleccionar...").click(timeout=15000)
            page.locator(".v-dropdown-option__text", has_text=CITY).click(timeout=10000)
            page.get_by_text("Confirmar", exact=True).click(timeout=10000)

            page.wait_for_selector(DATE_PICKER_SELECTOR, timeout=20000)
            days = page.locator(DATE_PICKER_SELECTOR).all_inner_texts()
        except Exception:
            page.screenshot(path="debug_screenshot.png", full_page=True)
            raise
        finally:
            browser.close()
        return [d.strip() for d in days]


def notify(message: str) -> None:
    if NTFY_TOPIC:
        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": "Boletas Cinecolombia"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=15)

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=15)


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"notified": False}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def main() -> None:
    state = load_state()

    try:
        days = get_available_days()
    except Exception as exc:  # el sitio pudo cambiar de estructura, timeout, etc.
        print(f"ERROR revisando la página: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Días visibles en el date-picker: {days}")
    available = TARGET_DAY in days

    if available and not state.get("notified"):
        msg = f"¡Ya se pueden comprar boletas para el {TARGET_DAY}! {FILM_URL}"
        print(msg)
        notify(msg)
        state["notified"] = True
        save_state(state)
    elif available:
        print("Ya disponible, pero ya se había notificado antes. No se reenvía.")
    else:
        print(f"Todavía no aparece el día {TARGET_DAY}. Nada que hacer.")


if __name__ == "__main__":
    main()
