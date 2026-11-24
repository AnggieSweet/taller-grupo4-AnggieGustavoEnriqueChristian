# Evidencias de ejecución: agente AlgoMarket (Gustavo Hormazábal)

Todas las pruebas se hicieron en **LOCAL** (computador del estudiante), no en producción.
Las claves, tokens y chat_id están ocultos en las capturas. Los datos de productos son inventados.

Cómo se ejecutó: agente AlgoMarket (puerto 8005) y API (puerto 8010) levantados según el README; consultas hechas a `POST /chat` desde Swagger (`/docs`) con la cabecera `X-API-Key`. Solo estaba levantado el agente AlgoMarket (catálogo con 1 agente).

## Pruebas automáticas

| Dato | Registro |
|---|---|
| Entorno y fecha | LOCAL, 22/11/2026 |
| Solicitud | `pip install -r requirements.txt` y `python -m pytest tests/test_algomarket_tools.py -q`; luego `python -m pytest tests -q` |
| Resultado esperado | Todas las pruebas pasan (AlgoMarket y API) |
| Resultado obtenido | Instalación sin errores. Solo AlgoMarket: 11 passed. Repo con los pull requests #1 y #2 mezclados: 18 passed, 1 skipped. Pruebas de la API (rama `api-fallas-agente`): 7 passed, 1 skipped. Con las pruebas de `texto.py` incluidas (ejecución final): **23 passed, 1 skipped** |
| Observaciones | Python 3.12; el README recomienda 3.13 y 3.12 también funcionó. El «skipped» es una prueba del repo que se omite sola. Capturas: [01-pytest-algomarket.png](capturas-algomarket/01-pytest-algomarket.png), [01b-pytest-completo.png](capturas-algomarket/01b-pytest-completo.png), [11a-pytest-api-fallas.png](capturas-algomarket/11a-pytest-api-fallas.png), [12-pytest-final.png](capturas-algomarket/12-pytest-final.png) (23 passed, 1 skipped) |

## Casos de la API (agente AlgoMarket)

### Caso 1: producto con precio, unidad y oferta

| Dato | Registro |
|---|---|
| Entorno y fecha | LOCAL, 22/11/2026 21:30 |
| Solicitud | «¿Cuánto cuesta la leche y en qué pasillo está?» |
| Resultado esperado | Agente de Algomarket. $1.290 por 1 litro, pasillo 3 (Lácteos), oferta 2x1 los martes, sin alterar cifras |
| Resultado obtenido | 200. Agente de Algomarket. Respuesta: «La leche de 1 litro cuesta $1.290 CLP y está en el pasillo 3 - Lácteos. Tiene la siguiente oferta: 2x1 los martes.» |
| Observaciones | Cumple. Hallazgo: en la primera ejecución `respuesta` llegaba como lista cruda con un bloque `signature` (captura [02-leche-antes.png](capturas-algomarket/02-leche-antes.png)). Se corrigió con `texto.py` y `graph.py` (convierten el contenido a texto plano) y se verificó (captura [02-leche.png](capturas-algomarket/02-leche.png)) |

### Caso 2: producto que no existe exactamente

| Dato | Registro |
|---|---|
| Entorno y fecha | LOCAL, 22/11/2026 21:57 |
| Solicitud | «¿Tienen aceite de oliva?» |
| Resultado esperado | No inventa el precio: avisa que no tiene aceite de oliva y ofrece una alternativa |
| Resultado obtenido | 200. Agente de Algomarket. Respuesta: «No tenemos aceite de oliva, pero ¿busca aceite?» |
| Observaciones | Cumple. La herramienta devolvió `encontrado: False` con sugerencias y el agente no inventó datos. Mejora posible: no cita el precio del aceite común ($3.990 por 1 litro). Antes del pull request #1 devolvía el precio del aceite común sin avisar. Capturas: [03a-aceite-oliva-solicitud.png](capturas-algomarket/03a-aceite-oliva-solicitud.png), [03-aceite-oliva.png](capturas-algomarket/03-aceite-oliva.png) |

### Caso 3: oferta que se cita sin alterar

| Dato | Registro |
|---|---|
| Entorno y fecha | LOCAL, 22/11/2026 22:02 |
| Solicitud | «Quiero 2 detergentes, ¿cuánto sería en total?» |
| Resultado esperado | Oferta «Pack 2 por $8.000» citada tal cual. Si calcula, muestra la cuenta |
| Resultado obtenido | 200. Agente de Algomarket. Respuesta: «Para 2 unidades, tienes la oferta Pack 2 por $8.000. Cuenta: 1 x $8.000 = $8.000 CLP en total.» |
| Observaciones | Cumple: cita la oferta y muestra la cuenta. Observaciones: (1) el `motivo` del coordinador dice que el agente «no vende ni calcula totales» aunque la consulta se le asignó y respondió con el total; es redacción del coordinador, no de AlgoMarket. (2) La respuesta trae marcas markdown (`**`); no se probó en un canal de texto plano. (3) No menciona el ahorro frente a 2 × $4.590 = $9.180. Captura: [04-detergente.png](capturas-algomarket/04-detergente.png) |

### Caso 4: horario

| Dato | Registro |
|---|---|
| Entorno y fecha | LOCAL, 22/11/2026 22:05 |
| Solicitud | «¿A qué hora abren el domingo?» |
| Resultado esperado | Domingo: abre 10:00 y cierra 20:00 |
| Resultado obtenido | 200. Agente de Algomarket. Respuesta: «El domingo abrimos de 10:00 a 20:00 horas.» |
| Observaciones | Cumple; coincide con los horarios de `tools.py`. Captura: [05-horario.png](capturas-algomarket/05-horario.png) |

### Caso 5: comida de mascotas (producto agregado con datos inventados)

| Dato | Registro |
|---|---|
| Entorno y fecha | LOCAL, 22/11/2026 22:10 |
| Solicitud | «¿Tienen comida para perros?» |
| Resultado esperado | Agente de Algomarket. Alimento para mascotas, $12.990 por 1 saco de 3 kilos, pasillo 9 (Mascotas) |
| Resultado obtenido | 200. Agente de Algomarket. Respuesta: sí, alimento para mascotas, saco de 3 kilos, $12.990 CLP, pasillo 9 - Mascotas, stock 22 unidades, sin oferta actualmente |
| Observaciones | Cumple y reconoce «comida para perros» como alias. Límite: con solo AlgoMarket levantado, esta prueba valida la respuesta del agente, no la elección del supervisor entre varios agentes (pendiente). La respuesta trae marcas markdown (`**`). Captura: [06-mascotas.png](capturas-algomarket/06-mascotas.png) |

### Caso 6: pregunta que ningún agente atiende

| Dato | Registro |
|---|---|
| Entorno y fecha | LOCAL, 22/11/2026 22:12 |
| Solicitud | «¿Cuál es la capital de Francia?» |
| Resultado esperado | Agente «ninguno»; mensaje claro de que no hay un agente para eso |
| Resultado obtenido | 200. `agente: "ninguno"`. Respuesta: «No tengo un agente para eso. Puedo ayudarte con: Agente de Algomarket. Motivo del supervisor: ...» |
| Observaciones | Cumple: no inventa una respuesta ni deriva a un agente que no corresponde. El mensaje repite el «motivo del supervisor» y suena técnico (texto del coordinador). Con 1 solo agente levantado la prueba es menos exigente. Captura: [07-ninguno.png](capturas-algomarket/07-ninguno.png) |

## Control de acceso

### Caso 7: acceso permitido y rechazado

| Dato | Registro |
|---|---|
| Entorno y fecha | LOCAL, 22/11/2026 22:22 (sin clave) y 22:24 (con clave) |
| Solicitud | `POST /chat` con la misma ruta, una vez sin `X-API-Key` y una vez con la clave correcta. Texto con clave: «¿A qué hora abren el lunes?» |
| Resultado esperado | Con clave: 200. Sin clave: 401 «Acceso no autorizado» |
| Resultado obtenido | Sin clave: 401, `{"detail": "Acceso no autorizado"}`. Con clave: 200, «El lunes abrimos a las 09:00 y cerramos a las 21:00 horas.» |
| Observaciones | Cumple. El mensaje 401 no revela si la clave faltaba o era incorrecta. Sin mostrar la clave real. Capturas: [08-acceso-ok.png](capturas-algomarket/08-acceso-ok.png), [09-acceso-401.png](capturas-algomarket/09-acceso-401.png) |

### Caso 8: entrada inválida

| Dato | Registro |
|---|---|
| Entorno y fecha | LOCAL, 22/11/2026 22:25 |
| Solicitud | `{"user_id": "caso-8", "texto": "   "}` (solo espacios) |
| Resultado esperado | 422, no una respuesta exitosa |
| Resultado obtenido | 422 Unprocessable Entity, `loc: ["body", "texto"]`, mensaje: «Value error, El texto no puede estar vacío ni contener solo espacios.» |
| Observaciones | Cumple: se rechaza sin llamar al coordinador. El formato del 422 es el estándar de validación de la API (el prefijo «Value error» viene en inglés). Captura: [10-texto-vacio.png](capturas-algomarket/10-texto-vacio.png) |

## Falla del proveedor

### Caso 9: el modelo falla dentro del agente AlgoMarket

| Dato | Registro |
|---|---|
| Entorno y fecha | LOCAL, 22/11/2026 22:33 |
| Solicitud | `{"user_id": "caso-9", "texto": "¿Cuánto cuesta la leche?"}`, con la clave del modelo **inválida solo en la terminal de AlgoMarket** (`$env:GOOGLE_API_KEY = "clave-invalida"` antes de levantar ese agente; el resto del sistema usaba la clave real) |
| Resultado esperado | La API responde 502 con «No se pudo obtener una respuesta del agente»; no aparece un 200 ni el detalle del error |
| Resultado obtenido | 502 Bad Gateway, `{"detail": "No se pudo obtener una respuesta del agente."}` |
| Observaciones | Cumple: la falla no se muestra como éxito. El registro del agente muestra que estaba activo y recibió la solicitud (`POST / 200 OK` a nivel de transporte), así que el 502 no viene de un agente caído. Límite: el registro del agente no mostró el detalle del error de Gemini, por lo que la causa (clave inválida) se deduce de cómo se preparó la prueba y no de un mensaje del proveedor. Antes del pull request #2 este caso devolvía 200 con el texto del error. Se restauró la clave real después de la prueba. Capturas: [11-falla-agente.png](capturas-algomarket/11-falla-agente.png), [11c-falla-agente-terminal.png](capturas-algomarket/11c-falla-agente-terminal.png) |

### Caso 9b: falla real del proveedor (créditos agotados)

| Dato | Registro |
|---|---|
| Entorno y fecha | LOCAL, 22/11/2026 (hora según la captura) |
| Solicitud | Consulta normal a `POST /chat` mientras la cuenta de Gemini no tenía créditos |
| Resultado esperado | La API informa el error, no una respuesta exitosa |
| Resultado obtenido | 502 «No se pudo obtener una respuesta del coordinador»; el registro de la API mostró el error 402 del proveedor (créditos de prepago agotados) |
| Observaciones | Falla real, no simulada. Se resolvió cambiando la clave por una con saldo. Captura pendiente: `11b-falla-proveedor.png` no se incluyó en el repositorio |

## Límites y pendientes

- La memoria conversacional vive en RAM y se pierde al reiniciar.
- Los precios, el stock y los horarios son datos de ejemplo.
- Gemini puede responder 503 por alta demanda; la API lo informa como error, no como respuesta.
- Solo estuvo levantado el agente AlgoMarket: **no se probó** la elección del supervisor entre varios agentes, ni A2A con los otros agentes del grupo.
- **No se probó** el canal Telegram ni el despliegue en la nube.
- Las respuestas incluyen marcas markdown (`**`); no se verificó cómo se ven en un canal de texto plano.
- Ejecución final de `python -m pytest tests -q` con los cambios de `texto.py` y `graph.py`: 23 passed, 1 skipped (captura [12-pytest-final.png](capturas-algomarket/12-pytest-final.png)).
