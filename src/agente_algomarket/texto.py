"""Extrae el texto de la respuesta de un modelo, que puede venir como str o como bloques."""


def texto_de_contenido(contenido) -> str:
    """Devuelve solo el texto visible.

    Algunos modelos entregan el contenido como lista de bloques, por ejemplo
    [{'type': 'text', 'text': 'Hola', 'extras': {...}}]. Se concatenan solo los
    bloques de texto y se descartan metadatos como 'extras' o 'signature'.
    """
    if contenido is None:
        return ""
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, (list, tuple)):
        partes = []
        for parte in contenido:
            if isinstance(parte, str):
                partes.append(parte)
            elif isinstance(parte, dict) and isinstance(parte.get("text"), str):
                partes.append(parte["text"])
        return "\n".join(p for p in partes if p).strip()
    if isinstance(contenido, dict) and isinstance(contenido.get("text"), str):
        return contenido["text"]
    return str(contenido)
