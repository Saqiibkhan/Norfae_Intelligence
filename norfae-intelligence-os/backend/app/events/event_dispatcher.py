class EventDispatcher:

    listeners = {}

    # ===================================
    # REGISTER LISTENER
    # ===================================

    @classmethod
    def register(cls, event_type, callback):

        if event_type not in cls.listeners:

            cls.listeners[event_type] = []

        cls.listeners[event_type].append(callback)

    # ===================================
    # DISPATCH EVENT
    # ===================================

    @classmethod
    async def dispatch(cls, event_type, data):

        print(f"[EVENT DISPATCH] {event_type}")

        if event_type in cls.listeners:

            print(f"[EVENT LISTENERS] " f"{len(cls.listeners[event_type])}")

            for callback in cls.listeners[event_type]:

                print(f"[CALLING LISTENER] " f"{callback.__name__}")

                await callback(data)

        else:

            print(f"[NO LISTENER] {event_type}")
