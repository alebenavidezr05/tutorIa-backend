from urllib.parse import quote

from fastapi import Response

from app.schemas.archivo import ArchivoDescarga

CACHE_PRIVADO = "private, no-store"


def respuesta_descarga(archivo: ArchivoDescarga, adjunto: bool = True) -> Response:
    """Respuesta binaria privada: nunca se cachea en intermediarios."""
    disposicion = "attachment" if adjunto else "inline"
    return Response(
        content=archivo.contenido,
        media_type=archivo.mime,
        headers={
            "Cache-Control": CACHE_PRIVADO,
            "Content-Disposition": f"{disposicion}; filename*=UTF-8''{quote(archivo.nombre)}",
        },
    )
