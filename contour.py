
MODE_COLOR_DEFAULTS = {
    "Cycling":            ("#90EE90", "#228B22"),
    "Walking":            ("#FFB6C1", "#8B0000"),
    "Driving":            ("#87CEEB", "#00008B"),
    "Transit":            ("#FFDAB9", "#D2691E"),
    "Approximate Transit": ("#FFC0CB", "#B22222"),
    "Bus":                ("#FFDAB9", "#D2691E"),
}

class Contour:
    def __init__(self, mode: str, location: str, max_time: int, interval: int):
        self.mode = mode
        self.location = location
        self.max_time = max_time
        self.interval = interval
        self.visible = True
        self.name = mode
        self.band_style = "None"
        self.features = None
        self.center_location = None
        defaults = MODE_COLOR_DEFAULTS.get(mode, ("#AAAAAA", "#333333"))
        self.start_color_hex = defaults[0]
        self.end_color_hex = defaults[1]

    def set_results(self, features, center_location):
        self.features = features
        self.center_location = center_location
