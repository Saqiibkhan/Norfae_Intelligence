from app.core.timezone import pakistan_now


class DateUtils:

    @staticmethod
    def now():

        return pakistan_now()

    @staticmethod
    def current_date():

        return pakistan_now().date()
