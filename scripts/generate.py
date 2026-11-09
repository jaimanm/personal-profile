#!/usr/bin/env python3
"""Generate deterministic public data and PDF source files from career.yaml."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "career.yaml"
CLIENTS = ROOT / "clients"
OUT = ROOT / "generated"
MANIFEST = OUT / "manifest.json"
TEMPLATE_VERSION = "2"

PREAMBLE = r"""
\documentclass[letterpaper,10pt]{article}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage[normalem]{ulem}
\input{glyphtounicode}
\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}\renewcommand{\footrulewidth}{0pt}
\addtolength{\oddsidemargin}{-0.5in}\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}\addtolength{\topmargin}{-.75in}\addtolength{\textheight}{1.5in}
\urlstyle{same}\raggedbottom\raggedright\setlength{\tabcolsep}{0in}\pdfgentounicode=1
\titleformat{\section}{\vspace{-4pt}\scshape\raggedright\large}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]
\newcommand{\resumeItem}[1]{\item\small{{#1\vspace{-2pt}}}}
\newcommand{\resumeSubheading}[4]{\vspace{-2pt}\item\begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}\textbf{#1} & #2 \\\textit{\small#3} & \textit{\small #4}\end{tabular*}\vspace{-7pt}}
\newcommand{\resumeProjectHeading}[2]{\vspace{-2pt}\item\begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}\small#1 & #2\end{tabular*}\vspace{-7pt}}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
"""


def load_yaml(path: Path) -> dict:
    with path.open() as handle:
        return yaml.safe_load(handle) or {}


def escape(value: object) -> str:
    text = str(value)
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
    return "".join(replacements.get(char, char) for char in text)


def url_text(url: str) -> str:
    return rf"\href{{{url}}}{{\uline{{{escape(url.removeprefix('https://'))}}}}}"


def selected(records: list[dict], ids: list[str]) -> list[dict]:
    by_id = {record["id"]: record for record in records}
    return [by_id[item] for item in ids if item in by_id]


def bullet_text(bullet: dict, key: str) -> str:
    return bullet.get("variants", {}).get(key, bullet["default"])


def fingerprint(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def heading(data: dict) -> str:
    profile = data["profile"]
    return (
        rf"\begin{{center}}\textbf{{\Huge \scshape {escape(profile['name'])}}} \\ \vspace{{1pt}}"
        rf"\small \href{{mailto:{profile['email']}}}{{\uline{{{escape(profile['email'])}}}}} $|$ "
        rf"{url_text(profile['linkedin'])} $|$ {url_text(profile['website'])}\end{{center}}"
    )


def render_list(items: list[str]) -> str:
    return "\\resumeItemListStart\n" + "\n".join(
        rf"\resumeItem{{{escape(item)}}}" for item in items
    ) + "\n\\resumeItemListEnd"


def render_resume(data: dict, client: dict) -> str:
    include = client["include"]
    key = client.get("variant_key", "default")
    education = data["education"][0]
    lines = [PREAMBLE, r"\begin{document}", heading(data), r"\section{Education}", r"\resumeSubHeadingListStart"]
    lines.append(
        rf"\resumeSubheading{{{escape(education['institution'])}}}{{{escape(education['location'])}}}"
        rf"{{{escape(education['degree'])} $|$ GPA: {escape(education['gpa'])}}}{{Graduation: {escape(education['graduation'])}}}"
    )
    lines.append(render_list([
        "Minors: " + ", ".join(education["minors"]),
        "Relevant Coursework: " + ", ".join(education["coursework"]),
    ]))
    lines += [r"\resumeSubHeadingListEnd", r"\section{Experience}", r"\resumeSubHeadingListStart"]
    for role in selected(data["experience"], include["experience"]):
        bullets = [bullet_text(item, key) for item in role["bullets"]]
        lines.append(rf"\resumeProjectHeading{{\textbf{{{escape(role['organization'])}}} $|$ \emph{{{escape(role['role'])}}}}}{{{escape(role['start'])} -- {escape(role['end'])}}}")
        lines.append(render_list(bullets))
    lines += [r"\resumeSubHeadingListEnd", r"\section{Projects}", r"\resumeSubHeadingListStart"]
    for project in selected(data["projects"], include["projects"]):
        title = project["title"]
        if project.get("links"):
            title = rf"\href{{{project['links'][0]['url']}}}{{\uline{{{escape(title)}}}}}"
        lines.append(rf"\resumeProjectHeading{{\textbf{{{title}}} $|$ \emph{{{escape(', '.join(project['technologies']))}}}}}{{{escape(project['date'])}}}")
        lines.append(render_list([bullet_text(item, key) for item in project.get("bullets", [])]))
    lines += [r"\resumeSubHeadingListEnd", r"\section{Technical Skills}", r"\begin{itemize}[leftmargin=0.15in, label={}]", r"\small{\item{"]
    for skill in data["skills"]:
        if skill["category"] in client.get("skill_categories", []):
            lines.append(rf"\textbf{{{escape(skill['category'])}}}: {escape(', '.join(skill['items']))} \\")
    lines += [r"}}", r"\end{itemize}", r"\end{document}"]
    return "\n".join(lines)


def render_cv(data: dict, client: dict) -> str:
    include = client["include"]
    key = client.get("variant_key", "default")
    education = data["education"][0]
    lines = [PREAMBLE.replace("10pt", "11pt"), r"\begin{document}", heading(data)]
    objective = data["profile"]["description"] + " Pursuing the next generation of systems bridging quantum software and machine learning."
    lines += [r"\section{Objective}", rf"\small{{{escape(objective)}}}", r"\section{Education}", r"\resumeSubHeadingListStart"]
    lines.append(rf"\resumeSubheading{{{escape(education['institution'])}}}{{{escape(education['location'])}}}{{{escape(education['degree'])} $|$ GPA: {escape(education['gpa'])}}}{{Graduation: {escape(education['graduation'])}}}")
    lines.append(render_list(["Minors: " + ", ".join(education["minors"]), "Relevant Coursework: " + ", ".join(education["coursework"])]))
    lines += [r"\resumeSubHeadingListEnd", r"\section{Experience}", r"\resumeSubHeadingListStart"]
    for role in selected(data["experience"], include["experience"]):
        lines.append(rf"\resumeProjectHeading{{\textbf{{{escape(role['organization'])}}} $|$ \emph{{{escape(role['role'])}}}}}{{{escape(role['start'])} -- {escape(role['end'])}}}")
        lines.append(render_list([bullet_text(item, key) for item in role["bullets"]]))
    lines += [r"\resumeSubHeadingListEnd", r"\section{Publications}", r"\resumeSubHeadingListStart"]
    for paper in data["publications"]:
        lines.append(rf"\resumeProjectHeading{{\textbf{{\href{{{paper['url']}}}{{\uline{{{escape(paper['title'])}}}}}}} $|$ \emph{{{escape(paper['role'])}}}}}{{{escape(paper['date'])}}}")
    lines += [r"\resumeSubHeadingListEnd", r"\section{Technical Projects}", r"\resumeSubHeadingListStart"]
    for project in selected(data["projects"], include["projects"]):
        lines.append(rf"\resumeProjectHeading{{\textbf{{{escape(project['title'])}}} $|$ \emph{{{escape(', '.join(project['technologies']))}}}}}{{{escape(project['date'])}}}")
        lines.append(render_list([bullet_text(item, key) for item in project.get("bullets", [])]))
    lines += [r"\resumeSubHeadingListEnd", r"\section{Technical Skills}", r"\begin{itemize}[leftmargin=0.15in, label={}]", r"\small{\item{"]
    for skill in data["skills"]:
        if skill["category"] in client.get("skill_categories", []):
            lines.append(rf"\textbf{{{escape(skill['category'])}}}: {escape(', '.join(skill['items']))} \\")
    lines += [r"}}", r"\end{itemize}", r"\section{Honors \& Awards}", r"\resumeSubHeadingListStart"]
    for honor in data["honors"]:
        lines.append(rf"\resumeProjectHeading{{\textbf{{{escape(honor['title'])}}} $|$ \emph{{{escape(honor.get('organization', ''))}}}}}{{{escape(honor['date'])}}}")
    lines += [r"\resumeSubHeadingListEnd", r"\section{Extracurricular Activities}", r"\resumeSubHeadingListStart"]
    for item in data["extracurricular"]:
        lines.append(rf"\resumeProjectHeading{{\textbf{{{escape(item['organization'])}}} $|$ \emph{{{escape(item['role'])}}}}}{{{escape(item['start'])} -- {escape(item['end'])}}}")
    lines += [r"\resumeSubHeadingListEnd", r"\end{document}"]
    return "\n".join(lines)


def public_projection(data: dict) -> dict:
    profile = data["profile"]
    projects = []
    for project in data["projects"]:
        projects.append({
            "id": project["id"], "title": project["title"], "category": " ".join(project.get("tags", [])),
            "tags": project.get("tags", []), "description": project["description"],
            "tech": project.get("technologies", []), "links": [{"text": link["label"], "url": link["url"]} for link in project.get("links", [])],
            "date": project.get("date", ""), "featured": "featured" in project.get("tags", []),
        })
    skills = [{"category": item["category"], "icon": "•", "colorClass": "ionq-teal", "items": [{"name": value, "percent": 85} for value in item["items"]]} for item in data["skills"]]
    achievements = [{"title": item["title"], "icon": "★", "description": item.get("description", item["title"]), "year": item["date"], "colorClass": "matrix-green"} for item in data["honors"]]
    return {
        "personal": {**profile, "profileImage": profile.get("profile_image")},
        "hero": {"typedLines": profile.get("typed_lines", [])},
        "projects": projects,
        "skills": skills,
        "achievements": achievements,
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
            subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={OUT}", str(tex)], check=True)
        manifest[name] = {"fingerprint": digest, "tex": tex.name, "pdf": pdf.name if pdf.exists() else None}
    if args.public or args.all or not args.client:
        projection = public_projection(data)
        (OUT / "public-profile.json").write_text(json.dumps(projection, indent=2) + "\n")
        manifest["public-profile"] = {"fingerprint": fingerprint(projection), "file": "public-profile.json"}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
