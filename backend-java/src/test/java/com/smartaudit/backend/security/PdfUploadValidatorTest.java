package com.smartaudit.backend.security;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class PdfUploadValidatorTest {

    private PdfUploadValidator validator;

    @BeforeEach
    void setUp() {
        validator = new PdfUploadValidator();
        ReflectionTestUtils.setField(validator, "maxPdfBytes", 1024L);
    }

    @Test
    void acceptsPdfAndStripsClientPath() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "../../contract.pdf", "application/pdf", "%PDF-1.7\nbody".getBytes());
        assertEquals("contract.pdf", validator.validate(file));
    }

    @Test
    void rejectsSpoofedPdfExtension() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "contract.pdf", "application/pdf", "not a pdf".getBytes());
        assertThrows(IllegalArgumentException.class, () -> validator.validate(file));
    }

    @Test
    void rejectsUnexpectedContentTypeAndOversizeFile() {
        MockMultipartFile wrongType = new MockMultipartFile(
                "file", "contract.pdf", "text/plain", "%PDF-1.7".getBytes());
        assertThrows(IllegalArgumentException.class, () -> validator.validate(wrongType));

        ReflectionTestUtils.setField(validator, "maxPdfBytes", 4L);
        MockMultipartFile tooLarge = new MockMultipartFile(
                "file", "contract.pdf", "application/pdf", "%PDF-1.7".getBytes());
        assertThrows(IllegalArgumentException.class, () -> validator.validate(tooLarge));
    }
}
