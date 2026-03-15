from fastapi import HTTPException, status

from app.api.errors import value_error_as_http_exception


def test_value_error_as_http_exception_default():
    exc = ValueError("Some generic error")
    http_exc = value_error_as_http_exception(exc)
    assert isinstance(http_exc, HTTPException)
    assert http_exc.status_code == status.HTTP_400_BAD_REQUEST
    assert http_exc.detail == "Some generic error"


def test_value_error_as_http_exception_not_found():
    exc = ValueError("The requested item was not found")
    http_exc = value_error_as_http_exception(exc)
    assert isinstance(http_exc, HTTPException)
    assert http_exc.status_code == status.HTTP_404_NOT_FOUND
    assert http_exc.detail == "The requested item was not found"


def test_value_error_as_http_exception_not_found_case_insensitive():
    exc = ValueError("NOT FOUND")
    http_exc = value_error_as_http_exception(exc)
    assert isinstance(http_exc, HTTPException)
    assert http_exc.status_code == status.HTTP_404_NOT_FOUND
    assert http_exc.detail == "NOT FOUND"


def test_value_error_as_http_exception_custom_default_status():
    exc = ValueError("Some other error")
    http_exc = value_error_as_http_exception(
        exc, default_status=status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    assert isinstance(http_exc, HTTPException)
    assert http_exc.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert http_exc.detail == "Some other error"
