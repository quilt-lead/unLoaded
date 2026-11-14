from enum import StrEnum


class ProcoreChangeOrderPackageType(StrEnum):
    CHANGEORDERPACKAGE = "ChangeOrderPackage"
    COMMITMENTCONTRACTCHANGEORDER = "CommitmentContractChangeOrder"
    PRIMECONTRACTCHANGEORDER = "PrimeContractChangeOrder"

    def __str__(self) -> str:
        return str(self.value)
