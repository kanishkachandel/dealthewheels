class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status_code = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class DuplicateTripException(DomainError):
    code = "DUPLICATE_TRIP"
    status_code = 409


class NoEligibleVendorException(DomainError):
    code = "NO_ELIGIBLE_VENDOR"
    status_code = 422


class VendorCapacityExceededException(DomainError):
    code = "VENDOR_CAPACITY_EXCEEDED"
    status_code = 422


class UnauthorizedException(DomainError):
    code = "UNAUTHORIZED"
    status_code = 401


class InvalidConfigurationException(DomainError):
    code = "INVALID_CONFIGURATION"
    status_code = 422
