from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = ROOT / "markdown"


def slugify(title: str) -> str:
    slug = title.strip()
    slug = slug.replace("/", "_")
    slug = slug.replace(" ", "_")
    slug = re.sub(r"[^\w가-힣\-_.]+", "", slug)
    slug = re.sub(r"_+", "_", slug)
    return slug.strip("_.")


def clean_page_text(text: str) -> str:
    text = text.replace("\f", "")
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    text = "\n".join(lines).strip()
    return text.replace("```", "'''")


BOOKS = [
    {
        "key": "book1",
        "title": "제1권",
        "pdf_path": Path("/Users/uma/Downloads/[600dpi] 제1권_ocr.pdf"),
        "chapters": [
            {"order": "00", "title": "워밍업! 핵심정리노트", "start": 10, "end": 15},
            {"order": "01", "title": "세제관련법규/세무전략", "start": 16, "end": 61},
            {"order": "02", "title": "금융상품", "start": 62, "end": 173},
            {"order": "03", "title": "부동산관련상품", "start": 174, "end": 233},
            {"order": "04", "title": "대안투자운용/투자전략", "start": 234, "end": 277},
            {"order": "05", "title": "해외 증권투자운용/투자전략", "start": 278, "end": 305},
            {"order": "06", "title": "투자분석기법", "start": 306, "end": 403},
            {"order": "07", "title": "리스크 관리", "start": 404, "end": 534},
        ],
    },
    {
        "key": "book2",
        "title": "제2권",
        "pdf_path": Path("/Users/uma/Downloads/[600dpi] 제2권_ocr.pdf"),
        "chapters": [
            {"order": "01", "title": "직무윤리", "start": 12, "end": 71},
            {
                "order": "02",
                "title": "자본시장과 금융투자업에 관한 법률 및 금융위원회규정",
                "start": 72,
                "end": 179,
            },
            {"order": "03", "title": "한국금융투자협회규정", "start": 180, "end": 223},
            {"order": "04", "title": "주식투자운용/투자전략", "start": 224, "end": 271},
            {"order": "05", "title": "채권투자운용/투자전략", "start": 272, "end": 329},
            {"order": "06", "title": "파생상품 투자운용/투자전략", "start": 330, "end": 389},
            {"order": "07", "title": "투자운용결과분석", "start": 390, "end": 421},
            {"order": "08", "title": "거시경제", "start": 422, "end": 453},
            {"order": "09", "title": "분산투자기법", "start": 454, "end": 494},
            {"order": "10", "title": "최종모의고사 제1회", "start": 495, "end": 521},
            {"order": "11", "title": "최종모의고사 제2회", "start": 522, "end": 548},
            {"order": "12", "title": "정답 및 해설", "start": 549, "end": 570},
        ],
    },
]


def render_book_readme(book: dict) -> str:
    lines = [
        f"# {book['title']}",
        "",
        f"- 원본 PDF: `{book['pdf_path']}`",
        f"- 총 챕터 수: {len(book['chapters'])}",
        "",
        "## 목차",
        "",
    ]
    for chapter in book["chapters"]:
        filename = f"{chapter['order']}_{slugify(chapter['title'])}.md"
        lines.append(
            f"- `{chapter['order']}` [{chapter['title']}](./{filename}) "
            f"(PDF 페이지 {chapter['start']}~{chapter['end']})"
        )
    lines.append("")
    return "\n".join(lines)


def render_chapter_markdown(book: dict, chapter: dict, pages: list[str]) -> str:
    lines = [
        f"# {book['title']} - {chapter['title']}",
        "",
        f"- 원본 PDF: `{book['pdf_path']}`",
        f"- PDF 페이지 범위: `{chapter['start']}~{chapter['end']}`",
        "",
    ]

    for page_number, text in zip(range(chapter["start"], chapter["end"] + 1), pages):
        lines.extend(
            [
                f"## PDF 페이지 {page_number}",
                "",
                "```text",
                clean_page_text(text),
                "```",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUTPUT_ROOT.mkdir(exist_ok=True)

    top_readme_lines = ["# PDF Chapter Exports", ""]

    for book in BOOKS:
        reader = PdfReader(str(book["pdf_path"]))
        total_pages = len(reader.pages)
        book_dir = OUTPUT_ROOT / book["key"]
        book_dir.mkdir(parents=True, exist_ok=True)

        for chapter in book["chapters"]:
            if not (1 <= chapter["start"] <= chapter["end"] <= total_pages):
                raise ValueError(
                    f"Invalid page range for {book['title']} / {chapter['title']}: "
                    f"{chapter['start']}~{chapter['end']} (total {total_pages})"
                )

            chapter_pages = [
                reader.pages[index - 1].extract_text() or ""
                for index in range(chapter["start"], chapter["end"] + 1)
            ]
            filename = f"{chapter['order']}_{slugify(chapter['title'])}.md"
            output_path = book_dir / filename
            output_path.write_text(
                render_chapter_markdown(book, chapter, chapter_pages),
                encoding="utf-8",
            )

        (book_dir / "README.md").write_text(render_book_readme(book), encoding="utf-8")
        top_readme_lines.append(f"- [{book['title']}](./{book['key']}/README.md)")

    top_readme_lines.append("")
    (OUTPUT_ROOT / "README.md").write_text("\n".join(top_readme_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
