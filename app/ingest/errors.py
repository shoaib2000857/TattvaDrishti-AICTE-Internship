class IngestError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class InvalidLinkError(IngestError):
    def __init__(self, message: str) -> None:
        super().__init__(400, "invalid_url", message)


class RateLimitedError(IngestError):
    def __init__(self, message: str = "The source platform rate-limited this request.") -> None:
        super().__init__(429, "rate_limited", message)


class PrivateSourceError(IngestError):
    def __init__(self, message: str) -> None:
        super().__init__(403, "private_source", message)


class DeletedContentError(IngestError):
    def __init__(self, message: str) -> None:
        super().__init__(410, "deleted_content", message)


class ExtractionError(IngestError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(status_code, "extraction_failed", message)
