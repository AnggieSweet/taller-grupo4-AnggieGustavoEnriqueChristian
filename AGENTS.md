# Reglas del proyecto

- Todo en español: nombres, comentarios y mensajes.
- Las funciones que usan internet son async.
- Toda llamada por red tiene un timeout explícito.
- Si algo no responde, el error se muestra en una sola línea entendible, sin stack trace.
- Cada agente expone una función `responder(texto, context_id)` que devuelve un texto. Es el contrato que todos cumplen.
- Cada agente se puede correr desde la terminal sin servidor, igual que en el Curso 1: `python main.py {agente} "pregunta"`. Con `--saltos` muestra por qué nodos y herramientas pasó; con `--diagrama` imprime su estructura en Mermaid sin ejecutarlo.
- La API va en `api/app.py` (FastAPI) y se levanta desde la raíz con: `uvicorn api.app:app --reload --port 8010`.
- La API no contiene agentes ni reglas de negocio: valida el acceso y el mensaje, y le pasa la pregunta al coordinador; el coordinador se encarga de hablar con los agentes por A2A.
- Toda ruta de la API, salvo `/health`, exige la cabecera `X-API-Key` con el valor de `API_KEY`; si falta o no coincide, responde 401.
- La API nunca devuelve claves, tokens ni stack traces al cliente; el detalle de los errores queda solo en el log.
- Los prompts de cada nodo nuevo van en `prompts.py`, no dentro de `graph.py`.
- Los scripts sueltos van en `scripts/` y las pruebas en `tests/` (pytest).
