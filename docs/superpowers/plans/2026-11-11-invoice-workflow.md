# Invoice workflow implementation plan

> Execute inline using test-driven development and verify the complete upload, edit, generate, download flow.

**Goal:** Make the existing local invoice application usable with its current Orders, Boxes, and Invoice Excel template.

**Architecture:** Retain React/Vite, FastAPI, pdfplumber, RapidOCR, and openpyxl. Extract locally, allow manual corrections, and export using the supplied template. One invoice per PDF, including multipage invoices; batches contain multiple PDFs.

**Requirements:** Preserve the current sheet names, columns, Reason column, and template formatting. Keep OCR review warnings. Do not send invoices to external services. Treat this as a local application, with sessions and defaults held in memory until server restart.

**Review focus:** Corrections must clear stale warnings; duplicate IDs must be rechecked across a batch; filenames must not escape upload storage; bad configuration must not partially update defaults; spreadsheet text must remain text.

## Tasks

- [x] Add failing regression tests in tests/test_workflow.py for missing settings routes, stale validation, duplicate correction, unsafe or invalid uploads, and literal Excel text.
- [x] Repair backend/app/main.py, config.py, validator.py and excel_generator.py against those tests. Respect deployment paths and run one server worker while sessions remain in memory.
- [x] Update frontend/src/App.tsx so defaults errors are visible, edited batches refresh, and stale downloads clear after editing.
- [x] Declare OCR dependencies, migrate obsolete test imports to the active implementation, and replace inaccurate setup documentation with verified instructions.
- [x] Run the full pytest suite, build the frontend, exercise real PDF upload and download, and launch the local application.

## Execution notes

- Baseline: frontend builds; active pipeline tests pass (8), including real OCR. Full test discovery fails on obsolete app.models.schemas and app.config.settings imports.
- Repository has no commits and all existing files are untracked. Work in place, preserve existing artifacts, and do not create a baseline commit of user invoices or environment files.
- User accepted the offered current-format implementation. Continue without another design approval step.

## Verification and review

- Full suite: 28 passed, including real OCR; one upstream Starlette TestClient deprecation warning. Frontend production build passes.
- Browser smoke test: settings validation, multi-PDF upload, edit, manual box defaults, regeneration, and download pass. Downloaded workbook values checked with openpyxl.
- Fresh reviewer found stale PO fallback warnings and hardcoded new-box dimensions. Both reproduced with failing tests, fixed, and verified.
- Deliberate MVP limits: in-memory state, no authentication, one backend worker, one invoice per PDF, no mixed-page OCR. Existing individual box validation remains limited; users must review dimensions before importing. Concurrent editing across tabs is not guaranteed.
- No Git commit or deployment performed. Docker configuration updated but no Docker image build tested.
