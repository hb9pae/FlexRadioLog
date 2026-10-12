"""Entry point for running FlexRadioLog server."""

import argparse
import logging
import sys
import uvicorn
from flexradiolog.api.app import create_app
from flexradiolog.config import AppConfig


def setup_logging(level_name: str = "INFO", file_path: str | None = None) -> None:
    """Configure structured logging to console and optional file."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if file_path:
        handlers.append(logging.FileHandler(file_path, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="FlexRadio 6400 Monitoring and Logging Server")
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)",
    )
    args = parser.parse_args()

    config = AppConfig.load_from_yaml(args.config)
    setup_logging(config.logging.level, config.logging.file_path)

    logger = logging.getLogger("flexradiolog")
    logger.info("Starting FlexRadioLog server...")
    logger.info("Radio target: %s:%d", config.radio.host, config.radio.port)
    logger.info("API bind: %s:%d", config.api.host, config.api.port)

    app = create_app(config, start_radio_client=True)

    uvicorn.run(
        app,
        host=config.api.host,
        port=config.api.port,
        log_level=config.logging.level.lower(),
    )


if __name__ == "__main__":
    main()
