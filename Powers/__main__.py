import asyncio
from platform import system

from Powers import LOGGER
from Powers.bot_class import Gojo

if __name__ == "__main__":
    if system() == "Windows":
        LOGGER.info("Windows detected — skipping uvloop.")
    else:
        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            LOGGER.info("✅ uvloop activated.")
        except ImportError:
            LOGGER.info("uvloop not installed — using default event loop.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    Gojo().run()
