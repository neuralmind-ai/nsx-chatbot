from enum import Enum

class SearchTool(str, Enum):
    FAQ = "FAQ"
    NSX = "NSX"
    SENSE = "SENSE"

    def __repr__(self) -> str:
        return self.value

    def __str__(self) -> str:
        return self.value