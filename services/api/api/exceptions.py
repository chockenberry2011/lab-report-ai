"""
Custom exceptions for the Lab AI API.

Defines specific exceptions for different error conditions that can occur
in the corrections and results processing system.
"""

from typing import Optional


class CorrectionsFileFormatError(Exception):
    """
    Raised when a corrections file has an invalid format.

    This is used when the corrections file exists but contains data
    in an unexpected format (e.g., object instead of array).
    """

    def __init__(
        self,
        result_id: str,
        file_path: str,
        expected_type: str = "array",
        found_type: str = "object",
        message: Optional[str] = None
    ):
        self.result_id = result_id
        self.file_path = file_path
        self.expected_type = expected_type
        self.found_type = found_type

        if message is None:
            message = (
                f"Corrections file for result_id='{result_id}' at path='{file_path}' "
                f"has wrong format: expected {expected_type}, found {found_type}"
            )

        super().__init__(message)

    def to_http_response_body(self) -> dict:
        """Convert the exception to an HTTP response body."""
        return {
            "error": "CORRECTIONS_FILE_WRONG_TYPE",
            "message": str(self),
            "expected": self.expected_type,
            "found": self.found_type,
            "result_id": self.result_id,
            "fix": "Run corrections migration or delete the file to allow recreation as an array"
        }