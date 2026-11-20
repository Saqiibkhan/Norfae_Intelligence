import asyncio
from collections import defaultdict


class BatchAggregator:

    def __init__(self):

        self.event_batches = defaultdict(list)

    # ===================================
    # ADD EVENT TO BATCH
    # ===================================

    async def add_to_batch(
        self,
        event_type: str,
        data: dict
    ):

        self.event_batches[event_type].append(
            data
        )

    # ===================================
    # GET BATCH
    # ===================================

    async def get_batch(
        self,
        event_type: str
    ):

        batch = self.event_batches[event_type]

        self.event_batches[event_type] = []

        return batch

    # ===================================
    # CLEAR BATCH
    # ===================================

    async def clear_batch(
        self,
        event_type: str
    ):

        self.event_batches[event_type] = []


batch_aggregator = BatchAggregator()