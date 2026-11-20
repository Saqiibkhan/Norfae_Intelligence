from config import CHANNEL_STATUS_MAP, HISTORICAL_SYNC_DAYS

from datetime import datetime, timedelta, timezone

from message_parser import parse_order_message

from services.order_sync_service import OrderSyncService


class HistoricalSyncService:

    @staticmethod
    async def sync_channel_history(client):

        print("\nStarting Historical Discord Sync...")

        total_synced = 0

        for guild in client.guilds:

            print(f"\nScanning Server: " f"{guild.name}")

            for channel in guild.text_channels:

                # ===================================
                # VALID ORDER CHANNELS ONLY
                # ===================================

                if channel.name not in CHANNEL_STATUS_MAP:

                    continue

                print(f"\nScanning Channel: " f"{channel.name}")

                status = CHANNEL_STATUS_MAP[channel.name]

                try:

                    # ===================================
                    # LAST 30 DAYS RECOVERY
                    # ===================================

                    after_time = datetime.now(timezone.utc) - timedelta(
                        days=HISTORICAL_SYNC_DAYS
                    )

                    print(f"Scanning Last " f"{HISTORICAL_SYNC_DAYS} Days")

                    print(f"Recovery Start Date: " f"{after_time}")

                    async for message in channel.history(
                        limit=None, after=after_time, oldest_first=True
                    ):

                        # ===================================
                        # IGNORE THIS BOT ONLY
                        # ===================================

                        if message.author.id == client.user.id:

                            continue

                        # ===================================
                        # PARSE MULTIPLE ORDERS
                        # ===================================

                        parsed_orders = parse_order_message(message.content)

                        if not parsed_orders:

                            continue

                        # ===================================
                        # PROCESS ALL ORDERS
                        # ===================================

                        for parsed_order in parsed_orders:

                            if not parsed_order.get("order_id"):

                                continue

                            OrderSyncService.upsert_order(
                                parsed_order=parsed_order,
                                status=status,
                                discord_channel=channel.name,
                                discord_message_id=message.id,
                                message_created_at=message.created_at,
                            )

                            total_synced += 1

                    print(f"Finished Channel: " f"{channel.name}")

                except Exception as error:

                    print(f"Historical Sync Error " f"in {channel.name}:", error)

        print(f"\nHistorical Sync Completed.")

        print(f"Total Orders Synced: " f"{total_synced}")
