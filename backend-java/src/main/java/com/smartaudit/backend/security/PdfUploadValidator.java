package com.smartaudit.backend.security;

import cn.hutool.core.util.StrUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;

@Component
public class PdfUploadValidator {

    private static final byte[] PDF_MAGIC = "%PDF-".getBytes(StandardCharsets.US_ASCII);

    @Value("${smartaudit.storage.max-pdf-bytes:31457280}")
    private long maxPdfBytes;

    public String validate(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("pdf file is required");
        }
        if (file.getSize() <= 0 || file.getSize() > maxPdfBytes) {
            throw new IllegalArgumentException("pdf file size is invalid or exceeds the configured limit");
        }
        String originalName = StrUtil.emptyToDefault(file.getOriginalFilename(), "contract.pdf");
        String safeName = safeBaseName(originalName);
        if (!StrUtil.endWithIgnoreCase(safeName, ".pdf")) {
            throw new IllegalArgumentException("only pdf file is supported");
        }
        String contentType = StrUtil.blankToDefault(file.getContentType(), "");
        if (!contentType.isEmpty() && !MediaTypes.isPdf(contentType)) {
            throw new IllegalArgumentException("uploaded content type is not PDF");
        }
        try (InputStream input = file.getInputStream()) {
            byte[] header = input.readNBytes(PDF_MAGIC.length);
            if (header.length != PDF_MAGIC.length) {
                throw new IllegalArgumentException("uploaded file is not a valid PDF");
            }
            for (int i = 0; i < PDF_MAGIC.length; i++) {
                if (header[i] != PDF_MAGIC[i]) {
                    throw new IllegalArgumentException("uploaded file is not a valid PDF");
                }
            }
        } catch (IOException ex) {
            throw new IllegalArgumentException("cannot read uploaded PDF", ex);
        }
        return safeName;
    }

    private String safeBaseName(String originalName) {
        try {
            String normalized = originalName.replace('\\', '/');
            String baseName = Path.of(normalized).getFileName().toString();
            if (StrUtil.isBlank(baseName) || baseName.indexOf('\0') >= 0 || baseName.length() > 255) {
                throw new IllegalArgumentException("invalid PDF filename");
            }
            return baseName;
        } catch (InvalidPathException ex) {
            throw new IllegalArgumentException("invalid PDF filename", ex);
        }
    }

    private static final class MediaTypes {
        private static boolean isPdf(String contentType) {
            return "application/pdf".equalsIgnoreCase(contentType)
                    || "application/octet-stream".equalsIgnoreCase(contentType);
        }
    }
}
