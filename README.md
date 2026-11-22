# Taller de agentes A2A

## Integrantes y agentes

- Anggie Merlo | Agente de tiendas del mall (Calzado Paso Firme, Cosmética Brillo Natural, Mascotas Huella Feliz, Muebles Casa Serena). Integración de los agentes del grupo en el proyecto base y ajustes al coordinador. | API FastAPI protegida con X-API-Key, memoria por usuario, pruebas del supervisor (pytest), colección Bruno, preparación de GitHub y README.
- Enrique Molina | Agente de cine (cartelera y horarios), puerto 8004. Grafo LangGraph con las herramientas `consultar_cartelera` (funciones por fecha, película, formato 2D/IMAX e idioma) y `buscar_funciones` (horarios, salas y precios de una película), sobre la cartelera de ejemplo en `data/cartelera.json`. | Corrección del manejo de fechas: el agente conoce la fecha de hoy y entiende "mañana" o "el sábado". Timeout del modelo y límite de pasos según `AGENTS.md`. Script `scripts/configurar_clave.py` para guardar `GOOGLE_API_KEY` en `.env` sin mostrarla.
- Gustavo Hormazabal | Agente AlgoMarket (supermercado), puerto 8005. Grafo LangGraph con las herramientas `buscar_producto` (precio en CLP, stock, pasillo y oferta vigente de leche, pan, arroz, aceite, detergente y bebidas) y `horario_supermercado` (apertura y cierre según el día). | Ficha A2A con sus límites: no vende, no reserva ni calcula despachos, y no responde sobre otras tiendas, restaurantes, cine ni estacionamiento.
- Christian Vasquez | Agente del patio de comidas "Terraza Sabores" (Mall Portal Nativo), puerto 8006. Herramientas `buscar_platos` (locales, platos, precios, alérgenos, dietas y si el local está abierto), `promociones_vigentes` (validadas por día y hora), `info_patio` (pagos, Club Nativo, Wi-Fi, baños, zona infantil, estacionamiento) y `calcular_total` (total de un pedido en CLP). | Guardias de entrada y salida en `src/comun/guardias.py` (inyección de instrucciones, datos personales, secretos y datos no respaldados), configuración central en `src/config.py` y fecha y hora actuales en el prompt.

## Opción elegida

Opción 2: servicio FastAPI protegido con `X-API-Key` e integración con Telegram

## Qué hace

Proyecto de agentes para tiendas del mall, cine, supermercado, patio de comidas, viajes y restaurantes. Los agentes se comunican mediante A2A; el coordinador clasifica las preguntas y la API FastAPI las recibe con autenticación por `X-API-Key`.

## Control de acceso

- Permitido: clave correcta → 200.
- Rechazado: sin clave o clave incorrecta → 401.
- Texto vacío → 422.

## Evidencias

## Límites conocidos

- La temperatura es ignorada por el modelo.
- Restaurantes solo LIM/BOG/EZE.
- La memoria se guarda en RAM.
- Los agentes deben estar arriba antes de iniciar la API.
- La cartelera de ejemplo es diaria; no hay funciones distintas por fecha.
- Gemini puede responder 503 por alta demanda (el bot contesta "Hubo un problema, intenta de nuevo").

## Preparación para despliegue

- Configura puertos y URLs por `.env`: `URL_VIAJES`, `URL_RESTAURANTES`, `URL_COORDINADOR`, `URL_ANGGIE`, `URL_ENRIQUE`, `URL_ALGOMARKET`, `URL_CHRISTIAN` y `URLS_AGENTES`. Ajusta las direcciones a la red o plataforma donde se ejecuten los servicios.
- La memoria conversacional usa almacenamiento en memoria y se pierde al reiniciar el proceso.
- Servicios externos: Gemini requiere `GOOGLE_API_KEY`.

## Telegram

1. Crea un bot con [@BotFather](https://t.me/BotFather) y copia el token que entrega en `TELEGRAM_TOKEN` dentro de `.env`.
2. Genera el secreto del webhook con `python -c "import secrets; print(secrets.token_urlsafe(32))"` y guárdalo en `TELEGRAM_SECRET`.
3. Configura `TELEGRAM_PERMITIDOS` con los `chat_id` autorizados, separados por comas. Si un chat no está permitido, el bot le responde con su `chat_id` para que puedas agregarlo.
4. Levanta los servicios en este orden: agentes → API → `python -m scripts.telegram_local`.

El túnel de `cloudflared` cambia de URL en cada arranque; es temporal y no constituye un despliegue. Esto puede tardar bastantes minutos.

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

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

Levanta primero los agentes requeridos, cada uno en una terminal separada. Activa el entorno indicado antes de ejecutar cada servidor. Los puertos deben coincidir con las URLs configuradas en `.env`.

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn src.agente_viajes.server:app --reload --port 8000
```

```powershell
.\.venv-crew\Scripts\Activate.ps1
uvicorn src.agente_restaurantes.server:app --reload --port 8001
```

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn src.agente_anggie.server:app --reload --port 8003
```

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn src.agente_enrique.server:app --reload --port 8004
```

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn src.agente_algomarket.server:app --reload --port 8005
```

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn src.agente_christian.server:app --reload --port 8006
```

Después de levantar los agentes, inicia la API. La API carga el catálogo al iniciar; si faltan agentes, `/chat` responde 502. No es necesario levantar por separado el servidor A2A del coordinador en el puerto 8002: la API llama directamente al grafo del coordinador.

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

La variable `apiKey` se lee de `bruno/.env` con `{{process.env.API_KEY}}`; no está en Secrets. No agregues `bruno/.env` ni `.env` a Git.

## Detener

En cada terminal donde corre un agente o la API, pulsa **Ctrl+C**.
