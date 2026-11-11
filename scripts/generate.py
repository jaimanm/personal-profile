#!/usr/bin/env python3
"""Generate resumes, a CV, and public profile data from career.yaml."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "career.yaml"
CLIENTS = ROOT / "clients"
OUT = ROOT / "generated"
MANIFEST = OUT / "manifest.json"
RESUME_TEMPLATE = ROOT / "templates" / "resumake" / "modular-multi" / "resume_preamble.tex"
CV_TEMPLATE = ROOT / "templates" / "cv" / "cv_preamble.tex"
TEMPLATE_VERSION = "5"


def load_yaml(path: Path) -> dict:
    with path.open() as handle:
        return yaml.safe_load(handle) or {}


def escape(value: object) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in str(value))


def fingerprint(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def selected(records: list[dict], ids: list[str]) -> list[dict]:
    by_id = {record["id"]: record for record in records}
    missing = [item for item in ids if item not in by_id]
    if missing:
        raise ValueError(f"Unknown record IDs: {', '.join(missing)}")
    return [by_id[item] for item in ids]


def bullet_text(bullet: dict, key: str) -> str:
    return bullet.get("variants", {}).get(key, bullet["default"])


def heading(data: dict) -> str:
    profile = data["profile"]
    return "\n".join(
        [
            r"\begin{center}",
            rf"\textbf{{\Huge \scshape {escape(profile['name'])}}} \\ \vspace{{1pt}}",
            rf"\small \href{{mailto:{profile['email']}}}{{\underline{{{escape(profile['email'])}}}}} $|$",
            rf"\href{{{profile['linkedin']}}}{{\underline{{linkedin.com/in/jaimanmunshi}}}} $|$",
            rf"\href{{{profile['website']}}}{{\underline{{jaimanm.github.io}}}}%",
            r"\end{center}",
        ]
    )


def item_list(items: list[str]) -> str:
    if not items:
        return ""
    return "\n".join(
        [
            r"\resumeItemListStart",
            *[rf"\resumeItem{{{escape(item)}}}" for item in items],
            r"\resumeItemListEnd",
        ]
    )


def role_block(role: dict, key: str, max_bullets: int | None = None) -> str:
    source_bullets = role.get("bullets", [])
    bullets = item_list([bullet_text(item, key) for item in source_bullets[:max_bullets]])
    return "\n".join(
        [
            r"\resumeProjectHeading",
            rf"{{\textbf{{{escape(role['organization'])}}} $|$ \emph{{{escape(role['role'])}}}}}{{{escape(role['start'])} -- {escape(role['end'])}}}",
            bullets,
        ]
    )


def project_block(project: dict, key: str, max_bullets: int | None = None) -> str:
    title = escape(project["title"])
    if project.get("links"):
        title = rf"\href{{{project['links'][0]['url']}}}{{\underline{{{title}}}}}"
    source_bullets = project.get("bullets", [])
    bullets = item_list([bullet_text(item, key) for item in source_bullets[:max_bullets]])
    return "\n".join(
        [
            r"\resumeProjectHeading",
            rf"{{\textbf{{{title}}} $|$ \emph{{{escape(', '.join(project.get('technologies', [])))}}}}}{{{escape(project.get('date', ''))}}}",
            bullets,
        ]
    )


def skills_block(data: dict, client: dict) -> str:
    rows = [
        rf"\textbf{{{escape(skill['category'])}}}: {escape(', '.join(skill['items']))} \\"
        for skill in data["skills"]
        if skill["category"] in client.get("skill_categories", [])
    ]
    return "\n".join(
        [
            r"\begin{itemize}[leftmargin=0.15in, label={}]",
            r"\small{\item{",
            *rows,
            r"}}",
            r"\end{itemize}",
        ]
    )


def common_education(data: dict) -> str:
    education = data["education"][0]
    return "\n".join(
        [
            r"\section{Education}",
            r"\resumeSubHeadingListStart",
            rf"\resumeSubheading{{{escape(education['institution'])}}}{{{escape(education['location'])}}}{{{escape(education['degree'])} $|$ GPA: {escape(education['gpa'])}}}{{Graduation: {escape(education['graduation'])}}}",
            item_list(
                [
                    "Minors: " + ", ".join(education["minors"]),
                    "Relevant Coursework: " + ", ".join(education["coursework"]),
                ]
            ),
            r"\resumeSubHeadingListEnd",
        ]
    )


def render_resume(data: dict, client: dict) -> str:
    key = client.get("variant_key", "default")
    include = client["include"]
    max_bullets = client.get("max_bullets")
    experiences = selected(data["experience"], include["experience"])
    projects = selected(data["projects"], include["projects"])
    certifications = selected(data["certifications"], include.get("certifications", []))
    sections = [
        RESUME_TEMPLATE.read_text(),
        r"\begin{document}",
        heading(data),
        common_education(data),
        r"\section{Experience}",
        r"\resumeSubHeadingListStart",
        *[role_block(role, key, max_bullets) for role in experiences],
        r"\resumeSubHeadingListEnd",
        r"\section{Projects}",
        r"\resumeSubHeadingListStart",
        *[project_block(project, key, max_bullets) for project in projects],
        r"\resumeSubHeadingListEnd",
        r"\section{Certifications}",
        r"\resumeSubHeadingListStart",
        *[
            rf"\resumeProjectHeading{{\textbf{{{escape(cert['name'])}}}}}{{{escape(cert['date'])}}}"
            for cert in certifications
        ],
        r"\resumeSubHeadingListEnd",
        r"\section{Technical Skills}",
        skills_block(data, client),
        r"\end{document}",
    ]
    return "\n".join(section for section in sections if section)


def render_cv(data: dict, client: dict) -> str:
    key = client.get("variant_key", "default")
    include = client["include"]
    experiences = selected(data["experience"], include["experience"])
    projects = selected(data["projects"], include["projects"])
    certifications = selected(data["certifications"], include.get("certifications", []))
    lines = [
        CV_TEMPLATE.read_text(),
        r"\begin{document}",
        heading(data),
        r"\section{Objective}",
        rf"\small{{{escape(data['profile']['description'])} First author of published quantum ML research (arXiv:2607.14160) and an IBM Certified Qiskit Developer.}}",
        common_education(data),
        r"\section{Experience}",
        r"\resumeSubHeadingListStart",
        *[role_block(role, key) for role in experiences],
        r"\resumeSubHeadingListEnd",
        r"\section{Publications}",
        r"\resumeSubHeadingListStart",
    ]
    lines.extend(
        rf"\resumeProjectHeading{{\textbf{{\href{{{paper['url']}}}{{\underline{{{escape(paper['title'])}}}}}}} $|$ \emph{{{escape(paper['role'])}}}}}{{{escape(paper['date'])}}}"
        for paper in data["publications"]
    )
    lines.extend([r"\resumeSubHeadingListEnd", r"\section{Technical Projects}", r"\resumeSubHeadingListStart"])
    lines.extend(project_block(project, key) for project in projects)
    lines.extend([r"\resumeSubHeadingListEnd", r"\section{Technical Skills}", skills_block(data, client)])
    lines.extend([r"\section{Honors \& Awards}", r"\resumeSubHeadingListStart"])
    lines.extend(
        rf"\resumeAwardItem{{{escape(honor['title'])}}}{{{escape(honor.get('organization', ''))}}}{{}}{{{escape(honor['date'])}}}"
        for honor in data["honors"]
        if "cv" in honor.get("tags", [])
    )
    lines.extend([r"\resumeSubHeadingListEnd", r"\section{Certificates}", r"\resumeSubHeadingListStart"])
    lines.extend(
        rf"\resumeProjectHeading{{\textbf{{{escape(cert['name'])}}}}}{{{escape(cert['date'])}}}"
        for cert in certifications
    )
    lines.extend([r"\resumeSubHeadingListEnd", r"\section{Extracurricular Activities}", r"\resumeSubHeadingListStart"])
    lines.extend(
        rf"\resumeProjectHeading{{\textbf{{{escape(item['organization'])}}} $|$ \emph{{{escape(item['role'])}}}}}{{{escape(item['start'])} -- {escape(item['end'])}}}"
        for item in data["extracurricular"]
    )
    lines.extend([r"\resumeSubHeadingListEnd", r"\end{document}"])
    return "\n".join(lines)


def public_projection(data: dict) -> dict:
    profile = data["profile"]
    return {
        "personal": {**profile, "profileImage": profile.get("profile_image")},
        "hero": {"typedLines": profile.get("typed_lines", [])},
        "projects": [
            {
                "id": project["id"],
                "title": project["title"],
                "category": " ".join(project.get("tags", [])),
                "tags": project.get("tags", []),
                "description": project["description"],
                "tech": project.get("technologies", []),
                "links": [{"text": link["label"], "url": link["url"]} for link in project.get("links", [])],
                "date": project.get("date", ""),
                "featured": "featured" in project.get("tags", []),
            }
            for project in data["projects"]
        ],
        "skills": [
            {
                "category": skill["category"],
                "icon": "•",
                "colorClass": "ionq-teal",
                "items": [{"name": value, "percent": 85} for value in skill["items"]],
            }
            for skill in data["skills"]
        ],
        "achievements": [
            {
                "title": honor["title"],
                "icon": "★",
                "description": honor.get("description", honor["title"]),
                "year": honor["date"],
                "colorClass": "matrix-green",
            }
            for honor in data["honors"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", action="append")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--public", action="store_true")
    args = parser.parse_args()
    data = load_yaml(DATA)
    OUT.mkdir(exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    names = args.client or (["resume-quantum", "resume-backend", "resume-aiml", "cv"] if args.all or not args.public else [])

    for name in names:
        client = load_yaml(CLIENTS / f"{name}.yaml")
        document = render_cv(data, client) if name == "cv" else render_resume(data, client)
        digest = fingerprint({"template": TEMPLATE_VERSION, "client": client, "data": data})
        tex = OUT / f"{name}.tex"
        pdf = OUT / f"{name}.pdf"
        entry = manifest.get(name, {})
        if entry.get("fingerprint") != digest or not tex.exists():
            tex.write_text(document)
        if shutil.which("latexmk") and (entry.get("fingerprint") != digest or not pdf.exists()):
            subprocess.run(
                ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={OUT}", str(tex)],
                check=True,
            )
        manifest[name] = {"fingerprint": digest, "tex": tex.name, "pdf": pdf.name if pdf.exists() else None}

    if args.public or args.all or not args.client:
        projection = public_projection(data)
        (OUT / "public-profile.json").write_text(json.dumps(projection, indent=2) + "\n")
        manifest["public-profile"] = {"fingerprint": fingerprint(projection), "file": "public-profile.json"}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
