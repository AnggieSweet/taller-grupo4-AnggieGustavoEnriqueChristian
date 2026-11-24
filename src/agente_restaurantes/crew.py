import asyncio
import os

from crewai import Agent, Crew, LLM, Task
from dotenv import load_dotenv

from src.agente_restaurantes.prompts import HISTORIA, OBJETIVO, ROL
from src.agente_restaurantes.tools import buscar_restaurantes, detalle_restaurante

load_dotenv()


def _crear_llm_crew() -> LLM:
    modelo_nombre = os.getenv("MODELO", "gemini-3.5-flash-lite")
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    usar_oauth = os.getenv("USAR_OAUTH", "").strip().lower() in ("1", "true", "si", "sí")
    proyecto = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    ubicacion = os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip() or "global"

    if usar_oauth and not api_key:
        from src import config

        creds, proyecto_adc = config.obtener_credenciales_oauth()
        proy = proyecto or proyecto_adc
        if proy:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", proy)
            os.environ.setdefault("VERTEXAI_PROJECT", proy)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", ubicacion)
        os.environ.setdefault("VERTEXAI_LOCATION", ubicacion)
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        return LLM(
            model=f"gemini/{modelo_nombre}",
            project=proy or None,
            location=ubicacion,
            client_params={"credentials": creds},
            timeout=30,
        )

    return LLM(model=f"gemini/{modelo_nombre}", api_key=api_key or "CLAVE_NO_CONFIGURADA", timeout=30)


llm = _crear_llm_crew()

agente_gourmet = Agent(
    role=ROL,
    goal=OBJETIVO,
    backstory=HISTORIA,
    tools=[buscar_restaurantes, detalle_restaurante],
    llm=llm,
    verbose=False,
    memory=False,
    max_iter=6,
)

# Memoria manual por context_id
HISTORIAL_CONVERSACIONES: dict[str, str] = {}


def _obtener_historial(context_id: str) -> str:
    return HISTORIAL_CONVERSACIONES.get(context_id, "")


def _guardar_historial(context_id: str, usuario: str, respuesta: str) -> None:
    actual = HISTORIAL_CONVERSACIONES.get(context_id, "")
    nuevo = f"{actual}\nUsuario: {usuario}\nAsistente: {respuesta}"
    HISTORIAL_CONVERSACIONES[context_id] = nuevo[-4000:]


async def responder(texto: str, context_id: str) -> str:
    """Ejecuta el crew con memoria manual por context_id y propaga fallas para que la API devuelva 502/504."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    usar_oauth = os.getenv("USAR_OAUTH", "").strip().lower() in ("1", "true", "si", "sí")
    if not api_key and not usar_oauth:
        raise RuntimeError("Falta GOOGLE_API_KEY en .env (o USAR_OAUTH=true).")

    historial = _obtener_historial(context_id)
    descripcion_tarea = (
        f"Historial previo de la conversación:\n{historial}\n\n"
        f"Pregunta actual del usuario:\n{texto}\n"
    )

    tarea = Task(
        description=descripcion_tarea,
        expected_output="Una recomendación de restaurantes clara, corta y en español basada en las herramientas.",
        agent=agente_gourmet,
    )

    crew = Crew(
        agents=[agente_gourmet],
        tasks=[tarea],
        verbose=False,
    )

    try:
        resultado = await asyncio.to_thread(crew.kickoff)
        texto_res = str(resultado)
        _guardar_historial(context_id, texto, texto_res)
        return texto_res
    except Exception as e:
        detalle = " ".join(str(e).splitlines()).strip()
        raise RuntimeError(f"Error al procesar la recomendación: {detalle or 'falla del proveedor'}") from e


def saltos(texto: str) -> None:
    """Ejecuta el crew con step_callback para mostrar los pasos, herramientas y argumentos."""
    herramientas_usadas = 0

    def callback(step_output):
        nonlocal herramientas_usadas
        print("👣 [Paso CrewAI]:")
        if hasattr(step_output, "thought") and step_output.thought:
            print(f"   💭 Pensamiento: {step_output.thought}")
        if hasattr(step_output, "tool") and step_output.tool:
            herramientas_usadas += 1
            print(f"   🛠️  Herramienta: {step_output.tool}")
            print(f"   📥 Argumentos: {step_output.tool_input}")
        if hasattr(step_output, "result") and step_output.result:
            print(f"   📤 Resultado: {str(step_output.result)[:200]}")

    tarea = Task(
        description=texto,
        expected_output="Recomendación basada en herramientas.",
        agent=agente_gourmet,
    )
    crew = Crew(
        agents=[agente_gourmet],
        tasks=[tarea],
        verbose=False,
        step_callback=callback,
    )

    try:
        crew.kickoff()
    except Exception as e:
        print(f"Error en saltos: {e}")
    print(f"\nTotal de herramientas usadas: {herramientas_usadas}")


def diagrama() -> None:
    """Imprime en Mermaid la estructura del crew armada a mano."""
    mermaid_code = """graph TD;
    Task["Task: Recomendación de restaurantes"] --> Agent["Agent: Crítico Gastronómico (CrewAI)"];
    Agent --> Tool1["buscar_restaurantes(ciudad, tipo)"];
    Agent --> Tool2["detalle_restaurante(nombre)"];
    classDef default fill:#f2f0ff,line-height:1.2;
    classDef task fill:#bfb6fc;
    class Task task;
"""
    print(mermaid_code)
