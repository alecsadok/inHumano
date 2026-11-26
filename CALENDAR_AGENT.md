# Agente de actualización del calendario A-List

## Forma de ejecución

Este calendario se actualiza manualmente desde ChatGPT, cuando el usuario escriba, por ejemplo:

- "Ejecutá el agente A-List".
- "Actualizá el calendario A-List".
- "Actualizá los premios y festivales".

No ejecutar el scraping editorial del calendario mediante un cron de GitHub Actions. ChatGPT realiza la investigación web en cada ejecución y actualiza los archivos de este repositorio mediante el conector de GitHub. GitHub Actions solo publica GitHub Pages después de que ChatGPT suba cambios.

## Repositorio y archivos

Repositorio: https://github.com/alecsadok/inHumano

Archivos principales:
- `event_watchlist.yaml`: catálogo de premios, festivales y eventos a monitorear; ampliar con eventos internacionales comparables.
- `events.yaml`: datos confirmados de la edición correspondiente.
- `generate_calendar.py`: generador ICS y formato de descripción.
- `update_events.py`: utilidades de extracción existentes; no asumir que su scraping es correcto sin comprobar los resultados.
- `premios.ics`: calendario publicado en https://alecsadok.github.io/inHumano/premios.ics
- `.github/workflows/pages-deploy.yml`: publica los archivos ya actualizados. No debe hacer scraping programado.

## Criterio editorial y fuentes

1. Priorizar páginas oficiales de organizadores, academias, sindicatos, festivales, cadenas de TV y plataformas.
2. Complementar con medios de noticias reconocidos que informen hechos confirmados y publiquen nombres, horarios o anuncios concretos.
3. Usar Wikipedia como fuente auxiliar para localizar páginas de ceremonias, historiales, nominaciones o fechas; comprobar los datos importantes con fuentes primarias o medios confiables cuando sea posible.
4. No usar rumores, predicciones, fechas tradicionales inferidas, publicaciones de fans ni redes sociales no oficiales.
5. Una fecha de años anteriores no demuestra la fecha de la edición actual. No reutilizar fechas históricas como confirmación.
6. Registrar URL de fuente para cada evento. Para nominaciones y asistencia, guardar también las URL específicas que respaldan esos datos.
7. Cuando las fuentes se contradigan, priorizar la fuente oficial más reciente y explicar la discrepancia en el resumen del trabajo; no elegir silenciosamente una fecha.

## Alcance del calendario

Tomar como base la lista histórica del usuario: Golden Globes, Actor/SAG Awards, anuncios de nominaciones a los Oscars, GRAMMYs, Critics Choice, Super Bowl y Halftime Show, NAACP Image Awards, BRIT Awards, Oscars, Queerties, iHeartRadio Music Awards, GLAAD Media Awards, Coachella, New Orleans Jazz & Heritage Festival, Billboard Music Awards, Met Gala, Rolling Loud, BBC Radio 1 Big Weekend, Nickelodeon Kids' Choice Awards, Governors Ball, Summertime Ball, Bonnaroo, Wango Tango, Glastonbury, Isle of Wight, BET Awards, Tomorrowland, Lollapalooza (Chicago y otras ediciones internacionales, incluida Argentina y Brasil), Chasing Summer, VELD, Outside Lands, Summer Sonic, MTV VMAs, Emmy Awards, iHeartRadio Music Festival, Rock in Rio, Billboard Latin Music Awards, People's Choice Awards, Billboard Women in Music, Jingle Ball, Jingle Bell Ball y Global Citizen.

Buscar e incorporar también premios y festivales internacionales comparables que encajen con el interés del usuario, por ejemplo BAFTA Film/TV, SAG/Actor Awards, Independent Spirit Awards, Satellite Awards, Juno Awards, Premio Lo Nuestro, Latin GRAMMYs, MTV Europe Music Awards, American Music Awards, Cannes, Venice, TIFF y eventos globales de música/pop. Incluirlos solo cuando la edición y su fecha estén confirmadas y tengan cobertura televisiva o streaming oficial, o relevancia internacional equivalente.

No incorporar como eventos activos los premios o festivales discontinuados, cancelados o en pausa indefinida. No agregar eventos sin una edición vigente verificable.

## Información obligatoria

### Ceremonias y premiaciones

- Fecha oficial y hora exacta de inicio/fin cuando se publiquen.
- Zona horaria original identificada con nombre IANA, por ejemplo `America/New_York`, `America/Los_Angeles` o `Europe/London`.
- Canal de TV y streaming oficial, priorizando la señal televisiva cuando exista.
- Red carpet como evento separado únicamente si una grilla oficial de la emisora/organizador confirma programa y horario. No inferir que existe por costumbre.
- Películas, series, programas, álbumes, canciones, artistas o personas con más nominaciones, con cantidades verificadas. Para premios de cine/TV listar títulos y conteos; para premios musicales, artistas/personas y conteos.
- Premios especiales y sus destinatarios confirmados.
- Performers y presentadores anunciados oficialmente.
- Celebridades cuya asistencia esté confirmada por organizadores, emisoras o medios confiables. Incluir estrellas A-list, B-list y argentinos en una sola línea titulada `Celebridades que van:`; no dividirlas en categorías separadas. Diferenciar claramente presentadores, performers y asistentes cuando corresponda.
- No tratar nominados, posibles invitados, anfitriones de red carpet ni artistas del lineup de un festival como asistentes a la ceremonia salvo confirmación explícita.

### Festivales y recitales

- Fechas oficiales; crear entradas por jornada cuando el lineup o la programación se organiza por día.
- Headliners y artistas pop destacados del lineup confirmado.
- Horarios de escenario de headliners y artistas pop cuando el timetable oficial esté publicado.
- Convertir cada horario al huso de Argentina. No estimar set times a partir del orden del cartel.
- Incluir transmisión oficial por TV/streaming cuando esté anunciada. No asumir livestream por ediciones anteriores.
- Incluir artistas argentinos confirmados en el lineup y en la descripción.

### Televisión y eventos en vivo

- Se pueden revisar grillas de ABC, CBS, NBC, FOX, E!, BET, ITV, BBC y otras cadenas relevantes, incluyendo TVPassport, TitanTV y guías equivalentes.
- Las palabras clave `Awards`, `Award`, `Live From`, `Honors` y `Celebration` sirven para descubrir candidatos, no para confirmar por sí solas un evento.
- Incorporar un descubrimiento solo si es un evento especial nuevo/en vivo y la grilla o la emisora confirma fecha, horario y emisión. Excluir repeticiones, episodios regulares, películas y bloques genéricos.
- Las grillas de TV pueden confirmar horario y canal; no bastan por sí solas para confirmar la asistencia de celebridades salvo que el listing identifique expresamente a los invitados.

## Conversión horaria

- Toda fecha/hora del archivo debe quedar en `America/Argentina/Buenos_Aires` (Argentina, GMT-3).
- Convertir desde la zona IANA local usando `zoneinfo`/la base tzdata; no sumar manualmente una cantidad fija de horas.
- Aplicar automáticamente el horario de verano vigente en EE.UU. y otros países. Argentina permanece en GMT-3 para este calendario.
- Si solo está confirmada la fecha y no la hora, crear evento de día completo. No completar horas con horarios habituales ni estimaciones.
- Si la emisión comienza en una fecha local y llega al día siguiente en Argentina, guardar la fecha argentina correcta en DTSTART/DTEND.

## Descripción de cada evento

Usar este orden y omitir líneas sin datos confirmados:

```text
Canal/Streaming: ABC / Disney+
Más nominaciones: Película A (12); Serie B (8); Artista C (7)
Premios especiales: Premio honorífico — Nombre de la distinción: Persona
Performers confirmados: Artista 1; Artista 2
Celebridades que van: Presentadores, invitados y asistentes A-list/B-list/argentinos confirmados
Fuente (evento): https://...
Fuente (nominaciones): https://...
Fuente (performers/premios especiales): https://...
Fuente (celebridades): https://...
```

Para festivales, adaptar el bloque central:

```text
Canal/Streaming: ...
Headliners: ...
Artistas pop destacados: ...
Horarios (Argentina, GMT-3): 21:30 Artista A; 23:00 Artista B
Artistas argentinos: ...
Fuente (evento/lineup): https://...
Fuente (horarios): https://...
```

No incluir las etiquetas `Auto-updated`, `Regla`, `Red carpet:`, `Argentinos confirmados`, `Celebrities A-list confirmadas` ni `Celebrities B-list confirmadas`. La red carpet se identifica en el título del evento separado y su canal/horario va en la descripción.

## Reglas de calidad para el ICS

- Mantener un UID estable por evento para que las actualizaciones no creen duplicados en Google Calendar. No generar un UUID nuevo cada vez para un evento ya existente.
- Escapar correctamente caracteres iCalendar y plegar líneas largas si es necesario.
- Usar DTSTART/DTEND con TZID `America/Argentina/Buenos_Aires` para eventos con hora y VALUE=DATE para eventos sin horario confirmado.
- No publicar un evento sin una URL de fuente del evento (oficial si existe; Wikipedia solo como alternativa cuando no exista página oficial).
- Mantener el histórico confirmado del año objetivo; actualizar los datos que cambien y eliminar o marcar cancelaciones/discontinuaciones con evidencia.
- Antes de terminar, validar sintaxis YAML, ejecutar el generador Python, validar que el ICS contenga BEGIN/END:VCALENDAR y que todos los DTSTART/DTEND con hora estén en huso argentino.
- No inventar nombres, conteos, asistencia, set times, horarios ni fuentes. Si no se confirmó, omitir el dato.

## Procedimiento al ejecutar el agente en ChatGPT

1. Leer las versiones actuales de `event_watchlist.yaml`, `events.yaml`, `update_events.py`, `generate_calendar.py` y el workflow.
2. Investigar la edición del año solicitado en la web. Empezar por fuentes oficiales; usar medios confiables y Wikipedia como apoyo.
3. Comparar lo publicado con el contenido actual para detectar altas, cambios, cancelaciones y datos nuevos.
4. Actualizar `event_watchlist.yaml` si hay nuevos eventos recurrentes relevantes o fuentes oficiales nuevas.
5. Actualizar `events.yaml` con hechos confirmados y URLs fuente.
6. Generar y validar `premios.ics`; mantener IDs/UIDs estables y no duplicar eventos.
7. Escribir los cambios directamente en la rama `main` del repositorio mediante el conector GitHub. No reemplazar archivos no relacionados.
8. El commit que modifique `premios.ics` dispara el workflow de publicación de Pages.
9. Verificar el resultado de GitHub Actions y, si está disponible, que el archivo publicado sea accesible en `https://alecsadok.github.io/inHumano/premios.ics`.
10. Entregar al usuario un resumen de altas/cambios/cancelaciones, señalar cualquier dato que aún no esté anunciado y compartir el enlace permanente del calendario.

La ejecución termina al completar la actualización solicitada. No programar trabajo en segundo plano ni afirmar que el calendario se actualizará solo sin una nueva orden del usuario.
