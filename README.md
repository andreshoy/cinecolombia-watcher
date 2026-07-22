# cinecolombia-watcher

Revisa cada 10 minutos si una fecha específica ya está disponible para
comprar boletas de una película en cinecolombia.com, y te notifica por
ntfy.sh y/o Telegram apenas aparece.

## Cómo funciona

El sitio es una SPA (Vue/Vuetify) — el HTML del servidor viene vacío y el
date-picker se renderiza con JavaScript. Por eso el script usa Playwright
para abrir la página real, esperar a que cargue el date-picker, y revisar
si el número de día que buscas (`TARGET_DAY`) aparece entre los spans
`.v-date-picker-date__day-of-month`.

Guarda el resultado en `estado.json` (commiteado al repo) para no
mandarte la misma notificación cada 10 minutos una vez que ya esté
disponible.

## Setup

1. Crea un repositorio en GitHub y sube estos archivos (respeta la
   carpeta `.github/workflows/`).
2. **Recomendado: hazlo repo público.** Los minutos de GitHub Actions son
   ilimitados en repos públicos; en repos privados el plan gratuito da
   2000 min/mes, y correr un navegador headless cada 10 min durante
   varios días puede acercarse a ese límite.
3. Configura la notificación (elige una o ambas):

   **ntfy.sh (más simple, sin registro):**
   - Piensa un "topic" único y difícil de adivinar, ej. `cineco-odyssey-x7k2p9`.
   - En tu celular, instala la app ntfy o abre `https://ntfy.sh/tu-topic` en el navegador y suscríbete.
   - En GitHub: Settings → Secrets and variables → Actions → New repository secret.
     - Nombre: `NTFY_TOPIC` — Valor: `cineco-odyssey-x7k2p9`

   **Telegram (opcional, además o en vez de ntfy):**
   - Crea un bot con [@BotFather](https://t.me/BotFather), copia el token.
   - Escríbele algo a tu bot y consulta tu `chat_id` con
     `https://api.telegram.org/bot<TOKEN>/getUpdates`.
   - Agrega los secrets `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.

4. Ajusta si hace falta en `check_boletas.py`:
   - `FILM_URL`: la URL de la película.
   - `TARGET_DAY`: el día del mes que esperas (ojo: solo el número, ej. `"30"`).
5. Prueba manualmente desde la pestaña **Actions → check-boletas → Run workflow**
   antes de dejarlo en automático, para confirmar que todo corre bien.

## Por qué usa el date-picker y no una API interna

Se investigaron dos APIs internas de `digital-api.cinecolombia.com`:

- **`film-screening-dates`** — descartada. Se comprobó en vivo que
  devuelve el calendario de *programación* (qué días habrá función),
  no si ya se puede comprar: el 30 de julio ya aparecía en esa
  respuesta varios días antes de que el date-picker lo mostrara como
  opción real de compra.
- **`showtimes/by-business-date/...`** — la señal real (trae horarios
  específicos), pero requiere un token Bearer emitido por
  `auth.moviexchange.com` que **expira cada 12 horas**, y el sitio está
  detrás de **Cloudflare** (`cf_clearance`), que normalmente solo se
  resuelve con un navegador real ejecutando JavaScript.

Por eso el script usa un navegador real (Playwright) y lee directamente
el date-picker que ve cualquier usuario — es la señal que se confirmó
como confiable, y de paso el navegador resuelve solo el token y el
challenge de Cloudflare sin que el script tenga que manejarlos.

## Notas / cosas a vigilar

- Si Cinecolombia cambia el nombre de la clase CSS del date-picker, el
  selector `DATE_PICKER_SELECTOR` va a dejar de funcionar y el script
  fallará (verás el error en los logs de Actions). Si pasa, hay que
  volver a inspeccionar el HTML y actualizar el selector.
- El cron de GitHub Actions es "best effort": en momentos de alta carga
  puede haber minutos de retraso.
- **Nunca commitees tokens, cookies o headers de tu sesión al repo** —
  ni siquiera aunque el repo sea privado. No hace falta: el script no
  necesita ninguno, los obtiene solo en cada corrida.
