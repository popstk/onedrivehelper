from enum import IntEnum
from enum import unique

# https://docs.microsoft.com/zh-cn/onedrive/developer/sp2019/docs/rest-api/concepts/errors?view=odsp-graph-online


@unique
class StatusCode(IntEnum):
    BadRequest = 400
    Unauthorized = 401
    Forbidden = 403
    NotFound = 404
    MethodNotAllowed = 405
    NotAcceptable = 406
    Conflict = 409
    Gone = 410
    LengthRequired = 411
    PreconditionFailed = 412
    RequestEntityTooLarge = 413
    UnsupportedMediaType = 415
    RequestedRangeNotSatisfiable = 416
    UnprocessableEntity = 422
    TooManyRequests = 429
    InternalServerError = 500
    NotImplemented = 501,
    ServiceUnavailable = 503
    InsufficientStorage = 507
    BandwidthLimitExceeded = 509
