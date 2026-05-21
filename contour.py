
MODE_COLOR_DEFAULTS = {
    "Cycling":            ("#66BB6A", "#1B5E20"),
    "Walking":            ("#EF9A9A", "#B71C1C"),
    "Driving":            ("#64B5F6", "#0D47A1"),
    "Transit":            ("#FFB74D", "#E65100"),
    "Approximate Transit": ("#BA68C8", "#4A148C"),
    "Bus":                ("#FFB74D", "#E65100"),
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
        self.display_interval = interval
        self.time_penalty = 0
        self.features = None
        self.center_location = None
        defaults = MODE_COLOR_DEFAULTS.get(mode, ("#AAAAAA", "#333333"))
        self.start_color_hex = defaults[0]
        self.end_color_hex = defaults[1]

    def set_results(self, features, center_location):
        self.features = features
        self.center_location = center_location
