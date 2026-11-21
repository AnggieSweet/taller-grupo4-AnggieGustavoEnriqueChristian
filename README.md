# Taller de agentes A2A

## Qué hace

Proyecto de agentes para tiendas del mall, cine, supermercado, patio de comidas, viajes y restaurantes. Los agentes se comunican mediante A2A; el coordinador clasifica las preguntas y la API FastAPI las recibe con autenticación por `X-API-Key`.

## Requisitos e instalación

Se recomienda Python **3.13** (el entorno del proyecto se probó con esa versión) y Windows PowerShell. Copia `.env.example` a `.env` y configura las credenciales localmente; no compartas `.env`.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
py -3.13 -m venv .venv-crew
.\.venv-crew\Scripts\python.exe -m pip install -r requirements-crew.txt
```

Usa `.venv` para la API, los agentes LangGraph y las pruebas generales. Usa `.venv-crew` para el agente de restaurantes basado en CrewAI.

## Levantar agentes

Levanta cada agente requerido en una terminal separada. Los puertos deben coincidir con las URLs configuradas en `.env`.

```powershell
uvicorn src.agente_viajes.server:app --reload --port 8000
uvicorn src.agente_restaurantes.server:app --reload --port 8001
uvicorn src.agente_anggie.server:app --reload --port 8003
uvicorn src.agente_enrique.server:app --reload --port 8004
uvicorn src.agente_algomarket.server:app --reload --port 8005
uvicorn src.agente_christian.server:app --reload --port 8006
```

No es necesario levantar por separado el servidor A2A del coordinador en el puerto 8002 para usar la API: esta carga el catálogo y llama directamente al grafo del coordinador.

## Levantar la API

Desde la raíz del proyecto, con las dependencias de `.venv` instaladas:

```powershell
uvicorn api.app:app --reload --port 8010
```

Genera una clave para `API_KEY` en `.env` con:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Abre [http://localhost:8010/docs](http://localhost:8010/docs), pulsa **Authorize** e introduce la clave. Para llamar a `/chat` desde PowerShell, configura `$env:API_KEY` en esa consola con el mismo valor de `.env` y ejecuta:

```powershell
$headers = @{ 'X-API-Key' = $env:API_KEY }
$cuerpo = @{ user_id = 'usuario-123'; texto = '¿Qué ofertas hay en cosméticos?' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://localhost:8010/chat' -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($cuerpo))
```

## Pruebas

Ejecuta las pruebas automatizadas con `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Para probar con Bruno, crea el archivo local de variables a partir de la plantilla, reemplaza el valor ficticio por tu `API_KEY` y abre la colección `bruno/` con el entorno `local`:

```powershell
Copy-Item bruno/.env.example bruno/.env
```

La variable `apiKey` del entorno Bruno usa `API_KEY` desde `bruno/.env` y está marcada como secreta. No agregues el archivo `.env` a Git.

## Preparación para despliegue

- Configura puertos y URLs por `.env`: `URL_VIAJES`, `URL_RESTAURANTES`, `URL_COORDINADOR`, `URL_ANGGIE`, `URL_ENRIQUE`, `URL_ALGOMARKET`, `URL_CHRISTIAN` y `URLS_AGENTES`. Ajusta las direcciones a la red o plataforma donde se ejecuten los servicios.
- La memoria conversacional usa almacenamiento en memoria y se pierde al reiniciar el proceso.
- Servicios externos: Gemini requiere `GOOGLE_API_KEY` (o las credenciales OAuth configuradas). La integración con Telegram está **pendiente**.

## Detener

En cada terminal donde corre un agente o la API, pulsa **Ctrl+C**.
