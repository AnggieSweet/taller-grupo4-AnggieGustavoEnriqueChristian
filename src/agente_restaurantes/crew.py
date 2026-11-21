import os
import asyncio
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from src.agente_restaurantes.tools import buscar_restaurantes, detalle_restaurante
from src.agente_restaurantes.prompts import ROL, OBJETIVO, HISTORIA

load_dotenv()

modelo_nombre = os.getenv("MODELO", "gemini-3.5-flash-lite")
api_key = os.getenv("GOOGLE_API_KEY", "")

# CrewAI espera formato proveedor/modelo
llm = LLM(model=f"gemini/{modelo_nombre}", api_key=api_key)

agente_gourmet = Agent(
    role=ROL,
    goal=OBJETIVO,
    backstory=HISTORIA,
    tools=[buscar_restaurantes, detalle_restaurante],
    llm=llm,
    verbose=True,
    memory=False,
)

# Memoria manual por context_id
HISTORIAL_CONVERSACIONES = {}

def _obtener_historial(context_id: str) -> str:
    return HISTORIAL_CONVERSACIONES.get(context_id, "")

def _guardar_historial(context_id: str, usuario: str, respuesta: str):
    actual = HISTORIAL_CONVERSACIONES.get(context_id, "")
    nuevo = f"{actual}\nUsuario: {usuario}\nAsistente: {respuesta}"
    HISTORIAL_CONVERSACIONES[context_id] = nuevo


async def responder(texto: str, context_id: str) -> str:
    """Ejecuta el crew con memoria manual por context_id y devuelve la respuesta en texto."""
    historial = _obtener_historial(context_id)
    
    descripcion_tarea = f"""
Historial previo de la conversación:
{historial}

Pregunta actual del usuario:
{texto}
"""
    
    tarea = Task(
        description=descripcion_tarea,
        expected_output="Una recomendación de restaurantes clara, corta y en español basada en las herramientas.",
        agent=agente_gourmet,
    )
    
    crew = Crew(
        agents=[agente_gourmet],
        tasks=[tarea],
        verbose=True,
    )
    
    try:
        # Ejecutar crew en un thread separado para no bloquear el bucle async de FastAPI
        resultado = await asyncio.to_thread(crew.kickoff)
        texto_res = str(resultado)
        _guardar_historial(context_id, texto, texto_res)
        return texto_res
    except Exception as e:
        error_msg = f"Error al procesar la recomendación: {str(e)}"
        print(f"[Error CrewAI] {error_msg}")
        return error_msg


def saltos(texto: str) -> None:
    """Ejecuta el crew con step_callback para mostrar los pasos, herramientas y argumentos."""
    herramientas_usadas = 0

    def callback(step_output):
        nonlocal herramientas_usadas
        print(f"👣 [Paso CrewAI]:")
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
