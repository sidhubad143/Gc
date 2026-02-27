import asyncio
import os
from platform import system

from Powers import LOGGER
from Powers.bot_class import Gojo

if __name__ == "__main__":
    if system() == "Windows":
        LOGGER.info("Windows system detected thus not installing uvloop")
    else:
        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            LOGGER.info("uvloop activated")
        except Exception:
            LOGGER.info("uvloop not available, using default event loop")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    Gojo().run()
