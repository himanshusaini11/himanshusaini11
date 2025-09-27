#!/usr/bin/env python3
"""
resume_to_json_autohead.py
Convert a résumé PDF to structured JSON with auto-detected headings.

Usage:
  python resume_pdf2json.py input.pdf output.json

Deps:
  pip install pdfminer.six
"""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

# ---------- PDF text extraction ----------
def extract_text_from_pdf(pdf_path: str) -> str:
    from pdfminer.high_level import extract_text
    text = extract_text(pdf_path) or ""
    # Normalize newlines and collapse large gaps
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# ---------- Helpers ----------
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-\.]?)?(?:\(?\d{3}\)?|\d{3})[\s\-\.]?\d{3}[\s\-\.]?\d{4}"
)
URL_RE = re.compile(r"\bhttps?://[^\s)]+|\bwww\.[^\s)]+", re.IGNORECASE)

ORG_TOKENS = {"INC", "LLC", "LTD", "CORP", "UNIVERSITY", "INSTITUTE", "COLLEGE", "SCHOOL", "LAB"}

def classify_urls(urls, name: str | None = None):
    """Classify URLs into LinkedIn, GitHub, Google Scholar, Portfolio, and Others.
    Returns a dict with keys: linkedin, github, google_scholar, portfolio (list), other (list).
    """
    out = {
        "linkedin": None,
        "github": None,
        "google_scholar": None,
        "portfolio": [],
        "other": [],
    }

    # Tokens from name to detect personal domains
    name_tokens = []
    if name:
        name_tokens = [t.lower() for t in re.split(r"[^a-zA-Z]+", name) if len(t) >= 3]

    portfolio_domains = {
        "github.io", "notion.site", "wixsite.com", "squarespace.com",
        "about.me", "carrd.co", "read.cv", "site.google.com", "wordpress.com",
        "medium.com", "weebly.com", "webflow.io", "substack.com", "hashnode.dev",
        "netlify.app", "vercel.app"
    }

    def is_personal_domain(netloc: str) -> bool:
        host = netloc.lower()
        return any(tok in host for tok in name_tokens) if name_tokens else False

    for u in urls:
        try:
            parsed = urlparse(u if u.lower().startswith(("http://", "https://")) else f"https://{u}")
        except Exception:
            out["other"].append(u)
            continue

        netloc = parsed.netloc.lower()
        path = parsed.path.lower()
        full = parsed.geturl()

        if "linkedin.com" in netloc:
            if out["linkedin"] is None:
                out["linkedin"] = full
            else:
                out["other"].append(full)
            continue

        if netloc == "github.com" or netloc.endswith(".github.com"):
            # prefer profile URLs like github.com/username
            if out["github"] is None:
                out["github"] = full
            else:
                out["other"].append(full)
            continue

        if "scholar.google" in netloc:
            if out["google_scholar"] is None:
                out["google_scholar"] = full
            else:
                out["other"].append(full)
            continue

        # portfolio candidates
        domain_matches_portfolio = any(netloc.endswith(d) for d in portfolio_domains)
        personal_domain = is_personal_domain(netloc)
        if domain_matches_portfolio or personal_domain:
            out["portfolio"].append(full)
        else:
            out["other"].append(full)

    # de-duplicate lists
    out["portfolio"] = sorted(set(out["portfolio"]))
    out["other"] = sorted(set(out["other"]))
    return out

def is_upper_like(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return False
    return sum(c.isupper() for c in letters) / len(letters) > 0.9

def looks_like_name(s: str) -> bool:
    # Short, 2–5 tokens, mostly caps, no org tokens, no '@'
    toks = s.split()
    if not (2 <= len(toks) <= 5):
        return False
    if any(t.strip(",.&").upper() in ORG_TOKENS for t in toks):
        return False
    if "@" in s:
        return False
    return is_upper_like(s)

def detect_headings(lines):
    """
    Returns:
      sections: dict[heading -> text]
      name: str|None
      headerless_prefix: text before first heading (sans name line)
    """
    sections = {}
    current_header = "headerless"
    buf = []
    name = None
    started = False

    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            buf.append("")  # keep blank to help paragraph splits later
            continue

        # Capture name if first non-empty line looks like a name
        if name is None and looks_like_name(line):
            name = line
            continue  # do not treat as content or heading

        # Heading heuristic
        token_count = len(line.split())
        heading_like = (
            (is_upper_like(line) and token_count <= 6)
            or line.endswith(":")
        )

        # Strengthen heuristic with context: blank line before or after => more likely a heading
        prev_blank = (i > 0 and not lines[i-1].strip())
        next_blank = (i + 1 < len(lines) and not lines[i+1].strip())
        contextual_boost = prev_blank or next_blank

        is_heading = heading_like and contextual_boost

        if is_heading:
            # flush previous buffer
            if buf:
                sections[current_header] = "\n".join(buf).strip()
                buf = []
            current_header = line.rstrip(":")
            started = True
        else:
            buf.append(line)

    if buf:
        sections[current_header] = "\n".join(buf).strip()

    # Remove empty sections
    sections = {k: v for k, v in sections.items() if v}

    # Split headerless into early headerless prefix and keep rest as-is
    headerless_prefix = sections.pop("headerless", "")
    return sections, name, headerless_prefix

def bulletize(block: str):
    if not block:
        return []
    out = []
    for ln in block.splitlines():
        s = ln.strip("•·*-–\t ").strip()
        if s:
            out.append(s)
    return out

def extract_contacts(text: str):
    emails = sorted(set(EMAIL_RE.findall(text)))
    # PHONE_RE may return strings; normalize
    phones = []
    for m in PHONE_RE.finditer(text):
        s = m.group(0)
        s = re.sub(r"\s+", " ", s).strip()
        phones.append(s)
    phones = sorted(set(phones))
    urls = sorted(set(URL_RE.findall(text)))
    return emails, phones, urls

# Optional parsers for common sections (will run only if present)
def parse_skills(block: str):
    toks = re.split(r"[,\n;|/]+", block or "")
    return [t.strip() for t in toks if t.strip()]

def parse_education(block: str):
    if not block:
        return []
    chunks = [c.strip() for c in re.split(r"\n\s*\n", block) if c.strip()]
    recs = []
    for ch in chunks:
        mdeg = re.search(r"(Ph\.?D\.?|M\.?Sc\.?|M\.?Eng\.?|M\.?Tech\.?|M\.?S\.?|B\.?Sc\.?|B\.?Eng\.?|B\.?Tech\.?|Bachelor|Master|Doctor)\b[^,\n]*", ch, re.IGNORECASE)
        minst = re.search(r"(University|Institute|College|Polytechnic|School)\b[^\n,]*", ch, re.IGNORECASE)
        mdate = re.search(r"\b(19|20)\d{2}\b(?:\s*[-–]\s*\b(19|20)\d{2}\b|(?:\s*[-–]\s*Present))?", ch, re.IGNORECASE)
        recs.append({
            "degree": mdeg.group(0) if mdeg else None,
            "institution": minst.group(0) if minst else None,
            "dates": mdate.group(0) if mdate else None,
            "raw": ch
        })
    return recs

def parse_experience(block: str):
    if not block:
        return []
    chunks = [c.strip() for c in re.split(r"\n\s*\n", block) if c.strip()]
    recs = []
    DATE_RE = r"((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\b(19|20)\d{2}\b)\s*[-–]\s*(Present|((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\b(19|20)\d{2}\b))"
    for ch in chunks:
        lines = [l for l in ch.splitlines() if l.strip()]
        header = lines[0] if lines else ""
        role = company = None
        parts = re.split(r"[—\-–|•]\s*", header, maxsplit=1)
        if len(parts) == 2:
            left, right = parts[0].strip(), parts[1].strip()
            # crude guess
            if any(k in right.lower() for k in ["inc", "corp", "llc", "ltd", "university", "lab"]):
                role, company = left, right
            else:
                company, role = left, right
        mdate = re.search(DATE_RE, ch, re.IGNORECASE)
        recs.append({
            "role": role,
            "company": company,
            "dates": mdate.group(0) if mdate else None,
            "highlights": bulletize("\n".join(lines[1:])),
            "raw": ch
        })
    return recs

# ---------- Build JSON ----------
def build_json(text: str):
    lines = [l for l in text.splitlines()]
    # normalize consecutive blanks to single blank to help heading context
    norm_lines = []
    for i, l in enumerate(lines):
        if l.strip() == "" and (len(norm_lines) > 0 and norm_lines[-1].strip() == ""):
            continue
        norm_lines.append(l)

    sections, name, headerless = detect_headings(norm_lines)

    emails, phones, urls = extract_contacts(text)
    url_bins = classify_urls(urls, name)

    # Try to map common sections if present (case-insensitive match)
    def get_case_insensitive(key):
        for k in sections.keys():
            if k.strip().lower() == key:
                return sections[k]
        return None

    exp_block = get_case_insensitive("experience") or get_case_insensitive("work experience") or get_case_insensitive("professional experience")
    edu_block = get_case_insensitive("education")
    skills_block = get_case_insensitive("skills") or get_case_insensitive("technical skills")

    data = {
        "name": name,
        "contact": {
            "emails": emails,
            "phones": phones,
            "linkedin": url_bins.get("linkedin"),
            "github": url_bins.get("github"),
            "google_scholar": url_bins.get("google_scholar"),
            "portfolio": url_bins.get("portfolio", []),
        },
        "other_urls": url_bins.get("other", []),
        "headerless_intro": headerless or None,
        "sections_raw": sections,  # all detected headings as-is
        "parsed": {
            "summary": get_case_insensitive("summary") or get_case_insensitive("profile") or get_case_insensitive("objective"),
            "skills": parse_skills(skills_block) if skills_block else [],
            "education": parse_education(edu_block) if edu_block else [],
            "experience": parse_experience(exp_block) if exp_block else [],
        }
    }
    return data

# ---------- JSON -> Markdown ----------

def json_to_markdown(data: dict) -> str:
    """Render a verbatim-style Markdown that mirrors the PDF order with minimal transformation.
    Rules:
      - H1 for name if present
      - Emit headerless_intro exactly as captured
      - For each detected section (in original order), print `## {SECTION}` then its block text as-is
      - No synthesized contact lines, no regrouping, no bullet rewrites
      - Drop standalone page-number lines (e.g., "2") when rendering
    """
    def normalize_section_text(block: str) -> str:
        # Collapse single newlines to spaces, keep double newlines as paragraph breaks
        if not block:
            return ""
        block = re.sub(r"[ \t]+", " ", block)
        # Replace single \n (not part of a \n\n) with a space
        block = re.sub(r"(?<!\n)\n(?!\n)", " ", block)
        # Collapse 3+ newlines to exactly two
        block = re.sub(r"\n{3,}", "\n\n", block)
        return block.strip()

    def strip_page_numbers(block: str) -> str:
        lines = block.splitlines()
        out = []
        for i, ln in enumerate(lines):
            if re.fullmatch(r"\s*\d{1,3}\s*", ln):
                # Skip lone numeric lines that are likely page numbers
                # If neighbors are blank or boundaries, treat as page number
                prev_blank = (i == 0) or (not lines[i-1].strip())
                next_blank = (i == len(lines)-1) or (not lines[i+1].strip())
                if prev_blank or next_blank:
                    continue
            out.append(ln)
        return "\n".join(out)

    parts = []

    name = data.get("name") or ""
    if name:
        parts.append(f"# {name}")

    headerless_intro = data.get("headerless_intro") or ""
    if headerless_intro:
        parts.append(normalize_section_text(strip_page_numbers(headerless_intro)))

    # Use sections_raw in original insertion order (dict preserves it)
    sections_raw = data.get("sections_raw") or {}
    for sec_name, sec_text in sections_raw.items():
        if not sec_text:
            continue
        parts.append(f"## {sec_name}")
        parts.append(normalize_section_text(strip_page_numbers(sec_text)))

    md = "\n\n".join([p for p in parts if p is not None and p != ""]).strip() + "\n"
    # Collapse excessive blank lines
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path", type=str)
    ap.add_argument("output_json", type=str)
    args = ap.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        raise SystemExit(f"File not found: {pdf_path}")

    text = extract_text_from_pdf(str(pdf_path))
    data = build_json(text)

    out = Path(args.output_json)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also emit a Markdown rendering for side-by-side comparison
    md_path = out.with_suffix(".md")
    md_str = json_to_markdown(data)
    md_path.write_text(md_str, encoding="utf-8")

    print(f"Wrote {out.resolve()}")
    print(f"Wrote {md_path.resolve()}")

if __name__ == "__main__":
    main()