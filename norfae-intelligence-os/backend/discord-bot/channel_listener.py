import discord
import asyncio

from config import CHANNEL_STATUS_MAP

from message_parser import parse_order_message

from services.order_sync_service import OrderSyncService

from services.historical_sync_service import HistoricalSyncService

# ===================================
# DISCORD INTENTS
# ===================================

intents = discord.Intents.default()

intents.message_content = True

client = discord.Client(intents=intents)

# ===================================
# PROTECTION FLAG
# ===================================

sync_started = False

# ===================================
# CONTINUOUS OPERATIONAL SYNC
# ===================================


async def continuous_operational_sync():

    while True:

        try:

            print("[DISCORD LIVE SYNC RUNNING]")

        except Exception as e:

            print(f"[SYNC ERROR] {e}")

        await asyncio.sleep(15)


# ===================================
# BOT READY
# ===================================


@client.event
async def on_ready():

    global sync_started

    print("===== NEW BOT VERSION LOADED =====")

    print(f"Discord Bot Connected: " f"{client.user}")

    # ===================================
    # PREVENT DUPLICATE STARTS
    # ===================================

    if sync_started:

        print("[SYNC ALREADY STARTED]")

        return

    sync_started = True

    # ===================================
    # HISTORICAL SYNC
    # ===================================

    try:

        print("\n[STARTING HISTORICAL SYNC]")

        await HistoricalSyncService.sync_channel_history(client)

        print("\n[HISTORICAL SYNC COMPLETED]")

    except Exception as e:

        print(f"[HISTORICAL SYNC ERROR] {e}")

    # ===================================
    # START BACKGROUND TASK
    # ===================================

    asyncio.create_task(continuous_operational_sync())


# ===================================
# MESSAGE LISTENER
# ===================================


@client.event
async def on_message(message):

    try:

        print("MESSAGE EVENT WORKING")

        # ===================================
        # IGNORE BOT ITSELF
        # ===================================

        if message.author.id == client.user.id:

            return

        # ===================================
        # CHANNEL NAME
        # ===================================

        channel_name = message.channel.name

        # ===================================
        # VALID CHANNELS ONLY
        # ===================================

        if channel_name not in CHANNEL_STATUS_MAP:

            return

        # ===================================
        # STATUS
        # ===================================

        status = CHANNEL_STATUS_MAP[channel_name]

        print(f"\nNew Message In: " f"{channel_name}")

        # ===================================
        # PARSE ORDERS
        # ===================================

        parsed_orders = parse_order_message(message.content)

        # ===================================
        # NO VALID ORDERS
        # ===================================

        if not parsed_orders:

            print("No Valid Orders Found")

            return

        # ===================================
        # PROCESS ORDERS
        # ===================================

        for parsed_order in parsed_orders:

            if not parsed_order.get("order_id"):

                continue

            print(f"Parsed Order: " f"{parsed_order['order_id']}")

            OrderSyncService.upsert_order(
                parsed_order=parsed_order,
                status=status,
                discord_channel=channel_name,
                discord_message_id=message.id,
                message_created_at=message.created_at,
            )

    except Exception as e:

        print(f"[MESSAGE PROCESS ERROR] {e}")


@client.event
async def on_raw_message_edit(payload):

    try:

        print("RAW EDIT EVENT FIRED")

        channel = client.get_channel(payload.channel_id)

        if not channel:
            return

        if channel.name not in CHANNEL_STATUS_MAP:
            return

        status = CHANNEL_STATUS_MAP[channel.name]

        message = await channel.fetch_message(payload.message_id)

        parsed_orders = parse_order_message(message.content)

        print("\n===== EDITED MESSAGE =====")
        print(message.content)

        print("\n===== PARSED ORDERS =====")
        print(parsed_orders)

        if not parsed_orders:
            return

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

        print(f"UPDATED FROM EDIT: {payload.message_id}")

    except Exception as e:

        print(f"[RAW EDIT ERROR] {e}")
