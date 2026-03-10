from fastapi import HTTPException, status


def value_error_as_http_exception(
    exc: ValueError,
    *,
    default_status: int = status.HTTP_400_BAD_REQUEST,
) -> HTTPException:
    detail = str(exc)
    status_code = (
        status.HTTP_404_NOT_FOUND
        if "not found" in detail.lower()
        else default_status
    )
    return HTTPException(status_code=status_code, detail=detail)
