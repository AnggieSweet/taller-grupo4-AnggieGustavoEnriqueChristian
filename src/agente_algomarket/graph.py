from dotenv import load_dotenv
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

from src import config
from src.agente_algomarket.prompts import SYSTEM_PROMPT
from src.agente_algomarket.texto import texto_de_contenido
from src.agente_algomarket.tools import buscar_producto, horario_supermercado
from src.comun.modelo import crear_llm_gemini

load_dotenv()

modelo = crear_llm_gemini(timeout=30.0, permitir_sin_clave_al_importar=True)

memoria = MemorySaver()

graph = create_agent(
    model=modelo,
    tools=[buscar_producto, horario_supermercado],
    system_prompt=SYSTEM_PROMPT,
    checkpointer=memoria,
)


def _config(context_id: str) -> dict:
    return {"configurable": {"thread_id": context_id}, "recursion_limit": config.MAX_PASOS_AGENTE * 2}


def _texto(mensaje) -> str:
    """Devuelve solo el texto de un mensaje.

    Gemini puede responder con una lista de partes ({'type': 'text', 'text': ..., 'extras': ...});
    .text las une y descarta los datos internos como la firma.
    """
    if isinstance(mensaje, dict):
        contenido = mensaje.get("content", "")
        return contenido if isinstance(contenido, str) else str(contenido)
    texto = getattr(mensaje, "text", None)
    if isinstance(texto, str):
        return texto
    return str(getattr(mensaje, "content", "") or "")


async def responder(texto: str, context_id: str) -> str:
    """Envía el texto al grafo y devuelve la última respuesta del agente como texto plano."""
    config = _config(context_id)
    resultado = await graph.ainvoke({"messages": [{"role": "user", "content": texto}]}, config=config)
    mensajes = resultado.get("messages", [])
    if not mensajes:
        return ""
    ultimo = mensajes[-1]
    contenido = getattr(ultimo, "content", None)
    if contenido is None and isinstance(ultimo, dict):
        contenido = ultimo.get("content", "")
    return texto_de_contenido(contenido)


def saltos(texto: str) -> None:
    """Ejecuta el grafo con stream y muestra cada nodo y herramienta por la que pasa."""
    config.exigir_clave()
    cfg = _config("saltos-demo")
    total = 0
    try:
        for paso in graph.stream({"messages": [{"role": "user", "content": texto}]}, config=cfg, stream_mode="updates"):
            for nodo, actualizacion in paso.items():
                total += 1
                print(f"→ Nodo: {nodo}")
                msgs = actualizacion.get("messages", []) if isinstance(actualizacion, dict) else []
                for m in msgs:
                    tipo = getattr(m, "type", None) or (m.get("type") if isinstance(m, dict) else None)
                    if tipo == "tool":
                        nombre_tool = getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else None)
                        print(f"   🛠️  Herramienta llamada: {nombre_tool}")
                    elif tipo in ("ai", "assistant"):
                        contenido = _texto(m)
                        if contenido:
                            print(f"   💬 Respuesta: {texto_de_contenido(contenido)[:200]}")
    except Exception as e:
        print(f"Error al ejecutar el agente: {e}")
        return
    print(f"\nTotal de saltos (nodos): {total}")


def diagrama() -> None:
    """Imprime la estructura del grafo en formato Mermaid."""
    print(graph.get_graph().draw_mermaid())
