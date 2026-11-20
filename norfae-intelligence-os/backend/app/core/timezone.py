from datetime import datetime
from zoneinfo import ZoneInfo


def pakistan_now():

    return datetime.now(ZoneInfo("Asia/Karachi"))
