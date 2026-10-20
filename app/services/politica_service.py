import re

from app.core.config import Settings
from app.crypto.indice_ciego import sha256_hex
from app.legal import TextosLegales
from app.models.enums import FinalidadConsentimiento
from app.schemas.privacidad import (
    CumplimientoPublico,
    FinalidadPublica,
    PoliticaPublica,
    ProveedorDatos,
    ResponsablePublico,
)

_PATRON_MARCADOR = re.compile(r"\{\{[a-z_]+\}\}")
PROVEEDORES_DATOS = (
    ProveedorDatos(
        nombre="Anthropic (Claude), EE. UU.",
        datos_enviados="Mensajes del turno con datos personales redactados, perfil pedagógico sin "
        "datos personales y archivos del nivel avanzado.",
        finalidad="Generar explicaciones, cuestionarios, planes y la síntesis del perfil.",
    ),
    ProveedorDatos(
        nombre="OpenAI, EE. UU.",
        datos_enviados="Texto e imágenes para moderación; descripción del concepto para "
        "ilustraciones; identificador seudónimo (HMAC).",
        finalidad="Moderar contenido y, como último recurso, generar ilustraciones educativas.",
    ),
    ProveedorDatos(
        nombre="Proveedores de fuentes e imágenes abiertas",
        datos_enviados="Solo términos de búsqueda sobre el concepto de estudio.",
        finalidad="Recuperar fuentes verificables e imágenes con licencia abierta.",
    ),
    ProveedorDatos(
        nombre="YouTube / Google",
        datos_enviados="Los que el navegador envía al reproducir un video incrustado.",
        finalidad="Reproducir videos explicativos revisados.",
    ),
    ProveedorDatos(
        nombre="Amazon Web Services",
        datos_enviados="Datos cifrados de la cuenta, archivos y correos transaccionales.",
        finalidad="Alojamiento, almacenamiento, claves de cifrado y envío de correo.",
    ),
)


class PoliticaService:
    """Muestra la política versionada y calcula la huella del texto exacto que se acepta.
    El texto jurídico no lo escribe el código: son plantillas que revisa un abogado."""

    def __init__(self, settings: Settings, textos: TextosLegales) -> None:
        self._settings = settings
        self._textos = textos
        self._politica = self._renderizar()

    def obtener(self) -> PoliticaPublica:
        return PoliticaPublica(
            version=self._settings.politica_version,
            texto=self._politica,
            responsable=self._responsable(),
            finalidades=[
                FinalidadPublica(
                    finalidad=FinalidadConsentimiento(clave),
                    obligatoria=bool(datos["obligatoria"]),
                    texto=str(datos["texto"]),
                )
                for clave, datos in self._textos.finalidades.items()
            ],
            vigente_desde=self._textos.vigente_desde,
        )

    def huella(self, finalidad: FinalidadConsentimiento) -> str:
        texto_finalidad = str(self._textos.finalidades[finalidad.value]["texto"])
        return sha256_hex(f"{self._politica}\n---\n{texto_finalidad}")

    def marcadores_pendientes(self) -> list[str]:
        return sorted(set(_PATRON_MARCADOR.findall(self._politica)))

    def cumplimiento(self) -> CumplimientoPublico:
        s = self._settings
        return CumplimientoPublico(
            proveedores=list(PROVEEDORES_DATOS),
            edad_minima=s.edad_minima,
            retencion_dias={
                "mensajes": s.retencion_mensajes_dias,
                "archivos": s.archivo_retencion_dias,
                "alertas": s.retencion_alertas_dias,
                "consumo_ia": s.retencion_consumo_dias,
            },
            contacto=s.responsable_correo_datos,
        )

    def _responsable(self) -> ResponsablePublico:
        s = self._settings
        return ResponsablePublico(
            razon_social=s.responsable_razon_social,
            nit=s.responsable_nit,
            domicilio=s.responsable_domicilio,
            correo_datos=s.responsable_correo_datos,
        )

    def _renderizar(self) -> str:
        texto = self._textos.politica
        for marcador, valor in self._valores().items():
            if valor:
                texto = texto.replace("{{" + marcador + "}}", valor)
        return texto

    def _valores(self) -> dict[str, str]:
        s = self._settings
        return {
            "razon_social": s.responsable_razon_social,
            "nit": s.responsable_nit,
            "domicilio": s.responsable_domicilio,
            "correo_datos": s.responsable_correo_datos,
            "finalidades": "\n".join(f"- {d['texto']}" for d in self._textos.finalidades.values()),
            "destinatarios": "\n".join(f"- {p.nombre}: {p.finalidad}" for p in PROVEEDORES_DATOS),
            "plazo_consulta": str(s.privacidad_plazo_consulta_dias_habiles),
            "plazo_reclamo": str(s.privacidad_plazo_reclamo_dias_habiles),
            "retencion": f"Mensajes: {s.retencion_mensajes_dias} días; archivos: "
            f"{s.archivo_retencion_dias} días; alertas: {s.retencion_alertas_dias} días.",
            "vigente_desde": self._textos.vigente_desde,
        }
