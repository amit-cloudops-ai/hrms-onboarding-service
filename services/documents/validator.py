
"""Validation helpers for employee onboarding documents."""

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

ALLOWED_DOCUMENT_TYPES = {
    "id_proof",
    "degree_certificate",
    "signed_offer_letter",
}

ALLOWED_FORMATS = {
    ".pdf": {
        "content_type": "application/pdf",
        "signature": b"%PDF-",
    },
    ".jpg": {
        "content_type": "image/jpeg",
        "signature": b"\xff\xd8\xff",
    },
    ".jpeg": {
        "content_type": "image/jpeg",
        "signature": b"\xff\xd8\xff",
    },
    ".png": {
        "content_type": "image/png",
        "signature": b"\x89PNG\r\n\x1a\n",
    },
}


def validate_document(
    doc_type,
    filename,
    content_type,
    file_size,
    file_content,
):
    """Validate document details and actual file signature."""

    if doc_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError("Unsupported document type")

    if not filename or "." not in filename:
        raise ValueError("Invalid filename")

    extension = "." + filename.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_FORMATS:
        raise ValueError("Unsupported file extension")

    expected = ALLOWED_FORMATS[extension]

    if content_type != expected["content_type"]:
        raise ValueError("Invalid content type")

    if type(file_size) is not int or file_size <= 0:
        raise ValueError("Invalid file size")

    if file_size > MAX_FILE_SIZE:
        raise ValueError("File exceeds the 5 MB limit")

    if not isinstance(file_content, bytes):
        raise ValueError("File content must be bytes")

    if len(file_content) != file_size:
        raise ValueError("File size does not match content")

    if not file_content.startswith(expected["signature"]):
        raise ValueError("File signature does not match file type")

    return True
