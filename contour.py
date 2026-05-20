
class Contour:
    def __init__(self, mode: str, location: str, max_time: int, interval: int, color: str = "Default"):
        self.mode = mode
        self.location = location
        self.max_time = max_time
        self.interval = interval
        self.color = color
        self.visible = True
        self.name = f"{mode}, {location}"
        self.features = None
        self.center_location = None

    def update_color(self, new_color: str):
        self.color = new_color

    def set_results(self, features, center_location):
        self.features = features
        self.center_location = center_location
