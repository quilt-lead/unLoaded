from enum import StrEnum


class SortBy(StrEnum):
    ASSIGNEDTO = "assignedTo"
    ASSIGNEDTOTYPE = "assignedToType"
    CLOSEDAT = "closedAt"
    CLOSEDBY = "closedBy"
    CREATEDAT = "createdAt"
    CREATEDBY = "createdBy"
    CUSTOMATTRIBUTES = "customAttributes"
    DESCRIPTION = "description"
    DISPLAYID = "displayId"
    DUEDATE = "dueDate"
    ISSUESUBTYPE = "issueSubType"
    ISSUETYPE = "issueType"
    LOCATIONDETAILS = "locationDetails"
    PUBLISHED = "published"
    STARTDATE = "startDate"
    STATUS = "status"
    TITLE = "title"
    UPDATEDAT = "updatedAt"

    def __str__(self) -> str:
        return str(self.value)
