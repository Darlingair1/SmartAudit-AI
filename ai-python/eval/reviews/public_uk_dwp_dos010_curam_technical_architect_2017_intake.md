# Public PDF Intake Review

## Decision

SUITABLE WITH LIMITATIONS

The PDF is suitable as a `rag_eval_dev_v1` candidate document. It has reliable
searchable text, stable physical-page mapping, extensive contract clauses, and
public-source provenance. It is not yet part of the formal manifest because the
current development baseline candidate is frozen and this document has no
reviewed evaluation cases yet.

## Identity And Provenance

- Proposed document ID: `public_uk_dwp_dos010_curam_technical_architect_2017`
- Stable filename: `uk_dwp_dos010_curam_technical_architect_call_off_contract_2017.pdf`
- Contract: `DOS_010 - CURAM Technical Architect required for the delivery of a Cúram upgrade`
- Buyer: UK Department for Work and Pensions (DWP)
- Supplier: IBM United Kingdom Limited
- Framework: Digital Outcomes & Specialists 2 Framework Agreement (`RM1043iv`)
- Contract type: Call-Off Contract for digital/software professional services
- Contract value: GBP 137,229.40, excluding VAT where stated in the Order Form
- Start/order date: 2017-08-29
- Initial end date: 2017-12-22
- Official source: UK Contracts Finder
- Attachment URL: https://www.contractsfinder.service.gov.uk/Notice/Attachment/151314ec-09ed-4149-a303-3c3c999457ae
- Reuse license: no explicit reuse license was confirmed during this intake review

## Canonical Extraction

- Environment: Python 3.11.5, pypdf 6.14.2
- Physical pages: 41
- Canonical parsed pages: 41
- Empty pages: 0
- Pages under 60 extracted characters: 0
- Unicode replacement characters: 0 on all pages
- Document SHA256: `dd1f1e1da81075a1fb9f40d313f2c531ad9b7da9b61f4defb36d0a8c7fe9760b`
- Extraction SHA256: `148357ca818fc3972ba37a4312da34e05323e614210b4c573e659baaf38aed34`
- Characters per page: `2088, 1789, 2389, 2760, 1640, 2681, 2384, 2803, 2603, 660, 2317, 3070, 1715, 1196, 1333, 1839, 556, 3217, 2942, 3010, 3591, 4157, 4255, 4666, 3828, 3732, 3357, 4324, 3986, 3756, 3449, 3673, 4234, 3329, 3149, 3891, 3578, 3371, 3267, 2760, 499`

Production parser quality is `WARNING`, not `BAD`. OCR is not required and no
fallback is required. Physical page ordering is preserved 1:1.

## Parent And Child Diagnostic

- Production chunk settings: parent 500-1200 approximate tokens; child 250 tokens; overlap 60 tokens
- Parent count: 41
- Child count: 332
- Empty Parent/Child chunks: 0/0
- Parent mapping: exactly one Parent per physical page
- Cross-page Child chunks: 0
- Parents over the configured approximate maximum: 28

The oversized Parents result from dense single PDF pages. The current builder
does not split one physical page into multiple Parents, even when that page is
larger than the configured Parent maximum. This intake does not change chunk
parameters or production behavior.

## Visual And Privacy Review

Pages 1, 2, 10, 21, and 41 were rendered and inspected. Text is clear and
legible, tables are aligned, and there is no clipping or overlap. The Order Form
visually confirms the buyer, supplier, value, dates, and framework reference.

Names, titles, personal contact details, signatures, staff details, day rates,
and selected commercial values are explicitly marked `[REDACTED]`. The visible
invoice email is an organizational DWP/SSCL mailbox rather than a personal
address. No visible handwritten signature, personal phone number, or bank
account was found in the sampled pages.

## Known Limitations

- Every page repeats the contract title and project title; pages 2-41 also
  repeat a separator and the `Page N of 41` footer. This text enters production
  chunks and can create lexical noise.
- Several clauses continue across physical pages. Future Gold must remain
  page-local and use separate evidence objects for each physical page.
- Embedded attachment icons on pages such as 10 and 41 do not expose the full
  attachment contents through the canonical page extractor.
- Redacted Schedule and pricing fields cannot be used as Gold evidence.
- The document is long and framework-heavy. Candidate cases should distinguish
  project-specific Order Form/SOW terms from generic framework clauses.

## Benchmark Value

The document is particularly useful for multi-page and multi-parent retrieval:
each page is a distinct Parent, while related rules are distributed across the
Order Form, SOW, and general terms. It also provides natural hard negatives for
contract dates versus extension dates, Order Form value versus SOW charges,
termination versus consequences of termination, confidentiality versus data
protection, and general terms versus project-specific terms.

## Suggested Manifest Entry

```json
{
  "document_id": "public_uk_dwp_dos010_curam_technical_architect_2017",
  "path": "../documents/public/uk_dwp_dos010_curam_technical_architect_call_off_contract_2017.pdf",
  "source_type": "public",
  "sha256": "dd1f1e1da81075a1fb9f40d313f2c531ad9b7da9b61f4defb36d0a8c7fe9760b",
  "metadata": {
    "purpose": "development_benchmark",
    "document_title": "DOS_010 - CURAM Technical Architect required for the delivery of a Cúram upgrade",
    "buyer": "UK Department for Work and Pensions",
    "supplier": "IBM United Kingdom Limited",
    "framework": "Digital Outcomes & Specialists 2 Framework Agreement (RM1043iv)",
    "contract_date": "2017-08-29",
    "contract_end_date": "2017-12-22",
    "contract_value": 137229.40,
    "currency": "GBP",
    "physical_page_count": 41,
    "extraction_sha256": "148357ca818fc3972ba37a4312da34e05323e614210b4c573e659baaf38aed34",
    "canonical_extraction_environment": {
      "python_version": "3.11.5",
      "pypdf_version": "6.14.2"
    },
    "official_attachment_url": "https://www.contractsfinder.service.gov.uk/Notice/Attachment/151314ec-09ed-4149-a303-3c3c999457ae",
    "redaction_status": "Published copy contains explicit redactions for personal and selected commercial information.",
    "license": "No explicit reuse license confirmed."
  }
}
```
