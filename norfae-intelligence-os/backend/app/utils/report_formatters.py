from datetime import datetime


class ReportFormatter:

    @staticmethod
    def currency(value):

        try:
            return f"Rs. {float(value):,.2f}"

        except:
            return "Rs. 0"

    @staticmethod
    def percentage(value):

        try:
            return f"{float(value):,.2f}%"

        except:
            return "0%"

    @staticmethod
    def date(value):

        try:

            if isinstance(value, str):

                value = datetime.fromisoformat(value)

            return value.strftime("%d %B %Y - %I:%M %p")

        except:

            return "-"
