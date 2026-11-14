from enum import StrEnum


class ListProjectsResponse200ItemWorkScopeType3Type1(StrEnum):
    MAINTENANCE_SERVICE = "maintenance_service"
    NEW_CONSTRUCTION = "new_construction"
    RENOVATION_ALTERATION = "renovation_alteration"

    def __str__(self) -> str:
        return str(self.value)
