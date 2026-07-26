import logging
import logging.config
from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


def configure_logging(log_level: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_context": {
                    "()": "app.core.logging.RequestContextFilter",
                }
            },
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "NOTSET",
                    "formatter": "default",
                    "filters": ["request_context"],
                    "stream": "ext://sys.stderr",
                }
            },
            "loggers": {
                "app": {"level": log_level, "handlers": [], "propagate": True},
                "sqlalchemy.engine": {"level": "WARNING", "handlers": [], "propagate": True},
                "uvicorn.access": {"level": "WARNING", "handlers": [], "propagate": True},
            },
            "root": {"level": "WARNING", "handlers": ["console"]},
        }
    )
