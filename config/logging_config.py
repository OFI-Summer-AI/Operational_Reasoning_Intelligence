import logging
import logging.handlers
import os

import structlog


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "pretty",
    log_file: str = "./logs/ori.log",
) -> structlog.BoundLogger:
    """Configure structlog + stdlib logging with file rotation."""
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    handlers.append(file_handler)

    giskard_log = log_file.replace("ori.log", "giskard.log").replace("orip1.log", "giskard.log")
    giskard_handler = logging.handlers.RotatingFileHandler(
        giskard_log, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    giskard_handler.addFilter(_GiskardFilter())
    handlers.append(giskard_handler)

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
        ],
    )
    for handler in handlers:
        handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    for handler in handlers:
        root.addHandler(handler)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("ori")


class _GiskardFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.msg).lower()
        return "giskard" in record.name.lower() or "trust.validation" in msg or "governance" in msg
