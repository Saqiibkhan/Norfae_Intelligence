from channel_listener import client

from dotenv import load_dotenv

from app.events.event_listeners import register_event_listeners

import os

# ===================================
# LOAD ENV
# ===================================

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# ===================================
# REGISTER EVENT LISTENERS
# ===================================

register_event_listeners()

# ===================================
# START BOT
# ===================================

client.run(TOKEN)
