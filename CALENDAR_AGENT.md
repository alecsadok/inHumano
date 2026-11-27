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

Deadline sirve como mapa editorial transversal para descubrir y ordenar fechas de la temporada de premios (Oscars, Emmys, Golden Globes y otras ceremonias cubiertas). Consultar su calendario al iniciar cada investigación y revisar sus actualizaciones. Usarlo como fuente secundaria de descubrimiento y planificación, nunca como confirmación final: verificar cada fecha, hora, canal/streaming y cambio con la academia, organizador o cadena correspondiente. Si Deadline y una fuente primaria difieren, prevalece la fuente primaria más reciente; conservar la URL de Deadline como referencia auxiliar.

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


## Reglas específicas de la ejecución solicitada

- El disparador literal principal es «Ejecutar». Cada orden inicia una investigación nueva y una actualización real del repositorio; no ejecuta cron ni trabajo en segundo plano.
- Usar como mapa de temporada de premios el calendario de Deadline: https://deadline.com/feature/awards-season-calendar-oscars-emmys-golden-globes-list-1234814076/. Deadline sirve para descubrir y ordenar ceremonias; no basta como prueba de fecha, horario, nominaciones o distribución. En la ejecución del 26/11/2026 la página devolvió error 402 (acceso restringido), por lo que se contrastó con fuentes primarias y medios confiables.
- Regla de inclusión: un evento entra al ICS únicamente si tiene fecha de edición confirmada y transmisión de TV o streaming confirmada para esa edición. Una fecha confirmada sin emisión confirmada permanece en la watchlist y no se publica. Nunca asumir que un canal/plataforma de años anteriores vuelve a transmitir.
- La descripción de cada evento debe incluir «Canal/Streaming:» y enumerar solo las señales/plataformas confirmadas para esa edición. No usar expresiones como «según cobertura anual» para dar por confirmada una transmisión.
- Premios: agregar «Más nominaciones:» con películas, series, álbumes, canciones, artistas o personas y cantidades oficiales disponibles. Incluir conductores, presentadores, performances, premios especiales y asistentes solo cuando estén anunciados. Si las nominaciones no fueron publicadas, omitir el bloque.
- Festivales/conciertos: crear una entrada por día cuando el lineup se organice por jornadas; incluir lineup del día, headliners, transmisión y fuentes. Convertir horarios de sets únicamente cuando se publique el timetable; nunca deducirlos del orden del cartel.
- Si no se anunció la hora, crear evento de día completo. Si solo se anunció el comienzo, usar DTSTART sin inventar duración ni finalización.
- Conservar zona IANA original (`tz_local`) y convertir con tzdata a `America/Argentina/Buenos_Aires` (UTC-3), incluyendo el horario de verano de origen. La descripción expresa siempre la hora argentina.
- Mantener histórico y UIDs estables; no generar duplicados. No modificar `talkshow-guests.ics` ni archivos ajenos a este calendario.
- Luego del commit, revisar GitHub Actions y abrir https://alecsadok.github.io/inHumano/premios.ics para comprobar que Pages publicó el archivo. Un commit exitoso no equivale a publicación verificada.
- Mantener en watchlist los eventos históricos, pausados o discontinuados (marcados inactivos), pero no publicarlos hasta que exista una edición vigente y una emisión confirmada.
- Catálogo a vigilar: Golden Globes; SAG/Actor Awards; anuncios de nominaciones Oscar; GRAMMYs; Critics Choice; Super Bowl/Halftime Show; NAACP Image Awards; BRIT Awards; Oscars; Queerties; iHeartRadio Music Awards; GLAAD; Coachella; New Orleans Jazz & Heritage; Billboard Music Awards; Met Gala; Rolling Loud; BBC Radio 1 Big Weekend; Kids' Choice; Governors Ball; Summertime Ball; Bonnaroo; Wango Tango; Glastonbury; Isle of Wight; BET Awards; Tomorrowland; Lollapalooza Argentina/Chicago/Brasil; Chasing Summer; VELD; Outside Lands; Summer Sonic; MTV VMAs; Emmy Awards (incluidos Creative Arts); iHeartRadio Music Festival; Rock in Rio; Billboard Latin Music Awards; People's Choice; Billboard Women in Music; Jingle Ball/Jingle Bell Ball; Global Citizen; BAFTA Film/TV; Independent Spirit; Satellite; JUNO; Premio Lo Nuestro; Latin GRAMMYs; MTV EMAs; AMAs; Cannes; Venice; TIFF; iHeart Summer Pool Party; B96 Jingle Bash.


## Verificación de televisión: guías y grillas

Usar **TV Passport** (https://www.tvpassport.com/tv-listings) y **TitanTV** (https://www.titantv.com/) de forma sistemática para descubrir eventos televisivos nuevos/en vivo, detectar títulos no incluidos en la watchlist y obtener horarios de emisión. No limitar la consulta a los eventos ya conocidos: revisar grillas de cadenas y señales relevantes para encontrar especiales, anuncios de nominaciones, ceremonias, galas, tributos y otros eventos que cumplan el alcance editorial.

### TV Passport: etiquetas y lectura de grilla

- Revisar las páginas de programación de la estación/señal concreta y la fecha exacta. Para cadenas nacionales estadounidenses, priorizar señales **East / Eastern** cuando estén disponibles; verificar siempre el nombre completo de la estación y el huso que muestra la página.
- En TV Passport, tratar las etiquetas **“New”** y **“Live”** como indicadores positivos de descubrimiento: señalan que la emisión es nueva y/o en vivo. Registrar cuál de las dos aparece. Si aparecen ambas, es una señal especialmente fuerte para investigar e incorporar el evento, siempre que cumpla el alcance editorial.
- La etiqueta **“Repeat”** (o una indicación equivalente de repetición) es motivo de exclusión, salvo que se trate de una nueva emisión en vivo distinta y comprobable. No confundir una descripción que menciona “live” dentro de la sinopsis con la etiqueta de estado de la emisión.
- Si la extracción de la página no devuelve las etiquetas visuales, inspeccionar la página renderizada o la grilla original antes de concluir que no están presentes. No interpretar la ausencia de una etiqueta en una extracción de texto como prueba de que la emisión no es nueva/en vivo.
- Ejemplo de detección: la grilla de E! Entertainment USA HD - East del 4/12/2026 muestra a las 9:00 AM el anuncio en vivo de nominaciones seleccionadas de los **32nd Annual Critics Choice Awards**. La ficha debe revisarse por sus marcas “New” y “Live” y contrastarse con la organización/cadena. Al ser una grilla East/Eastern en diciembre (EST, UTC−5), las 9:00 AM equivalen a **11:00 en Argentina (UTC−3)**. URL: https://www.tvpassport.com/tv-listings/stations/e-entertainment-usa-hd-east/6659/2026-12-04.

### TitanTV y contraste

- Usar TitanTV como segunda guía de detección y cotejo de fecha, título, señal y hora. Consultar el lineup/mercado correspondiente; no asumir que una grilla local representa a todas las filiales.
- Comparar TV Passport y TitanTV cuando ambas publiquen la emisión. Una diferencia de horario puede deberse a zona, proveedor, estación o actualización; resolverla con la página oficial de la cadena/organizador más reciente.
- Las guías pueden descubrir y corroborar la hora/canal, pero no confirman por sí solas derechos de streaming, invitados, performers, nominaciones ni asistencia de celebridades.

### Reglas de inclusión

- Las etiquetas “New” y “Live” habilitan la investigación, pero no sustituyen la verificación editorial. Incorporar solo eventos especiales nuevos/en vivo, anuncios de premios o nominaciones, galas, ceremonias, tributos, especiales originales de una sola emisión y programación-evento confirmada.
- Excluir repeticiones, episodios regulares, películas, maratones, bloques genéricos de programación y títulos que solo ingresan a un catálogo de streaming. No agregar un programa solo porque aparece en una grilla.
- Para cada candidato, verificar título, fecha, hora, canal y naturaleza de la emisión con la cadena, organizador o fuente oficial más reciente. Si no se puede verificar si es nuevo/en vivo, dejarlo como candidato pendiente y no publicarlo en el ICS.
- Guardar la URL específica de la grilla consultada y la URL oficial que confirma el evento. Las guías son fuentes de detección/cotejo, no sustitutos de la fuente primaria.

### Conversión horaria de grillas

- Registrar el huso horario que corresponde a la estación y a la opción seleccionada en la guía. Para señales estadounidenses East/Eastern, usar `America/New_York`; en diciembre corresponde EST (UTC−5), mientras que durante el horario de verano corresponde EDT (UTC−4).
- Convertir cada hora con la base IANA/tzdata a `America/Argentina/Buenos_Aires` (UTC−3). No aplicar una diferencia fija durante todo el año ni confundir ET con EST: ET cambia entre EST y EDT.
- Mantener la fecha local correcta después de la conversión; si el cambio de huso cruza la medianoche, guardar la fecha argentina resultante.
