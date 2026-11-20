import asyncio


class EventQueue:

    def __init__(self):

        self.queue = asyncio.Queue()

    # ===================================
    # ADD EVENT
    # ===================================

    async def add_event(
        self,
        event: dict
    ):

        await self.queue.put(event)

    # ===================================
    # GET EVENT
    # ===================================

    async def get_event(self):

        return await self.queue.get()

    # ===================================
    # QUEUE SIZE
    # ===================================

    def size(self):

        return self.queue.qsize()


event_queue = EventQueue()