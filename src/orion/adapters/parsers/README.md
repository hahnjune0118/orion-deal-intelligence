# Native source parsing

`NativeParser.parse_document(bytes, Document metadata)` parses PDF, DOCX and
PPTX into the existing `Document` and `SourceSpan` contracts. It runs the parser
in an isolated child process with a 20-second timeout. File size is at most
10 MiB, PDF pages/PPTX slides at most 50, expanded OOXML at most 64 MiB, text at
most 100,000 characters/document and 300,000 characters in a legacy deal pack.
POSIX worker processes additionally apply a 768 MiB address-space limit. That
OS resource guard is unavailable on Windows; all other bounds still apply.
Native Windows execution remains unverified.

PDF locator `block_index=0` means the entire extracted text of the requested
page. It is deliberately not a reconstructed visual paragraph. PDF units retain
actual extracted line breaks. DOCX body paragraph indices count actual body
paragraph/table blocks (excluding `sectPr`); paragraph_index is zero. Tables use
native table/row/column/paragraph indices. DOCX does not expose page numbers.
PPTX locators use real slide, shape ID, paragraph and optional table-cell indices.

Merged/nested tables, tracked changes, fields, text in images, charts, speaker
notes, substantive headers/footers, active PDF forms and external relationships
are not silently interpreted. They cause a manual-review status and unverified
spans. Scans return `needs_ocr`, encrypted PDFs require manual review, malformed
sources fail. These fallbacks are not counted as successful extraction.

`NativeSourceIndex` stores original immutable bytes and an independently parsed
index. Source validation resolves caller locators against that index and checks
the recorded source SHA-256. The supplied SourceSpan text is never its own
verification source. SourceSpan generated IDs bind full document ID/version,
file SHA-256, parser version and locator. Any changed source yields new IDs.

Small identical files may reuse a bounded immutable parse-output cache, keyed by
full source bytes and all metadata. The cache stores at most 32 outputs and only
files <=1 MiB; large files bypass it. Every returned Pydantic value is reconstructed.
Neither approval state nor deal snapshots are cached.

The 12 native examples retain the original three Foundation scenarios. They are
separate from the extended Northstar/manufacturing research packs. The native
runtime conversion deliberately creates new seeds in `data/parsed/`; it does
not rewrite the original `spec/` or `resources/demo/` snapshots or audit history.
`source_mapping.json` records old/native locators and input digest changes.

Source text, including malicious instruction-like text, remains untrusted plain
text. Retrieval returns candidates and never performs actions. A future UI must
escape these strings; this module does not produce HTML.
