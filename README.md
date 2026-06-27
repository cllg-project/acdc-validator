# ACDC Validator

A web application for collaborative validation and correction of OCR text extracted from historical book scans. Annotators are shown one line at a time alongside its image crop, confirm or correct the OCR output, and the results are exported as filtered ALTO XML files.

## Overview

Data is sourced from ALTO v4 XML files paired with page scans. Each `TextLine` in the XML becomes one annotation task. The application tracks which lines have been reviewed and by how many annotators, caps validation at two independent confirmations per line, and produces cleaned ALTO output containing only the validated lines.

## Requirements

- Python 3.14
- The packages listed in `requirements.txt` (Flask, Flask-SQLAlchemy, Flask-Migrate, Pillow, python-dotenv, …)

For running tests, also install `requirements-dev.txt` (adds pytest).

## Setup

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

Copy `.env` and set your values:

```
FLASK_APP=run.py
SECRET_KEY=<strong-random-value>
DATA_PATH=/path/to/book-samples   # directory containing manifest.csv and book subdirectories
DATABASE_URL=sqlite:///annotations.db   # or a PostgreSQL URL
```

Initialise the database schema:

```bash
flask db upgrade
```

Load data from the manifest and convert PNGs to JPEGs:

```bash
flask init
```

Create at least one user:

```bash
flask user add <username>
```

Run the development server:

```bash
flask run
```

## Data layout

`DATA_PATH` must contain a `manifest.csv` with columns `book_id`, `png`, and `alto_xml` (paths relative to `DATA_PATH`). Each row points to one page scan and its corresponding ALTO XML file. Book subdirectories sit alongside the manifest:

```
book-samples/
  manifest.csv
  erara__10064974/
    erara__10064974.pdf_page_270.png
    erara__10064974.pdf_page_270.png.xml
  ...
```

## Annotation workflow

The interface is split into two sequential steps.

**Step 1 — Validate** (`/validate`)  
The annotator sees a cropped image of one text line and the OCR string beneath it. Four actions are available:

| Action | Key | Meaning |
|---|---|---|
| Validate | V | OCR is correct as-is |
| Skip to edit | E | OCR needs correction; sends the line directly to Step 2 |
| Skip | S | Come back to this line later |
| Unsure / not qualified | U | Permanently removes the line from this annotator's queue |

A line is considered done once two independent annotators have validated or edited it.

**Step 2 — Review** (`/review`)  
Only lines that were flagged with "Skip to edit" in Step 1 appear here. The annotator sees the same image with a pre-filled text field (seeded from any prior correction). Actions: save edit, validate as-is, skip, or skip forever.

Betacode input is supported in Step 2: typing in Latin transliteration (e.g. `lo/gos`) is converted to Unicode Greek (`λόγος`) character by character.

## Line images

Each line image is served at `/image/<line_id>`. The crop is centred on the line's bounding box with horizontal padding and vertical context (2.5× the line height above and below). The polygon from the ALTO `<Shape>` element is used to grey out surrounding content, leaving the target line clearly readable.

## Validated view

`/validated` shows all lines that have received at least one validated or edited annotation. Images load lazily as cards scroll into view. The list can be filtered by book, status, and annotator.

## Export

```bash
flask export
```

Writes a `.post-cllg.xml` file next to each original ALTO that has at least one validated line. The output contains only the validated lines; if a line was edited, the corrected text replaces the original `String/@CONTENT`. Pages with no validated lines are skipped entirely.

## Statistics

`/stats` shows overall progress (validated, skipped, untouched), a per-user breakdown with action counts and average time per annotation, and an inter-annotator agreement matrix for any pair of users who have both annotated the same lines.

## CLI reference

```
flask init [--data-path PATH]      Load manifest, create tables, convert PNGs
flask user add <username>          Create a user (prompts for password)
flask user edit <username>         Change a user's password
flask export [--data-path PATH]    Write .post-cllg.xml files for validated pages
flask db upgrade                   Apply pending Alembic schema migrations
```

## Migrations and data scripts

Schema changes are managed with Alembic via `flask db upgrade`.

Two standalone data-migration scripts live in `scripts/`:

- `scripts/migrate_xml_line_ids.py` — backfills `xml_line_id` on each `Line` row from the `@ID` attribute of the corresponding `<TextLine>` element (run after `flask db upgrade`).
- `scripts/migrate_polygon_padding.py` — expands polygon point coordinates by a configurable number of pixels on the left and right sides (`--padding`, default 5). Supports `--dry-run`.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Tests use an in-memory SQLite database and fixture ALTO files under `tests/fixtures/`. They cover ALTO parsing, ingest correctness, the xml_line_id backfill logic, and polygon padding.

A GitHub Actions workflow (`.github/workflows/tests.yml`) runs the suite on every push and pull request to `main`.
