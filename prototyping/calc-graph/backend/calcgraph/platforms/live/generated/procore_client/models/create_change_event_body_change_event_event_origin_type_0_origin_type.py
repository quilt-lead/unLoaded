from enum import StrEnum


class CreateChangeEventBodyChangeEventEventOriginType0OriginType(StrEnum):
    COMMUNICATION = "communication"
    GENERIC_TOOLS = "generic_tools"
    MEETINGS = "meetings"
    OBSERVATIONS = "observations"
    RFI = "rfi"
    SITE_INSTRUCTIONS = "site_instructions"

    def __str__(self) -> str:
        return str(self.value)
