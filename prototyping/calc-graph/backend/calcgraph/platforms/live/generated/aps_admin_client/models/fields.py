from enum import StrEnum


class Fields(StrEnum):
    ACCOUNTID = "accountId"
    ADDRESSLINE1 = "addressLine1"
    ADDRESSLINE2 = "addressLine2"
    BUSINESSUNITID = "businessUnitId"
    CITY = "city"
    COMPANYCOUNT = "companyCount"
    CONSTRUCTIONTYPE = "constructionType"
    COUNTRY = "country"
    CREATEDAT = "createdAt"
    DELIVERYMETHOD = "deliveryMethod"
    ENDDATE = "endDate"
    IMAGEURL = "imageUrl"
    JOBNUMBER = "jobNumber"
    LASTSIGNIN = "lastSignIn"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    MEMBERCOUNT = "memberCount"
    NAME = "name"
    PLATFORM = "platform"
    POSTALCODE = "postalCode"
    PRODUCTS = "products"
    PROJECTVALUE = "projectValue"
    SHEETCOUNT = "sheetCount"
    STARTDATE = "startDate"
    STATEORPROVINCE = "stateOrProvince"
    STATUS = "status"
    THUMBNAILIMAGEURL = "thumbnailImageUrl"
    TIMEZONE = "timezone"
    TYPE = "type"
    UPDATEDAT = "updatedAt"

    def __str__(self) -> str:
        return str(self.value)
