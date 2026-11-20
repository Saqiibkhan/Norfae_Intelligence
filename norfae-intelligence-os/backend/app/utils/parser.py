class Parser:

    @staticmethod
    def parse_float(
        value
    ):

        try:

            return float(value)

        except:

            return 0