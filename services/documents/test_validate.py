
import unittest

from validator import validate_document, MAX_FILE_SIZE


class TestDocumentValidator(unittest.TestCase):

    def test_valid_pdf(self):
        result = validate_document(
            "id_proof",
            "identity.pdf",
            "application/pdf",
            9,
            b"%PDF-1234",
        )
        self.assertTrue(result)

    def test_valid_jpg(self):
        result = validate_document(
            "id_proof",
            "photo.jpg",
            "image/jpeg",
            6,
            b"\xff\xd8\xffabc",
        )
        self.assertTrue(result)

    def test_valid_png(self):
        content = b"\x89PNG\r\n\x1a\nabc"

        result = validate_document(
            "degree_certificate",
            "certificate.png",
            "image/png",
            len(content),
            content,
        )
        self.assertTrue(result)

    def test_invalid_document_type(self):
        with self.assertRaises(ValueError):
            validate_document(
                "passport",
                "identity.pdf",
                "application/pdf",
                9,
                b"%PDF-1234",
            )

    def test_invalid_extension(self):
        with self.assertRaises(ValueError):
            validate_document(
                "id_proof",
                "identity.exe",
                "application/pdf",
                9,
                b"%PDF-1234",
            )

    def test_invalid_content_type(self):
        with self.assertRaises(ValueError):
            validate_document(
                "id_proof",
                "identity.pdf",
                "image/jpeg",
                9,
                b"%PDF-1234",
            )

    def test_file_exceeds_5_mb(self):
        content = b"%PDF-" + b"A" * MAX_FILE_SIZE

        with self.assertRaises(ValueError):
            validate_document(
                "id_proof",
                "identity.pdf",
                "application/pdf",
                len(content),
                content,
            )

    def test_wrong_file_signature(self):
        with self.assertRaises(ValueError):
            validate_document(
                "id_proof",
                "identity.pdf",
                "application/pdf",
                9,
                b"NOT-A-PDF",
            )

    def test_file_size_mismatch(self):
        with self.assertRaises(ValueError):
            validate_document(
                "id_proof",
                "identity.pdf",
                "application/pdf",
                100,
                b"%PDF-1234",
            )


if __name__ == "__main__":
    unittest.main()
