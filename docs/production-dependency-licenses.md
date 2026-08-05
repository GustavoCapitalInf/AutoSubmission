# Production Dependency License Review

This file is an engineering inventory, not legal advice. Legal counsel or the
company's license owner must approve the final deployment and distribution model.

Reviewed on August 4, 2026.

Primary references:

- [Unlimited OCR upstream repository](https://github.com/baidu/Unlimited-OCR)
- [Tesseract user manual](https://tesseract-ocr.github.io/tessdoc/)
- [Gemini API paid-service terms](https://ai.google.dev/gemini-api/terms)
- [PyMuPDF licensing FAQ](https://pymupdf.readthedocs.io/en/latest/faq/index.html)
- [Poppler project](https://poppler.freedesktop.org/)

## Runtime Components

| Component | Use | License / service terms | Production action |
| --- | --- | --- | --- |
| Unlimited OCR | Layout-aware visual OCR model | MIT in the upstream Baidu repository | Preserve the upstream license and notices with deployed model artifacts. |
| Tesseract OCR | Local scanned-text preflight | Apache License 2.0 | Preserve required copyright and license notices. |
| Gemini API | Unknown-layout structured extraction | Google Gemini API paid-service terms | Use a Cloud project with active billing and complete privacy, DPA, residency, and retention review. Never submit customer statements through the unpaid tier. |
| PyMuPDF / MuPDF | Native PDF text and geometry | GNU AGPL or commercial Artifex license | Proprietary deployment requires confirmed AGPL compliance or a commercial license before release. |
| Poppler | PDF rasterization through `pdf2image` | Poppler contains GPL-licensed components | Have counsel approve server-side command-line use and packaging, or replace it with an approved permissive/commercial renderer. |

## Current Release Gates

The application is technically capable of running these components, but a
proprietary production release must not claim dependency-license clearance until:

1. The company records its chosen PyMuPDF/MuPDF license basis.
2. Counsel reviews the exact Poppler installation and distribution topology.
3. Third-party notices are generated for the pinned production dependency set.
4. The Gemini key belongs to a billing-enabled project governed by the approved
   data-processing terms.
5. Unlimited OCR model and code notices are retained in the deployed artifact.

## Cost-Sensitive Resolution Options

- Obtain a PyMuPDF commercial license if its proven geometry behavior is worth
  more than migration and regression risk.
- Otherwise benchmark permissively licensed PDF text/geometry and rendering
  replacements against the complete statement corpus before removing PyMuPDF or
  Poppler.
- Do not change a PDF engine only on license metadata; native extraction order
  affects transaction ownership and must pass all corpus and balance audits.
