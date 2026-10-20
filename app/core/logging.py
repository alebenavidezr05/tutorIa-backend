import logging

FORMATO_LOG = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOGGERS_RUIDOSOS = ("httpx", "httpx2", "httpcore", "anthropic", "openai", "botocore", "urllib3")


def configurar_logging(es_produccion: bool) -> None:
    logging.basicConfig(level=logging.INFO if es_produccion else logging.DEBUG, format=FORMATO_LOG)
    # Los SDK registran URLs y cuerpos en DEBUG; se silencian para no filtrar datos ni llaves.
    for nombre in LOGGERS_RUIDOSOS:
        logging.getLogger(nombre).setLevel(logging.WARNING)
