# personal-profile

Public source of truth for personal profile data, generated resumes, CV, and portfolio content.

## Workflow

`career.yaml` is the only hand-maintained profile data file. Client definitions
under `clients/` decide which records and wording variants each output uses.

On changes to the source data or client rules, GitHub Actions:

1. Validates and resolves the YAML.
2. Generates the quantum, backend, and AI/ML resumes plus the CV.
3. Generates `public-profile.json` for the portfolio site.
4. Publishes the YAML, JSON, and PDFs through GitHub Pages.

The PDF generator uses the exact modular multi-resume template from Resumake
and the existing CV template. Local generation requires Python and the
dependencies in `requirements.txt`. If `latexmk` is installed, PDFs are built
as well:

```bash
pip install -r requirements.txt
python scripts/generate.py --all
```

LinkedIn synchronization is intentionally not included yet.
