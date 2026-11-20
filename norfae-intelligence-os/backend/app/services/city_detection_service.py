class CityDetectionService:

    # ===================================
    # SUPPORTED CITIES + ALIASES
    # ===================================

    SUPPORTED_CITIES = {

        "lahore": [
            "lahore",
            "lhe",
            "naya lahore",
            "chota lahore"
        ],

        "karachi": [
            "karachi",
            "khi"
        ],

        "islamabad": [
            "islamabad",
            "isb"
        ],

        "rawalpindi": [
            "rawalpindi",
            "rwp",
            "pindi"
        ],

        "sukkur": [
            "sukkur",
            "skz"
        ],

        "kasur": [
            "kasur",
            "ksa"
        ],

        "sheikhupura": [
            "sheikhupura",
            "sra"
        ],

        "peshawar": [
            "peshawar",
            "pwr"
        ],

        "quetta": [
            "quetta",
            "uet"
        ],

        "hyderabad": [
            "hyderabad",
            "hdd"
        ],

        "sahiwal": [
            "sahiwal",
            "swl"
        ],

        "multan": [
            "multan",
            "mul"
        ],

        "sargodha": [
            "sargodha",
            "sgd"
        ],

        "sialkot": [
            "sialkot",
            "skt"
        ],

        "gujranwala": [
            "gujranwala",
            "guj"
        ],

        "jhelum": [
            "jhelum",
            "jlm"
        ],

        "mirpur": [
            "mirpur",
            "mir"
        ],

        "abbottabad": [
            "abbottabad",
            "abt"
        ],

        "bahawalpur": [
            "bahawalpur",
            "bhv"
        ],

        "faisalabad": [
            "faisalabad",
            "fsd"
        ],

        "dera ismail khan": [
            "dera ismail khan",
            "dik"
        ],

        "gwadar": [
            "gwadar",
            "gwr"
        ],

        "turbat": [
            "turbat",
            "tur"
        ],

        "dera ghazi khan": [
            "dera ghazi khan",
            "dgk"
        ],

        "hafizabad": [
            "hafizabad",
            "hfz"
        ],

        "mandi bahauddin": [
            "mandi bahauddin",
            "mbd"
        ],

        "rahim yar khan": [
            "rahim yar khan",
            "ryk"
        ],

        "okara": [
            "okara",
            "oka"
        ],

        "mianwali": [
            "mianwali",
            "mwi"
        ],

        "vehari": [
            "vehari",
            "vri"
        ],

        "gujrat": [
            "gujrat",
            "grt"
        ],

        "attock": [
            "attock",
            "att"
        ],

        "wah cantt": [
            "wah cantt",
            "wah"
        ],

        "narowal": [
            "narowal",
            "nrl"
        ],

        "pakpattan": [
            "pakpattan",
            "pps"
        ],

        "bhakkar": [
            "bhakkar",
            "bkr"
        ],

        "kamoke": [
            "kamoke",
            "kmk"
        ],

        "haripur": [
            "haripur",
            "hri"
        ],

        "chakwal": [
            "chakwal",
            "ckl"
        ],

        "mardan": [
            "mardan",
            "mdn"
        ],

        "kharian": [
            "kharian",
            "krn"
        ],

        "thatta": [
            "thatta",
            "tht"
        ],

        "bannu": [
            "bannu",
            "bnu"
        ],

        "nankana sahib": [
            "nankana sahib",
            "nks"
        ],

        "khushab": [
            "khushab",
            "khb"
        ],

        "arifwala": [
            "arifwala",
            "arf"
        ],

        "balakot": [
            "balakot",
            "bkt"
        ],

        "badin": [
            "badin",
            "bdn"
        ],

        "bhimber": [
            "bhimber",
            "bmr"
        ],

        "charsadda": [
            "charsadda",
            "crs"
        ],

        "chiniot": [
            "chiniot",
            "cht"
        ],

        "chitral": [
            "chitral",
            "ctl"
        ],

        "daska": [
            "daska",
            "dsk"
        ],

        "dina": [
            "dina",
            "din"
        ],

        "dinga": [
            "dinga",
            "dng"
        ],

        "farooqabad": [
            "farooqabad",
            "fqb"
        ],

        "fateh jang": [
            "fateh jang",
            "ftj"
        ],

        "gojra": [
            "gojra",
            "gra"
        ],

        "harappa": [
            "harappa",
            "hpa"
        ],

        "hasil pur": [
            "hasil pur",
            "hsl"
        ],

        "haveli lakha": [
            "haveli lakha",
            "hlk"
        ],

        "hazro": [
            "hazro",
            "hzo"
        ],

        "hub chowki": [
            "hub chowki",
            "hub"
        ],

        "jahanian": [
            "jahanian",
            "jhn"
        ],

        "jalalpur jattan": [
            "jalalpur jattan",
            "jlp"
        ],

        "jampur": [
            "jampur",
            "jmp"
        ],

        "jaranwala": [
            "jaranwala",
            "jrw"
        ],

        "joharabad": [
            "joharabad",
            "jrd"
        ],

        "kabirwala": [
            "kabirwala",
            "kbr"
        ],

        "kahuta": [
            "kahuta",
            "kht"
        ],

        "kamalia": [
            "kamalia",
            "kml"
        ],

        "kamra": [
            "kamra",
            "kma"
        ],

        "karak": [
            "karak",
            "krk"
        ],

        "khanewal": [
            "khanewal",
            "kwl"
        ],

        "khanpur": [
            "khanpur",
            "knp"
        ],

        "khuzdar": [
            "khuzdar",
            "kzd"
        ],

        "kohat": [
            "kohat",
            "oht"
        ],

        "kot addu": [
            "kot addu",
            "kou"
        ],

        "kotli": [
            "kotli",
            "kly"
        ],

        "kotri": [
            "kotri",
            "ktr"
        ],

        "larkana": [
            "larkana",
            "lar"
        ],

        "layyah": [
            "layyah",
            "lya"
        ],

        "lodhran": [
            "lodhran",
            "lod"
        ],

        "loralai": [
            "loralai",
            "lri"
        ],

        "mailsi": [
            "mailsi",
            "msi"
        ],

        "malakwal": [
            "malakwal",
            "mlk"
        ],

        "mansehra": [
            "mansehra",
            "mna"
        ],

        "mian channu": [
            "mian channu",
            "mcn"
        ],

        "mingora": [
            "mingora",
            "mng"
        ],

        "mirpur khas": [
            "mirpur khas",
            "mpk"
        ],

        "moro": [
            "moro",
            "mro"
        ],

        "muridke": [
            "muridke",
            "mdk"
        ],

        "murree": [
            "murree",
            "ree"
        ],

        "muzaffarabad": [
            "muzaffarabad",
            "mak"
        ],

        "muzaffargarh": [
            "muzaffargarh",
            "mzg"
        ],

        "nawabshah": [
            "nawabshah",
            "nwb"
        ],

        "nowshera": [
            "nowshera",
            "now"
        ],

        "pasrur": [
            "pasrur",
            "prr"
        ],

        "patoki": [
            "patoki",
            "pti"
        ],

        "phalia": [
            "phalia",
            "phl"
        ],

        "pindi bhattian": [
            "pindi bhattian",
            "pbt"
        ],

        "raiwind": [
            "raiwind",
            "rnd"
        ],

        "rajanpur": [
            "rajanpur",
            "rjp"
        ],

        "renala khurd": [
            "renala khurd",
            "rlk"
        ],

        "rohri": [
            "rohri",
            "rhi"
        ],

        "sadiqabad": [
            "sadiqabad",
            "sdq"
        ],

        "samundri": [
            "samundri",
            "smd"
        ],

        "sanghar": [
            "sanghar",
            "san"
        ],

        "sangla hill": [
            "sangla hill",
            "sgh"
        ],

        "saray alamgir": [
            "saray alamgir",
            "sag"
        ],

        "shahdadpur": [
            "shahdadpur",
            "spr"
        ],

        "shahkot": [
            "shahkot",
            "shk"
        ],

        "shakargarh": [
            "shakargarh",
            "sgr"
        ],

        "shikarpur": [
            "shikarpur",
            "sip"
        ],

        "shorkot": [
            "shorkot",
            "shr"
        ],

        "shujabad": [
            "shujabad",
            "shu"
        ],

        "swabi": [
            "swabi",
            "swb"
        ],

        "swat": [
            "swat",
            "swt"
        ],

        "taxila": [
            "taxila",
            "txl"
        ],

        "timergara": [
            "timergara",
            "tmg"
        ],

        "toba tek singh": [
            "toba tek singh",
            "tts"
        ],

        "tulamba": [
            "tulamba",
            "tlb"
        ],

        "umerkot": [
            "umerkot",
            "ukt"
        ],

        "wazirabad": [
            "wazirabad",
            "wzd"
        ],

        "yazman": [
            "yazman",
            "yzn"
        ],

        "zafarwal": [
            "zafarwal",
            "zfr"
        ],

        "zhob": [
            "zhob",
            "zob"
        ]
    }

    # ===================================
    # DETECT CITY
    # ===================================

    @staticmethod
    def detect_city(text: str):

        if not text:

            return "unknown"

        # ===================================
        # CLEAN INPUT
        # ===================================

        cleaned_text = (
            text
            .lower()
            .strip()
        )

        cleaned_text = " ".join(
            cleaned_text.split()
        )

        text_words = (
            cleaned_text.split()
        )

        # ===================================
        # DETECT CITY
        # ===================================

        for city, aliases in (
            CityDetectionService
            .SUPPORTED_CITIES
            .items()
        ):

            for alias in aliases:

                alias_cleaned = (
                    alias
                    .lower()
                    .strip()
                )

                # ===========================
                # EXACT MATCH
                # ===========================

                if cleaned_text == alias_cleaned:

                    return city

                # ===========================
                # WORD MATCH
                # ===========================

                if alias_cleaned in text_words:

                    return city

                # ===========================
                # FULL TEXT MATCH
                # ===========================

                if alias_cleaned in cleaned_text:

                    return city

        # ===================================
        # NO MATCH
        # ===================================

        return "unknown"