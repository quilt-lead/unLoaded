from enum import StrEnum


class GetRfiResponse200CostImpactType0Status(StrEnum):
    NO_IMPACT = "no_impact"
    N_A = "n_a"
    TBD = "tbd"
    YES_KNOWN = "yes_known"
    YES_UNKNOWN = "yes_unknown"

    def __str__(self) -> str:
        return str(self.value)
