from pathlib import Path
from typing import Literal
import sys
import traceback
import asyncio
import spdlog as spd


class SpdLog:
    """
    Log registration class responsible for creating and managing loggers.

    Features:
    - Supports multiple log levels
    - Structured log output (e.g., JSON format)
    - Captures and logs synchronous and asynchronous exceptions
    - Supports log rotation
    - Allows managing log settings via configuration files or environment variables
    """

    log_dir = Path(".log")
    log_dir_created = False
    loggers = {}
    async_mode = True
    error_logger = None
    
    daily_sink = spd.daily_file_sink_mt(filename=str(log_dir / "log.log"), rotation_hour=0, rotation_minute=0)
    daily_sink.set_level(spd.LogLevel.INFO)
    
    stdout_sink = spd.stdout_color_sink_mt()    
    stdout_sink.set_level(spd.LogLevel.DEBUG)
    
    sinks = [
        daily_sink,
        stdout_sink,
    ]

    @classmethod
    def setup_error_handling(cls):
        cls.error_logger = cls.get_logger("Error", level="ERROR", flush=True)

        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            tb_str = "".join(
                traceback.format_exception(exc_type, exc_value, exc_traceback)
            )
            cls.error_logger.error(tb_str)

        sys.excepthook = handle_exception

        def handle_async_exception(loop, async_context):
            msg = async_context.get(
                "exception", async_context.get("message", "Unknown async exception")
            )
            if "exception" in async_context:
                exception = async_context["exception"]
                tb_str = "".join(
                    traceback.format_exception(
                        type(exception), exception, exception.__traceback__
                    )
                )
                cls.error_logger.error(tb_str)
            else:
                cls.error_logger.error(f"Caught async exception: {msg}")

        asyncio.get_event_loop().set_exception_handler(handle_async_exception)

    @classmethod
    def get_logger(
        cls,
        name: str,
        level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
        flush: bool = False,
        production_mode: bool = False,
    ) -> spd.Logger:
        """
        Get the logger with the specified name. If it doesn't exist, create a new logger.

        :param name: Logger name
        :param level: Log level
        :param flush: Whether to flush after each log entry
        :return: spdlog.Logger instance
        """
        if name not in cls.loggers:
            if not cls.log_dir_created:
                cls.log_dir.mkdir(parents=True, exist_ok=True)
                cls.log_dir_created = True
            if production_mode:
                logger_instance = spd.SinkLogger(name=name, sinks=cls.sinks)
            else:
                logger_instance = spd.DailyLogger(
                    name=name,
                    filename=str(cls.log_dir / f"{name}.log"),
                    hour=0,
                    minute=0,
                    async_mode=cls.async_mode,
                )
            logger_instance.set_level(cls.parse_level(level))
            if flush:
                logger_instance.flush_on(cls.parse_level(level))
            cls.loggers[name] = logger_instance
        return cls.loggers[name]

    @classmethod
    def parse_level(
        cls, level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    ) -> spd.LogLevel:
        """
        Parse the log level string to spdlog.LogLevel.

        :param level: Log level string
        :return: spdlog.LogLevel
        """
        levels = {
            "DEBUG": spd.LogLevel.DEBUG,
            "INFO": spd.LogLevel.INFO,
            "WARNING": spd.LogLevel.WARN,
            "ERROR": spd.LogLevel.ERR,
            "CRITICAL": spd.LogLevel.CRITICAL,
        }
        return levels[level]

    @classmethod
    def close_all_loggers(cls):
        """
        Close all loggers and release resources.
        """
        for logger in cls.loggers.values():
            logger.flush()
            logger.drop()

    @classmethod
    def initialize(cls, log_dir: str = ".logs", async_mode: bool = True, setup_error_handlers: bool = True):
        """
        Initialize the log registry.

        :param setup_error_handlers: Whether to set up global exception handlers
        :param log_dir: Log directory
        :param async_mode: Whether to enable asynchronous mode
        """
        cls.log_dir = Path(log_dir)
        cls.async_mode = async_mode
        if setup_error_handlers:
            cls.setup_error_handling()

    @classmethod
    def __del__(cls):
        cls.close_all_loggers()


if __name__ == "__main__":
    SpdLog.initialize(setup_error_handlers=False)  # You should initialize the logger in the main thread
    logger = SpdLog.get_logger("test", level="DEBUG", flush=True)
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warn("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    raise ValueError("This is a test exception")
