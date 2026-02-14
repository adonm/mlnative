"""Example: Production deployment patterns.

Shows best practices for deploying mlnative in production:
- Resource management with connection pooling
- Error handling and logging
- Health checks
- Graceful shutdown
"""

import logging
import os
import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from queue import Queue

from mlnative import Map
from mlnative.exceptions import MlnativeError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MapConfig:
    """Configuration for map rendering."""

    width: int = 512
    height: int = 512
    pixel_ratio: float = 1.0
    style_url: str = "https://tiles.openfreemap.org/styles/liberty"


class MapPool:
    """Simple pool of Map instances for concurrent rendering."""

    def __init__(self, config: MapConfig, pool_size: int = 3):
        self.config = config
        self.pool_size = pool_size
        self._pool: Queue[Map] = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._initialized = False

    def initialize(self) -> None:
        """Pre-create Map instances."""
        with self._lock:
            if self._initialized:
                return
            for _ in range(self.pool_size):
                m = Map(self.config.width, self.config.height, self.config.pixel_ratio)
                m.load_style(self.config.style_url)
                self._pool.put(m)
            self._initialized = True
            logger.info(f"MapPool initialized with {self.pool_size} instances")

    @contextmanager
    def get_map(self) -> Generator[Map, None, None]:
        """Get a Map instance from the pool."""
        if not self._initialized:
            self.initialize()

        m = self._pool.get()
        try:
            yield m
        finally:
            self._pool.put(m)

    def shutdown(self) -> None:
        """Close all Map instances."""
        with self._lock:
            while not self._pool.empty():
                m = self._pool.get()
                m.close()
            self._initialized = False
            logger.info("MapPool shutdown complete")


class MapRenderer:
    """Production-ready map renderer with error handling and logging."""

    def __init__(self, config: MapConfig | None = None, pool_size: int = 3):
        self.config = config or MapConfig()
        self.pool = MapPool(self.config, pool_size)

    def render(
        self, center: list[float], zoom: float, bearing: float = 0, pitch: float = 0
    ) -> bytes | None:
        """Render a map with error handling."""
        try:
            with self.pool.get_map() as m:
                png = m.render(center=center, zoom=zoom, bearing=bearing, pitch=pitch)
                logger.debug(f"Rendered map: center={center}, zoom={zoom}, size={len(png)}")
                return png
        except MlnativeError as e:
            logger.error(f"Render failed: {e}")
            return None

    def health_check(self) -> bool:
        """Check if the renderer is healthy."""
        try:
            with self.pool.get_map() as m:
                png = m.render(center=[0, 0], zoom=1)
                return len(png) > 0
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def shutdown(self) -> None:
        """Gracefully shutdown the renderer."""
        self.pool.shutdown()


def production_example():
    """Example of production usage."""
    config = MapConfig(
        width=800,
        height=600,
        style_url="https://tiles.openfreemap.org/styles/liberty",
    )

    renderer = MapRenderer(config, pool_size=2)

    try:
        if not renderer.health_check():
            logger.error("Renderer unhealthy, aborting")
            return

        locations = [
            ([-122.4, 37.8], 12, "San Francisco"),
            ([-74.0, 40.7], 11, "New York"),
        ]

        for center, zoom, name in locations:
            png = renderer.render(center, zoom)
            if png:
                logger.info(f"Rendered {name}: {len(png)} bytes")
            else:
                logger.warning(f"Failed to render {name}")

    finally:
        renderer.shutdown()


def docker_environment():
    """Show environment variables for Docker deployment."""
    env_vars = {
        "MLNATIVE_DEBUG": os.environ.get("MLNATIVE_DEBUG", "0"),
        "MLNATIVE_TIMEOUT": os.environ.get("MLNATIVE_TIMEOUT", "30"),
    }
    logger.info(f"Environment: {env_vars}")


if __name__ == "__main__":
    print("=== Production Example ===")
    production_example()

    print("\n=== Docker Environment ===")
    docker_environment()
