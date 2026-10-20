from app.schemas.bloques import Diagrama


def validar_diagrama(diagrama: Diagrama) -> list[str]:
    ids = [n.id for n in diagrama.nodos]
    motivos = []
    if len(ids) != len(set(ids)):
        motivos.append("el diagrama tiene nodos repetidos")
    existentes = set(ids)
    if any(a.desde not in existentes or a.hasta not in existentes for a in diagrama.aristas):
        motivos.append("el diagrama tiene aristas hacia nodos inexistentes")
    return motivos
