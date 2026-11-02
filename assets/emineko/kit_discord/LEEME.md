# EmiNeko · Kit para Discord Developers

## Emojis de aplicación

En **Emojis → Subir un emoji**, selecciona los PNG de la carpeta `emojis`. Usa como nombre el del archivo sin la extensión. Cada imagen está preparada para 128 × 128 píxeles.

| Nombre | Reacción |
|---|---|
| `emi_hola` | Saludar a alguien que llega |
| `emi_corazon` | Agradecer o dar cariño |
| `emi_risa` | Reírse de una ocurrencia |
| `emi_llora` | Lamentar una derrota |
| `emi_gg` | Celebrar una buena partida |
| `emi_sorpresa` | Reaccionar a una tirada inesperada |

Si más adelante quieres que Emi los envíe en sus respuestas, copia el ID asignado por Discord a cada emoji. El formato de un emoji estático en un mensaje de la aplicación es `<:nombre:ID>`.

## Imágenes de Rich Presence

En **Rich Presence → Recursos → Añadir imagen(es)** sube los archivos de `rich_presence`. Comprueba las claves antes de guardar. El portal puede tardar en mostrarlas por la caché.

| Clave | Papel en la tarjeta |
|---|---|
| `emi_club` | Ilustración principal del club de cartas |
| `emi_insignia` | Emblema pequeño de actividad |

## Visualizador · una tarde con Emi

| Campo de tu captura | Valor |
|---|---|
| **state** | `En el club de cartas` |
| **details** | `Preparando mi mazo con Emi` |
| **start Timestamp** | Vacío |
| **end Timestamp** | Vacío |
| **large Image Key** | Selecciona `emi_club` |
| **large Image Text** | `EmiNeko · Una tarde en el club` |
| **small Image Key** | Selecciona `emi_insignia` |
| **small Image Text** | `Coleccionista de cartas` |
| **party Id** | Vacío |
| **party Size** | Vacío |
| **party Max** | Vacío |
| **join secret** | Vacío |

Borra los tiempos y los datos de grupo que vienen en el ejemplo. Así evitas mostrar una cuenta atrás en cero o un grupo ficticio. En **Perfil completo**, comprueba la composición y pasa el cursor sobre ambas imágenes para revisar sus textos. La imagen pequeña se superpone a la esquina de la grande.

El visualizador sirve para previsualizar una actividad en el perfil de una persona. Mostrarla en vivo requiere una integración de Rich Presence en una aplicación cliente. La presencia de la cuenta del bot por Gateway admite un conjunto de campos más limitado. Subir los recursos prepara el catálogo y no cambia por sí solo el estado público del bot.

[Rich Presence de Discord](https://docs.discord.com/developers/rich-presence/overview) · [Campos de actividad del bot](https://docs.discord.com/developers/events/gateway-events#activity-object) · [Emojis de aplicaciones](https://docs.discord.com/developers/resources/emoji)
