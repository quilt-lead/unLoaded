from enum import StrEnum


class Fields(StrEnum):
    ASSIGNEDTO = "assignedTo"
    ASSIGNEDTOTYPE = "assignedToType"
    CLOSEDAT = "closedAt"
    CLOSEDBY = "closedBy"
    COMMENTCOUNT = "commentCount"
    CREATEDAT = "createdAt"
    CREATEDBY = "createdBy"
    CUSTOMATTRIBUTES = "customAttributes"
    DESCRIPTION = "description"
    DISPLAYID = "displayId"
    DUEDATE = "dueDate"
    ID = "id"
    ISSUESUBTYPEID = "issueSubtypeId"
    ISSUETYPEID = "issueTypeId"
    LOCATIONDETAILS = "locationDetails"
    LOCATIONID = "locationId"
    OPENEDAT = "openedAt"
    OPENEDBY = "openedBy"
    PERMITTEDACTIONS = "permittedActions"
    PERMITTEDATTRIBUTES = "permittedAttributes"
    PERMITTEDSTATUSES = "permittedStatuses"
    PUBLISHED = "published"
    ROOTCAUSEID = "rootCauseId"
    ROOTCAUSETITLE = "rootCauseTitle"
    STARTDATE = "startDate"
    STATUS = "status"
    TITLE = "title"
    UPDATEDAT = "updatedAt"
    UPDATEDBY = "updatedBy"

    def __str__(self) -> str:
        return str(self.value)
