from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResultadoValidacion:
    valido: bool
    motivos: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def desde_motivos(cls, motivos: list[str]) -> "ResultadoValidacion":
        return cls(valido=not motivos, motivos=tuple(motivos))
