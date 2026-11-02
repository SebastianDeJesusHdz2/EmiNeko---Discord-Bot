# EmiNeko en tu servidor de Discord

EmiNeko se ejecuta en tu PC. Usa las cuotas gratuitas de los proveedores. Si alcanzas un límite, espera a su renovación. La tienda de cartas usa monedas del juego.

## 1. Instalación desde un clon limpio (Windows)

1. Instala Python 3.12 para Windows con la opción **Add python.exe to PATH**. Abre PowerShell y verifica con `python --version`.
2. Descarga el ZIP del repositorio y descomprímelo o usa Git:

   ```powershell
   git clone https://github.com/SebastianDeJesusHdz2/EmiNeko---Discord-Bot.git
   cd EmiNeko---Discord-Bot
   .\instalar.bat
   ```

   Si elegiste el ZIP, abre su carpeta y ejecuta `instalar.bat` con doble clic. El instalador crea un entorno Python, instala las dependencias (incluido FFmpeg), copia `.env.example` a `.env` si todavía no existe y genera el archivo de configuración local de Playnite.
3. En [Discord Developer Portal](https://discord.com/developers/applications) crea tu propia aplicación o abre la tuya. En **Bot** activa **Server Members Intent** y **Message Content Intent**. Guarda los cambios. Copia el token de la cuenta de bot. Si necesitas restablecerlo, actualiza también las instalaciones que lo usen.
4. Abre `.env` en la raíz del proyecto. Sustituye `PEGA_TU_TOKEN_AQUI` en `DISCORD_TOKEN` por tu token. Puedes dejar vacías las claves de las integraciones que aún no usas. Reinicia el proceso tras editar la configuración.
5. En **Installation** u **OAuth2 URL Generator** selecciona instalación en servidor con los ámbitos `bot` y `applications.commands`. Concede **View Channels, Send Messages, Embed Links, Attach Files, Read Message History, Connect y Speak**. Abre el enlace con una cuenta que pueda invitar aplicaciones al servidor.
6. Ejecuta `iniciar_bot.bat` y mantén la consola abierta. El bot crea su base SQLite y sus carpetas de trabajo. En Discord ejecuta `/inicio` y `/estado`. Usa `/configurar clave:zona_horaria valor:America/Mexico_City` si corresponde a tu servidor.

### Qué se excluye del repositorio y cómo se obtiene

| Archivo o carpeta local | Qué contiene | Cómo se obtiene en otra instalación |
|---|---|---|
| `.env`, variantes, `.secrets/`, claves y certificados | Credenciales, ID de Discord y opciones personales | El instalador crea `.env` desde la plantilla pública. Cada administrador introduce sus valores. |
| `.venv/`, cachés y archivos del editor | El intérprete instalado, paquetes y preferencias del equipo | Ejecuta `instalar.bat`. Python genera sus cachés cuando hagan falta. |
| `*.db`, archivos auxiliares SQLite | Cartas, usuarios, notas, reuniones, bibliotecas y progreso | El primer arranque crea una base vacía. Para trasladar una instalación propia, usa una copia privada con el bot detenido. |
| `data/`, incluida la galería, el bloqueo de instancia y `playnite.json` | Fotos privadas, biblioteca de juegos y estado local | EmiNeko crea la carpeta. Importa tus propias fotos y exporta tu biblioteca según el paso 3. |
| `playnite_bridge/config.json` | Ruta de salida específica del equipo | `preparar_playnite.py` la genera al instalar. Copia después el puente completo a Playnite. |
| `logs/`, `backups/`, volcados, temporales y archivos comprimidos | Diagnóstico y copias que pueden contener datos personales | Se generan localmente. Las copias SQLite aparecen al arrancar cuando ya existe una base. |
| Originales gráficos, paquetes de trabajo y otros archivos nuevos | Recursos locales fuera del conjunto público | El kit público contiene los PNG preparados para Discord. El bot funciona sin los originales. |

La lista permitida de `.gitignore` deja fuera por defecto los archivos nuevos en la raíz y los recursos no seleccionados. Si añades un módulo, revisa su contenido y agrégalo explícitamente a la lista. Git sigue rastreando los archivos que ya estaban versionados aunque después cambies las reglas.

**Primera prueba.** Abre `/tienda`, consulta el precio y pulsa **5 tiradas** si quieres comprarlas con monedas del juego. Comprueba el cambio en `/saldo`. Ejecuta `/tirar` y abre `/coleccion`. Las compras de la tienda se aplican al pulsar su botón. En `/mercado`, comprar una carta de otro jugador sí tiene un segundo paso de confirmación.

**Segunda prueba.** Desde un canal de voz usa `/play` con un enlace público de YouTube que admita reproducción. Escribe `/audio` y pulsa **Pausa** y **Reanudar**. El entorno incluye FFmpeg. `/audio accion:restaurar` recupera la cola guardada al reiniciar. La pausa del video compartido en navegador se controla con `/sala` (paso 5).

**Tercera prueba.** Crea `/recordatorio minutos:1 texto:Prueba de EmiNeko` y comprueba que llegue al mismo canal. Para un aviso diario usa `/recurrente texto:Hora del club horas:24`. `/agenda` muestra tus avisos y permite cancelarlos por ID.

## 2. Qué puedes usar inmediatamente

| Actividad | Dónde empezar |
|---|---|
| Colección y economía | `/diario`, `/saldo`, `/tirar`, `/coleccion`, `/bloquear`, `/favorita`, `/mazo`, `/historial`, `/mercado` |
| Progreso TCG | `/misiones`, `/expedicion`, `/raid accion:atacar`, `/arena`, `/logros`, `/cosmeticos` |
| Juegos del grupo | `/biblioteca accion:agregar`, `/quejuego`, `/encomun`, `/partida`, `/equipo`, `/torneo` |
| Planes y votaciones | `/encuesta`, `/votar`, `/disponibilidad`, `/evento`, `/reunion`, `/tareas` |
| Cine, series y anime | `/cine accion:agregar`, `/quevemos`, `/anime`, `/temporada`, `/album_anime anime_id:ID_MAL` |
| Fotografía | `/foto accion:guardar`, `/foto accion:exif`, `/foto accion:comparar`, `/fotografia accion:reto`, `/concurso` |
| Música | `/play`, `/cola`, `/audio`, `/mezclar`, `/quitar` |
| Memoria | `/memoria`, `/sesion`, `/privacidad`, `/datos` |

`/album_anime` compara tu inventario con el reparto consultado en Jikan. Completar un reparto da una insignia y 50 cristales una sola vez. `/arena` normaliza los tres enfrentamientos por elementos y actualiza la clasificación mensual. `/batalla` conserva el modo interactivo por turnos. En `/raid` cada persona puede atacar una vez por hora. Tras vencer al jefe diario, los participantes usan `/raid accion:reclamar` antes del cambio de día UTC. `/logros` evalúa los requisitos, concede cristales y registra las insignias. `/cosmeticos` compra y equipa títulos de perfil.

Para organizar una noche, usa `/disponibilidad accion:crear horarios:Viernes 20h|Sábado 18h`. Cada persona vota con `accion:votar`, el ID y opciones como `1,2`. Con el horario elegido crea `/evento accion:crear titulo:Noche de juegos fecha:2027-01-15T20:00:00-06:00 plazas:4`. Sustituye la fecha por la de tu reunión. Los invitados usan `accion:unirme` con el ID. Las plazas sobrantes pasan a espera y avanzan cuando alguien sale. Usa `accion:acuerdos` para guardar notas. Emi avisa en el canal diez minutos antes. Para una votación de una sola opción usa `/encuesta` y `/votar`.

## 3. Tus bibliotecas de Steam, Epic Games, GOG, Xbox e itch.io

**Para importar tus plataformas desde este PC**

1. Instala [Playnite](https://playnite.link/). Añade las integraciones de biblioteca Steam, Epic Games, GOG, Xbox e itch.io desde sus complementos. Inicia sesión en cada proveedor a través de Playnite y actualiza sus bibliotecas. Verifica qué juegos aparecen allí antes de continuar. La cobertura de cada cuenta depende de su integración y permisos.
2. Cierra Playnite. Copia la carpeta `playnite_bridge` de este proyecto, **incluido `config.json`**, a la carpeta `Extensions` de Playnite. En una instalación estándar de Windows suele estar en `%APPDATA%\Playnite\Extensions`. En una instalación portable usa `Extensions` dentro de su carpeta. Abre Playnite de nuevo. Si cambias el proyecto de ubicación, ejecuta `preparar_playnite.py` con el Python de `.venv` y vuelve a copiar la carpeta.
3. En el menú de extensiones de Playnite, abre **EmiNeko → Exportar biblioteca a EmiNeko**. Comprueba que existe `data/playnite.json`. La extensión vuelve a exportar al actualizar la biblioteca o al terminar de jugar. [API de scripts de Playnite](https://api.playnite.link/docs/tutorials/extensions/scripting.html) · [Eventos de biblioteca](https://api.playnite.link/docs/tutorials/extensions/events.html).
4. Ejecuta `vincular_playnite.bat` en el PC de EmiNeko. Activa el modo desarrollador en Discord, haz clic derecho en tu propio perfil y elige **Copiar ID de usuario**. Pega ese número en la consola. La herramienta importa los juegos y guarda el destino privado. Si cambiaste la ubicación del JSON, indica su ruta en `PLAYNITE_EXPORT_PATH` dentro de `.env` antes de vincular.
5. Abre `/biblioteca` para ver el total y las páginas. Para ver una tienda usa `/biblioteca detalle:Epic` o `/biblioteca detalle:itch`. Primero actualiza las bibliotecas en Playnite y vuelve a exportar para incluir los juegos recién añadidos. El bot comprueba el archivo al abrir la biblioteca vinculada y también en segundo plano. Para una importación puntual puedes usar `/importar_juegos archivo:` con el JSON. Las actualizaciones identifican juegos por ID y conservan el progreso que anotaste en Discord. Usa `/encomun usuario:@amigo` para compartir coincidencias si la otra persona acepta. Confirma plataforma y juego cruzado al preparar la partida.

Si obtener una clave te exige gastar dinero en tu cuenta, usa la importación con Playnite.

**Para importar Steam directamente** también puedes obtener una [Steam Web API key](https://steamcommunity.com/dev/apikey), guardarla como `STEAM_API_KEY`, reiniciar y usar `/steam steamid:TU_STEAMID64`. Los detalles de juegos deben ser visibles para la consulta. Elige una vía principal para Steam porque Playnite y Steam utilizan identificadores de importación diferentes. [Referencia de Valve](https://partner.steamgames.com/doc/webapi/IPlayerService).

## 4. Cine, series y alertas

1. Entra a [TMDB](https://www.themoviedb.org/settings/api), solicita el acceso de desarrollador gratuito para uso personal no comercial y copia **API Read Access Token** en `TMDB_TOKEN` de `.env`. Reinicia el bot. Para mostrar el logotipo oficial en `/creditos` puedes guardar la imagen aprobada como `assets/tmdb.png`. [Registro de TMDB](https://developer.themoviedb.org/docs/getting-started).
2. Prueba `/buscar_cine busqueda:Alien tipo:pelicula`. Copia el ID de la película correcta. Ejecuta `/buscar_cine tipo:pelicula guardar:ID` para guardarla y `/dondever identificador:ID tipo:pelicula pais:MX` para consultar proveedores regionales. Para series elige `tipo:serie`. Los datos de disponibilidad proceden de JustWatch mediante TMDB. [Proveedores por región](https://developer.themoviedb.org/reference/movie-watch-providers).
3. Actualiza el **ID local** en `/cine accion:estado identificador:ID_LOCAL detalle:visto`. Usa el ID de TMDB solo para las consultas externas. `/quevemos` selecciona hasta tres títulos pendientes.
4. Para seguir cambios usa `/alertas accion:crear tipo:pelicula objetivo:ID_TMDB` o `tipo:serie`. La primera consulta establece una referencia. Los cambios posteriores generan un mensaje privado. El estreno de película se basa en la fecha publicada por TMDB. Para series se sigue la ficha del capítulo próximo o del más reciente.
5. Para precios usa `/alertas accion:buscar objetivo:Terraria`, copia el `gameID` y crea `/alertas accion:crear tipo:precio objetivo:GAMEID limite:5`. Los importes son **USD**. El bot revisa las alertas aproximadamente cada hora y envía el enlace de CheapShark cuando corresponde. Habilita mensajes privados del bot. `/alertas` muestra errores de consulta o entrega. [API de CheapShark](https://apidocs.cheapshark.com/).

## 5. Sala de video sincronizada

1. Para probar en el mismo PC, guarda estas variables en `.env` y reinicia. El servicio escucha en la interfaz local.

   ```dotenv
   EMI_WEB_ENABLED=1
   EMI_WEB_HOST=127.0.0.1
   EMI_WEB_PORT=8765
   EMI_WEB_PUBLIC_URL=http://127.0.0.1:8765
   ```

2. Usa `/sala accion:crear url:URL_DE_UN_VIDEO_YOUTUBE`. Abre el enlace de la respuesta privada y pulsa **Entrar a la sala**. El anfitrión usa `/sala accion:reanudar`, `/sala accion:pausa` y `/sala accion:ir segundos:90`. El navegador permite activar sonido mediante el botón. Los clientes comprueban la posición cada dos segundos.
3. Para un ensayo con amigos fuera de tu red, instala `cloudflared` siguiendo la [guía oficial de túneles temporales](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/). Ejecuta `cloudflared tunnel --url http://127.0.0.1:8765`. Copia la dirección HTTPS que aparece en `EMI_WEB_PUBLIC_URL`, reinicia EmiNeko y mantén el túnel abierto. Vuelve a pedir `/sala accion:enlace` y comparte el enlace completo, incluido el fragmento después de `#`. El túnel temporal funciona mientras mantengas abierta esa consola.
4. `/sala accion:cerrar` invalida el enlace. La sala vence automáticamente tras 24 horas. El control afecta a quienes abran ese reproductor. Pantallas compartidas y ventanas independientes siguen bajo el control de quien las abrió. [Reproductor oficial de YouTube](https://developers.google.com/youtube/iframe_api_reference).

## 6. Memoria y fotografía en tu equipo

1. Guarda una nota con `/memoria accion:agregar titulo:Gustos detalle:Prefiero los cooperativos`. Escribe `/preguntar pregunta:cooperativos` para recuperar las coincidencias por título o contenido.
2. Abre `/sesion accion:crear titulo:Proyecto` en un canal. Cada persona que quiera guardar sus mensajes usa `accion:aceptar identificador:ID`. Al terminar usa `accion:cerrar`. Los participantes autorizados pueden consultar los mensajes recientes con `/resumen sesion:ID`. Con `accion:retirar` pueden eliminar sus aportaciones. Sin ID, `/resumen` repasa tus registros personales de la semana. Ambas consultas usan la base local.
3. Para guardar una foto usa `/foto accion:guardar archivo:FOTO titulo:Retrato`. Puedes consultar sus datos técnicos con `accion:exif`, abrir tu copia con `accion:abrir` o comparar dos fotos con `accion:comparar`. El bot guarda la copia sin coordenadas GPS incrustadas.
4. Crea un concurso con `/concurso accion:crear titulo:Sombras horas:24`. Cada participante puede compartir una foto propia con `accion:participar` y los demás pueden votar con `accion:votar`.

## 7. Operación, copias y solución de problemas

- Ejecuta `diagnostico.bat` para comprobar dependencias, audio y presencia de configuración sin mostrar claves. `/estado` hace una comprobación de configuración dentro de Discord. Un indicador configurado requiere la prueba del comando correspondiente para confirmar que el proveedor acepta la cuenta.
- El lanzador guarda hasta 14 copias SQLite en `backups` y registra errores en `logs/emineko.log`. Para una copia manual ejecuta `.\.venv\Scripts\python.exe emi_runtime.py`. Respalda también `data/photos` si quieres conservar las imágenes. La base contiene su catálogo. Guarda `.env` y `.secrets` en un lugar privado. Si usas una carpeta sincronizada, comprueba quién puede acceder a las copias locales.
- Para restaurar, detén el bot, guarda aparte la base actual y copia la versión deseada sobre el archivo indicado por `BOT_DB_PATH`. Reinicia con `iniciar_bot.bat`. Los recordatorios pendientes se reanudan al volver a conectar.
- `/datos accion:exportar` entrega un JSON privado. `/datos accion:borrar` pide confirmación antes de eliminar notas, imágenes guardadas y avisos. Conserva el progreso y las operaciones de economía. Si habilitaste el puente Playnite, desactiva su sincronización para evitar importar nuevamente la biblioteca.
- Si Discord muestra `PrivilegedIntentsRequired`, revisa los dos intents del paso 1. Si no ves comandos, comprueba que el bot está conectado, que fue instalado con `applications.commands` y que tu rol puede usar comandos en el canal. Revisa el registro de sincronización global.
- Si falla un video, prueba otra URL pública que admita inserción, comprueba `/estado` y actualiza `yt-dlp` dentro de `.venv` si cambió YouTube. Para reproducción remota conserva tanto el bot como el túnel en ejecución.
- Si una conexión devuelve 401/403, revisa el proveedor indicado, la cuenta autorizada y los permisos. Si una alerta no llega, revisa `/alertas` y permite mensajes directos.
- Para repetir las pruebas locales ejecuta `verificar.bat`. Las pruebas usan bases separadas. Las comprobaciones reales de Discord, sincronización de cuentas y reproducción con invitados se completan con tus permisos y contenido.

Todos los comandos que registra esta instalación están en [COMANDOS.md](COMANDOS.md).
