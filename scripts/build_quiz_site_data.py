from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ModuleNotFoundError:
    PdfReader = None


ROOT = Path(__file__).resolve().parent.parent
BASE_SOURCE_FILE = ROOT / "markdown" / "투자자산운용사_예상문제_100선.md"
GENERATED_BANK_FILE = ROOT / "markdown" / "투자자산운용사_확장_문제은행.md"
OUTPUT_FILE = ROOT / "docs" / "data" / "questions.json"
MOCK_EXAM_1_FILE = ROOT / "markdown" / "book2" / "10_최종모의고사_제1회.md"
MOCK_EXAM_2_FILE = ROOT / "markdown" / "book2" / "11_최종모의고사_제2회.md"
MOCK_ANSWER_FILE = ROOT / "markdown" / "book2" / "12_정답_및_해설.md"
CALC_NOTE_PDF = ROOT / "[600dpi] 계산문제 특강노트_ocr.pdf"
BOOK1_PDF = ROOT / "[600dpi] 제1권_ocr.pdf"
BOOK2_PDF = ROOT / "[600dpi] 제2권_ocr.pdf"
QUESTION_IMAGE_DIR = ROOT / "docs" / "assets" / "question-pages"
RENDER_PDF_SCRIPT = ROOT / "scripts" / "render_pdf_page.swift"
INLINE_SKIP_SOURCES = {
    "book1/01_세제관련법규_세무전략.md",
    "book1/02_금융상품.md",
}
FIGURE_PROMPT_PATTERN = re.compile(r"그림|도표")


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_display_text(text: str) -> str:
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"[★☆◦•▪◆◇□■△▽▶◀※]", " ", text)
    text = re.sub(r"\b[FDQGC]+\b", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:;,")


def clean_question_prompt(text: str) -> str:
    cleaned = clean_display_text(text)
    cleaned = re.sub(r"\s*[#eEoO]{2,}$", "", cleaned)
    cleaned = re.sub(r"\s*[.…]+$", "", cleaned)
    return cleaned.strip()


def lookup_text(text: str) -> str:
    text = clean_display_text(text)
    return re.sub(r"\s+", "", text).lower()


def shorten_text(text: str, limit: int) -> str:
    text = normalize_spaces(clean_display_text(text))
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].strip()
    return f"{cut}..."


def parse_questions(question_text: str) -> list[dict]:
    lines = question_text.splitlines()
    course = ""
    chapter = ""
    questions: list[dict] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("## "):
            course = line[3:].strip()
            i += 1
            continue

        if line.startswith("### "):
            chapter = line[4:].strip()
            i += 1
            continue

        match = re.match(r"^(\d+)\. (.+)$", line)
        if not match:
            i += 1
            continue

        number = int(match.group(1))
        prompt_parts = [match.group(2).strip()]
        i += 1

        while i < len(lines):
            current = lines[i]
            if re.match(r"^\s+1\. ", current):
                break
            if not current.strip():
                i += 1
                continue
            if current.startswith("## ") or current.startswith("### "):
                raise ValueError(f"Question {number} has no options.")
            prompt_parts.append(current.strip())
            i += 1

        options: list[str] = []
        for expected in range(1, 5):
            if i >= len(lines):
                raise ValueError(f"Question {number} ended before option {expected}.")

            option_match = re.match(r"^\s+([1-4])\. (.+)$", lines[i])
            if not option_match:
                raise ValueError(
                    f"Question {number} expected option {expected}, got: {lines[i]!r}"
                )

            option_number = int(option_match.group(1))
            if option_number != expected:
                raise ValueError(
                    f"Question {number} option order mismatch: expected {expected}, got {option_number}"
                )

            option_parts = [option_match.group(2).strip()]
            i += 1

            while i < len(lines):
                current = lines[i]
                if re.match(r"^\s+[1-4]\. ", current) or not current.strip():
                    break
                option_parts.append(current.strip())
                i += 1

            while i < len(lines) and not lines[i].strip():
                i += 1

            options.append(normalize_spaces(" ".join(option_parts)))

        questions.append(
            {
                "id": number,
                "course": course,
                "chapter": chapter,
                "prompt": normalize_spaces(" ".join(prompt_parts)),
                "options": options,
            }
        )

    return questions


def parse_explanations(explanation_text: str) -> dict[int, dict]:
    lines = explanation_text.splitlines()
    explanations: dict[int, dict] = {}
    i = 0

    while i < len(lines):
        line = lines[i]
        match = re.match(r"^(\d+)\. 정답: ([1-4])\s*$", line.strip())
        if not match:
            i += 1
            continue

        number = int(match.group(1))
        answer = int(match.group(2))
        i += 1

        block_lines: list[str] = []
        while i < len(lines):
            current = lines[i]
            if (
                re.match(r"^\d+\. 정답: [1-4]\s*$", current.strip())
                or current.startswith("### ")
                or current.startswith("## ")
            ):
                break
            if current.strip():
                block_lines.append(current.strip())
            i += 1

        block = normalize_spaces(" ".join(block_lines))
        if block.startswith("풀이: "):
            block = block[4:].strip()

        source = ""
        source_match = re.search(r"근거:\s*`([^`]+)`", block)
        if source_match:
            source = source_match.group(1).strip()
            block = normalize_spaces(block[: source_match.start()].strip())

        explanations[number] = {
            "answer": answer,
            "explanation": block,
            "source": source,
        }

    return explanations


def clean_topic_title(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^[0-9]{1,2}\s*", "", text)
    text = re.sub(r"\s*P\.\s*[0-9\-]+$", "", text)
    text = re.sub(r"[★☆◦•=＿_]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return clean_display_text(text.strip(" |-"))


def compact_summary(lines: list[str], limit: int = 260) -> str:
    text = normalize_spaces(" ".join(lines))
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].strip()
    return f"{cut}..."


def chapter_display_title(markdown_text: str, fallback_source: str) -> str:
    first_line = markdown_text.splitlines()[0].strip() if markdown_text.splitlines() else ""
    if first_line.startswith("# "):
        return first_line[2:].strip()
    return fallback_source.replace(".md", "")


def extract_overview(lines: list[str], topic_titles: list[str], chapter_name: str) -> str:
    if topic_titles:
        preview = ", ".join(topic_titles[:4])
        if len(topic_titles) > 4:
            preview += " 등"
        return f"{chapter_name} 챕터는 {preview}을 중심으로 학습해야 합니다. 아래 핵심 개념을 먼저 익힌 뒤 관련 문제를 풀어보세요."
    excerpt_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("## PDF 페이지"):
            continue
        if stripped.startswith("```") or stripped.startswith("- 원본 PDF") or stripped.startswith("- PDF 페이지 범위"):
            continue
        excerpt_lines.append(stripped)
        if len(excerpt_lines) >= 4:
            break
    return compact_summary(excerpt_lines, limit=220)


def extract_topics_from_chapter(markdown_text: str) -> list[dict]:
    lines = markdown_text.splitlines()
    topics: list[dict] = []
    seen_titles: set[str] = set()

    def nearest_page(index: int) -> str:
        for j in range(index, -1, -1):
            match = re.match(r"^## PDF 페이지 (\d+)$", lines[j].strip())
            if match:
                return match.group(1)
        return ""

    def add_topic(title_line: str, start_index: int) -> None:
        title = clean_topic_title(title_line)
        if not title or len(title) < 2:
            return
        if title in seen_titles:
            return

        summary_lines: list[str] = []
        explanation_start = None
        for j in range(start_index, min(start_index + 80, len(lines))):
            stripped = lines[j].strip()
            if "더 알아보기" in stripped:
                explanation_start = j + 1
                break

        if explanation_start is not None:
            for j in range(explanation_start, min(explanation_start + 18, len(lines))):
                stripped = lines[j].strip()
                if not stripped:
                    continue
                if stripped.startswith("## PDF 페이지") or stripped.startswith("보충문제"):
                    break
                if stripped.startswith("```"):
                    continue
                if stripped == "TOPIC":
                    break
                if "핵심문제" in stripped:
                    continue
                summary_lines.append(stripped)
                if len(summary_lines) >= 6:
                    break

        if not summary_lines:
            for j in range(start_index + 1, min(start_index + 10, len(lines))):
                stripped = lines[j].strip()
                if not stripped:
                    continue
                if "핵심문제" in stripped or stripped.startswith("①") or stripped.startswith("```"):
                    continue
                if stripped.startswith("## PDF 페이지") or stripped == "TOPIC":
                    break
                summary_lines.append(stripped)
                if len(summary_lines) >= 3:
                    break

        topics.append(
            {
                "title": title,
                "summary": compact_summary(
                    summary_lines
                    or [f"{title}의 정의, 구조, 핵심 포인트를 중심으로 정리한 챕터입니다."]
                ),
                "page": nearest_page(start_index),
            }
        )
        seen_titles.add(title)

    for i in range(len(lines) - 2):
        current = lines[i].strip()
        next_line = lines[i + 1].strip()
        next_next = lines[i + 2].strip() if i + 2 < len(lines) else ""

        if current == "TOPIC" and "핵심문제" in next_next:
            add_topic(next_line, i + 1)
            continue

        if clean_topic_title(current) and "핵심문제" in next_line:
            candidate = clean_topic_title(current)
            if len(candidate) > 3 and "PDF 페이지" not in candidate and "원본 PDF" not in candidate:
                add_topic(current, i)

    return topics[:20]


def build_lessons(items: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(item["source"], []).append(item)

    lessons: list[dict] = []
    for source, source_questions in grouped.items():
        chapter_file = ROOT / "markdown" / source
        if not chapter_file.exists():
            continue

        markdown_text = chapter_file.read_text(encoding="utf-8")
        display_title = chapter_display_title(markdown_text, source)
        topics = extract_topics_from_chapter(markdown_text)
        topic_titles = [topic["title"] for topic in topics]

        lessons.append(
            {
                "source": source,
                "displayTitle": display_title,
                "course": source_questions[0]["course"],
                "chapter": source_questions[0]["chapter"],
                "overview": extract_overview(
                    markdown_text.splitlines(), topic_titles, source_questions[0]["chapter"]
                ),
                "topics": topics,
                "questionIds": [
                    question["id"] for question in sorted(source_questions, key=lambda x: x["id"])
                ],
                "questionCount": len(source_questions),
            }
        )

    lessons.sort(key=lambda lesson: min(lesson["questionIds"]) if lesson["questionIds"] else 9999)
    return lessons


def markdown_pdf_for_source(source: str) -> Path | None:
    if source.startswith("book1/"):
        return BOOK1_PDF
    if source.startswith("book2/"):
        return BOOK2_PDF
    return None


def locate_source_page(source: str, prompt: str) -> int | None:
    if not source.startswith("book"):
        return None

    markdown_file = ROOT / "markdown" / source
    if not markdown_file.exists():
        return None

    markdown_text = markdown_file.read_text(encoding="utf-8")
    prompt_key = lookup_text(prompt.split("?")[0][:60])
    if not prompt_key:
        return None

    for page_number, block in extract_markdown_pages(markdown_text):
        block_key = lookup_text(block)
        if prompt_key in block_key:
            return page_number

    return None


def ensure_question_page_image(source: str, page_number: int) -> str | None:
    pdf_file = markdown_pdf_for_source(source)
    if pdf_file is None or not pdf_file.exists():
        return None

    book_prefix = "book1" if source.startswith("book1/") else "book2"
    output_file = QUESTION_IMAGE_DIR / f"{book_prefix}-page-{page_number}.png"
    if not output_file.exists():
        if sys.platform != "darwin":
            return None
        subprocess.run(
            [
                "swift",
                str(RENDER_PDF_SCRIPT),
                str(pdf_file),
                str(page_number),
                str(output_file),
                "1.8",
            ],
            check=True,
            cwd=str(ROOT),
        )
    return str(output_file.relative_to(ROOT / "docs"))


STANDARD_OPTION_MAP = {
    "①": 1,
    "②": 2,
    "③": 3,
    "④": 4,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
}

OCR_OPTION_MAP = {
    "©": 3,
    "⊙": 3,
    "㈢": 3,
    "®": 3,
    "@": 4,
    "Q": 4,
    "¥": 4,
}


def clean_ocr_line(text: str) -> str:
    text = clean_display_text(text)
    text = re.sub(r"[•∙·⋅]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_question_number_prefix(line: str) -> str:
    match = re.match(r"^([0-9])\s+([0-9])(\s+.+)$", line.strip())
    if match:
        return f"{match.group(1)}{match.group(2)}{match.group(3)}"
    return line


def extract_option_entries(line: str) -> tuple[str, list[tuple[int, str]]]:
    cleaned = clean_ocr_line(normalize_question_number_prefix(line))
    if not cleaned:
        return "", []

    matches = list(re.finditer(r"[①②③④©⊙㈢®@Q¥]", cleaned))
    if matches:
        prefix = cleaned[: matches[0].start()].strip()
        entries: list[tuple[int, str]] = []
        for index, match in enumerate(matches):
            number = map_answer_token(match.group(0))
            if number is None:
                continue
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
            text = clean_ocr_line(cleaned[start:end])
            if text:
                entries.append((number, text))
        return prefix, entries

    numeric_match = re.match(r"^[-:;\s]*\(?([1-4])\)?[.)]?\s*(.+)$", cleaned)
    if numeric_match:
        return "", [(int(numeric_match.group(1)), clean_ocr_line(numeric_match.group(2)))]

    return cleaned, []


def parse_option_prefix(line: str, expected_next: int | None = None) -> tuple[int | None, str | None]:
    stripped = normalize_question_number_prefix(line).strip()
    if not stripped:
        return None, None

    token = stripped[0]
    if token in STANDARD_OPTION_MAP:
        return STANDARD_OPTION_MAP[token], clean_ocr_line(stripped[1:])
    if token in OCR_OPTION_MAP:
        return OCR_OPTION_MAP[token], clean_ocr_line(stripped[1:])

    match = re.match(r"^\(?([1-4])\)?[.)]?\s*(.+)$", stripped)
    if match:
        return int(match.group(1)), clean_ocr_line(match.group(2))

    if expected_next and token in {"©", "®", "@", "Q", "¥"}:
        return expected_next, clean_ocr_line(stripped[1:])

    return None, None


def parse_answer_prefix(text: str) -> tuple[int | None, str]:
    stripped = normalize_question_number_prefix(text).strip()
    if not stripped:
        return None, ""

    token = stripped[0]
    if token in STANDARD_OPTION_MAP:
        return STANDARD_OPTION_MAP[token], clean_ocr_line(stripped[1:])

    match = re.match(r"^([1-4])\s*(.+)$", stripped)
    if match:
        return int(match.group(1)), clean_ocr_line(match.group(2))

    return None, clean_ocr_line(stripped)


def normalize_question_key(item: dict) -> str:
    key = f"{item['course']}|{item['chapter']}|{item['prompt']}"
    key = re.sub(r"\W+", "", key)
    return key.lower()


def detect_inline_answer(line: str) -> tuple[int | None, str]:
    cleaned = clean_ocr_line(normalize_question_number_prefix(line))
    if not cleaned:
        return None, ""

    match = re.match(
        r"^(?:\d{2}\s+)?(?:[A-Za-z가-힣$#*]+(?:\s+[A-Za-z가-힣$#*]+)*)?\s*([①②③④©⊙㈢®@Q¥]|\(\d\)|[1-4])(?:\s+|$)(.*)$",
        cleaned,
    )
    if not match:
        return None, cleaned

    answer = map_answer_token(match.group(1))
    remainder = clean_ocr_line(match.group(2))
    return answer, remainder


def trim_explanation_text(text: str, limit: int = 420) -> str:
    trimmed = re.split(r"더 알아보기|핵심이론|합격률을 높이는 보충문제", text, maxsplit=1)[0]
    return shorten_text(trimmed, limit)


def is_high_confidence_inline_question(item: dict) -> bool:
    prompt = item["prompt"]
    options = item["options"]
    explanation = item["explanation"]

    if prompt.endswith("O") or prompt.startswith("더 알아보기"):
        return False
    if any(len(option) > 95 for option in options):
        return False
    if any(re.search(r"핵심이론|더 알아보기|PDF 페이지", option) for option in options):
        return False
    if re.search(r"핵심이론|더 알아보기|PDF 페이지", explanation):
        return False
    if not re.search(r"(옳|틀린|적절|것은|무엇|설명|연결|빈칸|해당|거리가 먼)", prompt):
        return False

    return is_quality_question(item)


def infer_answer_from_explanation(options: list[str], explanation: str) -> int | None:
    cleaned = clean_ocr_line(explanation)
    explicit_match = re.match(r"^([①②③④©⊙㈢®@Q¥]|\(\d\)|[1-4])(?:\s|은|는|이|가)", cleaned)
    if explicit_match:
        return map_answer_token(explicit_match.group(1))

    normalized_explanation = re.sub(r"[^0-9A-Za-z가-힣]", "", cleaned)
    scores: list[tuple[int, int]] = []
    for index, option in enumerate(options, start=1):
        normalized_option = re.sub(r"[^0-9A-Za-z가-힣]", "", option)
        if not normalized_option:
            scores.append((index, 0))
            continue
        if normalized_option and normalized_option in normalized_explanation:
            scores.append((index, 100))
            continue
        tokens = [token for token in re.findall(r"[0-9A-Za-z가-힣]+", normalized_option) if len(token) >= 2]
        score = sum(1 for token in tokens if token in normalized_explanation)
        scores.append((index, score))

    best_index, best_score = max(scores, key=lambda item: item[1])
    if best_score < 1:
        return None
    if sum(1 for _, score in scores if score == best_score) > 1:
        return None
    return best_index


def extract_code_blocks(markdown_text: str) -> list[str]:
    return re.findall(r"```text\n(.*?)```", markdown_text, flags=re.S)


def parse_question_block(block: str) -> tuple[str, list[str]] | None:
    prompt_parts: list[str] = []
    options: dict[int, str] = {}
    current_option: int | None = None

    for raw in block.splitlines():
        line = clean_ocr_line(normalize_question_number_prefix(raw))
        if not line:
            continue

        if not prompt_parts and not options:
            line = re.sub(r"^\d{2}(?:-\d+)?\s*", "", line).strip()

        prefix, entries = extract_option_entries(line)
        if entries:
            if prefix:
                if options and current_option is not None:
                    options[current_option] = clean_ocr_line(f"{options[current_option]} {prefix}")
                else:
                    prompt_parts.append(prefix)
            for number, text in entries:
                options[number] = text
                current_option = number
            continue

        if options and len(options) < 4 and current_option is not None:
            options[current_option] = clean_ocr_line(f"{options[current_option]} {line}")
        elif not options:
            prompt_parts.append(line)

    if len(options) < 4:
        return None

    prompt = clean_question_prompt(" ".join(prompt_parts))
    ordered_options = [clean_ocr_line(options.get(index, "")) for index in range(1, 5)]
    if len(prompt) < 8 or any(not option for option in ordered_options):
        return None

    return prompt, ordered_options


def finalize_question(question: dict | None) -> dict | None:
    if not question:
        return None

    prompt = clean_question_prompt(" ".join(question["prompt_parts"]))
    if len(prompt) < 10:
        return None

    options = []
    for number in range(1, 5):
        option = clean_ocr_line(question["options"].get(number, ""))
        if not option:
            return None
        options.append(option)

    return {
        "number": question["number"],
        "prompt": prompt,
        "options": options,
    }


def is_quality_question(item: dict) -> bool:
    prompt = item["prompt"]
    options = item["options"]
    explanation = item["explanation"]

    forbidden_prompt_patterns = [
        r"[①②③④©®@¥]",
        r"제\d+과목",
        r"정답 및 해설",
        r"PDF 페이지",
        r"-{4,}",
        r"\b\d{2}\s+.+\?",
    ]
    forbidden_option_patterns = [
        r"제\d+과목",
        r"정답 및 해설",
        r"PDF 페이지",
        r"부록",
        r"[©®@¥]",
        r"-{4,}",
        r"\b\d{2}\s+[가-힣A-Za-z]",
    ]

    if len(prompt) < 10 or len(prompt) > 220:
        return False
    if len(explanation) < 5:
        return False

    for pattern in forbidden_prompt_patterns:
        if re.search(pattern, prompt):
            return False

    for option in options:
        if len(option) < 2 or len(option) > 160:
            return False
        for pattern in forbidden_option_patterns:
            if re.search(pattern, option):
                return False
        normalized = re.sub(r"[^0-9A-Za-z가-힣%./+-]", "", option)
        if len(normalized) < 3:
            return False

    return True


def extract_chapter_review_questions(source: str, course: str, chapter: str) -> list[dict]:
    chapter_file = ROOT / "markdown" / source
    markdown_text = chapter_file.read_text(encoding="utf-8")
    code_blocks = extract_code_blocks(markdown_text)

    start_index = next((idx for idx, block in enumerate(code_blocks) if "CHAPTER" in block), None)
    if start_index is None:
        return []

    lines: list[str] = []
    for block in code_blocks[start_index:]:
        for raw in block.splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped == "CHAPTER":
                continue
            if stripped.startswith("제") and ("장" in stripped or "과목" in stripped or "부록" in stripped):
                continue
            lines.append(raw.rstrip())

    batches: list[tuple[list[dict], dict[int, dict]]] = []
    mode = "questions"
    questions: list[dict] = []
    answers: dict[int, dict] = {}
    current_question: dict | None = None
    current_option: int | None = None
    current_answer_no: int | None = None

    def flush_question() -> None:
        nonlocal current_question, current_option
        finalized = finalize_question(current_question)
        if finalized:
            questions.append(finalized)
        current_question = None
        current_option = None

    def flush_batch() -> None:
        nonlocal questions, answers, current_answer_no
        flush_question()
        if questions and answers:
            batches.append((questions, answers))
        questions = []
        answers = {}
        current_answer_no = None

    for raw in lines:
        line = normalize_question_number_prefix(raw.strip())
        if line in {"정답 및 해설", "및 해설", "정답"} or line.endswith("해설"):
            flush_question()
            mode = "answers"
            current_answer_no = None
            continue

        if mode == "questions":
            question_match = re.match(r"^(\d{2})\s+(.+)$", line)
            prefix, option_entries = extract_option_entries(line)
            if question_match and not option_entries:
                flush_question()
                current_question = {
                    "number": int(question_match.group(1)),
                    "prompt_parts": [clean_ocr_line(question_match.group(2))],
                    "options": {},
                }
                current_option = None
                continue

            if current_question and option_entries:
                if prefix:
                    if current_question["options"] and current_option is not None:
                        current_question["options"][current_option] = clean_ocr_line(
                            f"{current_question['options'][current_option]} {prefix}"
                        )
                    else:
                        current_question["prompt_parts"].append(prefix)
                for option_no, option_text in option_entries:
                    current_question["options"][option_no] = option_text
                    current_option = option_no
                continue

            if current_question and current_option is not None:
                current_question["options"][current_option] = clean_ocr_line(
                    f"{current_question['options'][current_option]} {line}"
                )
                continue

            if current_question:
                current_question["prompt_parts"].append(clean_ocr_line(line))
            continue

        answer_match = re.match(r"^(\d{2})\s+(.+)$", line)
        if answer_match:
            answer_no = int(answer_match.group(1))
            answer_value, remainder = parse_answer_prefix(answer_match.group(2))
            if answer_value is not None:
                answers[answer_no] = {
                    "answer": answer_value,
                    "explanation_parts": [remainder] if remainder else [],
                }
                current_answer_no = answer_no
                continue

            flush_batch()
            mode = "questions"
            current_question = {
                "number": answer_no,
                "prompt_parts": [clean_ocr_line(answer_match.group(2))],
                "options": {},
            }
            current_option = None
            continue

        if current_answer_no is not None:
            answers[current_answer_no]["explanation_parts"].append(clean_ocr_line(line))

    flush_batch()

    items: list[dict] = []
    for question_batch, answer_batch in batches:
        for question in question_batch:
            answer_info = answer_batch.get(question["number"])
            if not answer_info:
                continue
            explanation = clean_ocr_line(" ".join(answer_info["explanation_parts"]))
            if len(explanation) < 5:
                continue
            candidate = {
                "course": course,
                "chapter": chapter,
                "prompt": question["prompt"],
                "options": question["options"],
                "answer": answer_info["answer"],
                "explanation": explanation,
                "source": source,
            }
            if is_quality_question(candidate):
                items.append(candidate)

    return items


def merge_base_questions() -> list[dict]:
    text = BASE_SOURCE_FILE.read_text(encoding="utf-8")
    question_part, explanation_part = text.split("## 정답 및 풀이", 1)
    questions = parse_questions(question_part)
    explanations = parse_explanations(explanation_part)

    if len(questions) != len(explanations):
        raise ValueError(
            f"Question count and explanation count mismatch: {len(questions)} vs {len(explanations)}"
        )

    items = []
    for question in questions:
        extra = explanations.get(question["id"])
        if extra is None:
            raise ValueError(f"Missing explanation for question {question['id']}")
        items.append({**question, **extra})
    return items


def extract_inline_chapter_questions(
    source: str,
    course: str,
    chapter: str,
    existing_keys: set[str],
    start_id: int,
) -> list[dict]:
    if source in INLINE_SKIP_SOURCES:
        return []

    chapter_file = ROOT / "markdown" / source
    markdown_text = chapter_file.read_text(encoding="utf-8")
    code_blocks = extract_code_blocks(markdown_text)
    chapter_index = next((idx for idx, block in enumerate(code_blocks) if "CHAPTER" in block), len(code_blocks))

    lines: list[str] = []
    for block in code_blocks[:chapter_index]:
        lines.extend(block.splitlines())

    items: list[dict] = []
    next_id = start_id
    in_supplement = False
    pending_number: str | None = None
    current: dict | None = None
    current_option: int | None = None

    def flush_current() -> None:
        nonlocal current, current_option, next_id
        if not current:
            return

        prompt = clean_question_prompt(" ".join(current["prompt_parts"]))
        options = [clean_ocr_line(current["options"].get(index, "")) for index in range(1, 5)]
        explanation = trim_explanation_text(" ".join(current["explanation_parts"]), 420)

        candidate = {
            "course": course,
            "chapter": chapter,
            "prompt": prompt,
            "options": options,
            "answer": current["answer"],
            "explanation": explanation,
            "source": source,
        }
        item_key = normalize_question_key(candidate)

        if (
            current["answer"] is not None
            and all(options)
            and item_key not in existing_keys
            and is_high_confidence_inline_question(candidate)
        ):
            existing_keys.add(item_key)
            items.append({**candidate, "id": next_id})
            next_id += 1

        current = None
        current_option = None

    for raw in lines:
        line = clean_ocr_line(normalize_question_number_prefix(raw))
        if not line:
            continue
        if line in {"TOPIC", "TO 이 C"} or re.match(r"^제\d+과목", line):
            continue
        if re.match(r"^\d+\s+제[0-9가-힣A-Za-z ]+$", line):
            continue

        if line.startswith("보충문제 >") or "합격률을 높이는 보충문제" in line:
            flush_current()
            in_supplement = True
            pending_number = None
            continue

        if "핵심문제" in line:
            flush_current()
            current = {
                "prompt_parts": [clean_ocr_line(line.split("핵심문제", 1)[1])],
                "options": {},
                "answer": None,
                "explanation_parts": [],
            }
            current_option = None
            in_supplement = False
            pending_number = None
            continue

        if in_supplement:
            if re.fullmatch(r"\d{2}", line):
                flush_current()
                pending_number = line
                continue

            supplement_match = re.match(r"^(\d{2})\s+(.+)$", line)
            if supplement_match and (current is None or (len(current["options"]) == 4 and current["answer"] is not None)):
                flush_current()
                current = {
                    "prompt_parts": [clean_ocr_line(supplement_match.group(2))],
                    "options": {},
                    "answer": None,
                    "explanation_parts": [],
                }
                current_option = None
                pending_number = None
                continue

            if pending_number and current is None:
                current = {
                    "prompt_parts": [line],
                    "options": {},
                    "answer": None,
                    "explanation_parts": [],
                }
                current_option = None
                pending_number = None
                continue

        if current is None:
            continue

        prefix, option_entries = extract_option_entries(line)
        if option_entries:
            if prefix:
                if current["options"] and current_option is not None and len(current["options"]) < 4:
                    current["options"][current_option] = clean_ocr_line(
                        f"{current['options'][current_option]} {prefix}"
                    )
                elif not current["options"]:
                    current["prompt_parts"].append(prefix)
                elif current["answer"] is not None:
                    current["explanation_parts"].append(prefix)
            for number, text in option_entries:
                current["options"][number] = text
                current_option = number
            continue

        if len(current["options"]) < 4:
            if current_option is not None and current["options"]:
                current["options"][current_option] = clean_ocr_line(
                    f"{current['options'][current_option]} {line}"
                )
            else:
                current["prompt_parts"].append(line)
            continue

        if current["answer"] is None:
            answer, remainder = detect_inline_answer(line)
            if answer is not None:
                current["answer"] = answer
                if remainder:
                    current["explanation_parts"].append(remainder)
                continue

        if current["answer"] is not None and (
            "더 알아보기" in line or "핵심이론" in line or re.match(r"^제\d+장", line)
        ):
            flush_current()
            continue

        current["explanation_parts"].append(line)

    flush_current()
    return items


def extract_real_question_bank(base_items: list[dict], start_id: int) -> tuple[list[dict], list[dict]]:
    source_map: dict[str, tuple[str, str]] = {}
    for item in base_items:
        source_map.setdefault(item["source"], (item["course"], item["chapter"]))

    existing_keys = {normalize_question_key(item) for item in base_items}
    inline_items: list[dict] = []
    review_items: list[dict] = []
    next_id = start_id

    for source, (course, chapter) in source_map.items():
        chapter_inline = extract_inline_chapter_questions(
            source,
            course,
            chapter,
            existing_keys,
            next_id,
        )
        inline_items.extend(chapter_inline)
        if chapter_inline:
            next_id = max(item["id"] for item in chapter_inline) + 1

        for item in extract_chapter_review_questions(source, course, chapter):
            item_key = normalize_question_key(item)
            if item_key in existing_keys:
                continue
            existing_keys.add(item_key)
            review_items.append({**item, "id": next_id})
            next_id += 1

    return inline_items, review_items


def extract_markdown_pages(markdown_text: str) -> list[tuple[int, str]]:
    pattern = re.compile(r"## PDF 페이지 (\d+)\n\n```text\n(.*?)```", re.S)
    return [(int(page), block) for page, block in pattern.findall(markdown_text)]


def map_answer_token(token: str) -> int | None:
    token = token.strip()
    if token in STANDARD_OPTION_MAP:
        return STANDARD_OPTION_MAP[token]
    if token in OCR_OPTION_MAP:
        return OCR_OPTION_MAP[token]
    match = re.match(r"^\((\d)\)$", token)
    if match:
        return int(match.group(1))
    if token in {"(3", "3)"}:
        return 3
    return None


def split_first_four_options(text: str) -> tuple[str, list[str]] | None:
    markers = []
    search_start = 0
    for symbol in ["①", "②", "③", "④"]:
        match = re.search(re.escape(symbol), text[search_start:])
        if not match:
            return None
        absolute_start = search_start + match.start()
        absolute_end = search_start + match.end()
        markers.append((symbol, absolute_start, absolute_end))
        search_start = absolute_end

    prompt = clean_ocr_line(text[: markers[0][1]])
    prompt = re.sub(r"^\d+(?:-\d+)?\s*", "", prompt).strip()
    if len(prompt) < 8:
        return None

    tail_cut_points = [
        idx
        for idx in [
            text.find("더 알아보기", markers[-1][2]),
            text.find("정답 및 해설", markers[-1][2]),
        ]
        if idx != -1
    ]
    option4_end = min(tail_cut_points) if tail_cut_points else len(text)

    options: list[str] = []
    for index, (_, _, marker_end) in enumerate(markers):
        next_start = markers[index + 1][1] if index + 1 < len(markers) else option4_end
        option_text = clean_ocr_line(text[marker_end:next_start])
        if len(option_text) < 1:
            return None
        options.append(option_text)

    return prompt, options


def is_question_start_line(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^\d{2}\s+.+$", stripped))


def is_page_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped in {"CHAPTER", "정답 및 해설"}:
        return False
    if re.match(r"^제\d+장", stripped):
        return True
    if "부록" in stripped and "최종모의고사" in stripped:
        return True
    if re.match(r"^제\d+회 정답 및 해설", stripped):
        return True
    if stripped.startswith("제") and ("과목" in stripped or "회 최종모의고사" in stripped):
        return True
    return False


def extract_mock_question_blocks(markdown_file: Path) -> list[str]:
    markdown_text = markdown_file.read_text(encoding="utf-8")
    pages = extract_markdown_pages(markdown_text)

    lines: list[str] = []
    started = False
    for _, block in pages:
        for raw in block.splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            if "최종모의고사 100문항" in stripped:
                started = True
                continue
            if not started:
                continue
            if is_page_noise(stripped):
                continue
            lines.append(clean_ocr_line(raw))

    question_blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        if is_question_start_line(line):
            if current:
                question_blocks.append(" ".join(current))
            current = [line]
        else:
            if current:
                current.append(line)
    if current:
        question_blocks.append(" ".join(current))

    return question_blocks


def parse_mock_exam_questions(markdown_file: Path, chapter_name: str, start_id: int) -> list[dict]:
    items: list[dict] = []
    next_id = start_id
    for exam_number, block in enumerate(extract_mock_question_blocks(markdown_file), start=1):
        parsed = parse_question_block(block)
        if not parsed:
            continue
        prompt, options = parsed
        items.append(
            {
                "id": next_id,
                "examNumber": exam_number,
                "course": "종합모의고사",
                "chapter": chapter_name,
                "prompt": clean_question_prompt(prompt),
                "options": options,
                "source": f"mock_exam/{chapter_name}",
            }
        )
        next_id += 1
    return items


def parse_mock_exam_answers(markdown_file: Path, page_start: int, page_end: int) -> tuple[dict[int, int], dict[int, str]]:
    markdown_text = markdown_file.read_text(encoding="utf-8")
    pages = [
        block for page, block in extract_markdown_pages(markdown_text)
        if page_start <= page <= page_end
    ]

    lines: list[str] = []
    for block in pages:
        for raw in block.splitlines():
            stripped = normalize_question_number_prefix(raw.strip())
            if not stripped or is_page_noise(stripped):
                continue
            lines.append(clean_ocr_line(raw))

    answers: dict[int, int] = {}
    explanations: dict[int, str] = {}

    for index, line in enumerate(lines):
        if re.fullmatch(r"(?:\d{2}\s+){5,}\d{2}", line):
            numbers = [int(token) for token in re.findall(r"\d{2}", line)]
            answer_line_parts: list[str] = []
            pointer = index + 1
            while pointer < len(lines):
                candidate = lines[pointer]
                if re.fullmatch(r"(?:\d{2}\s+){5,}\d{2}", candidate):
                    break
                if re.match(r"^\d{2}\s+.+$", candidate):
                    break
                answer_line_parts.append(candidate)
                tokens = re.findall(r"[①②③④©⊙㈢®@Q¥]|\(\d\)|[1-4]", " ".join(answer_line_parts))
                if len(tokens) >= len(numbers) or len(answer_line_parts) >= 3:
                    break
                pointer += 1
            tokens = re.findall(r"[①②③④©⊙㈢®@Q¥]|\(\d\)|[1-4]", " ".join(answer_line_parts))
            for number, token in zip(numbers, tokens):
                mapped = map_answer_token(token)
                if mapped is not None:
                    answers[number] = mapped

    current_no: int | None = None
    explanation_parts: list[str] = []

    def flush_explanation() -> None:
        nonlocal current_no, explanation_parts
        if current_no is not None and explanation_parts:
            explanations[current_no] = clean_ocr_line(" ".join(explanation_parts))
        current_no = None
        explanation_parts = []

    for line in lines:
        if re.fullmatch(r"(?:\d{2}\s+){5,}\d{2}", line):
            continue

        match = re.match(r"^(\d{2})\s+(.+)$", line)
        if match:
            second_token_is_number_row = len(re.findall(r"\d{2}", line)) >= 4
            if second_token_is_number_row:
                continue
            flush_explanation()
            current_no = int(match.group(1))
            answer_value, remainder = parse_answer_prefix(match.group(2))
            if answer_value is not None and current_no not in answers:
                answers[current_no] = answer_value
            explanation_parts = [remainder] if remainder else []
            continue

        if current_no is not None:
            explanation_parts.append(line)

    flush_explanation()
    return answers, explanations


def attach_mock_exam_metadata(
    questions: list[dict],
    answers: dict[int, int],
    explanations: dict[int, str],
) -> list[dict]:
    items: list[dict] = []
    for question in questions:
        answer = answers.get(question["examNumber"])
        explanation = shorten_text(explanations.get(question["examNumber"], ""), 420)
        if answer is None or not explanation:
            continue
        inferred_answer = infer_answer_from_explanation(question["options"], explanation)
        if inferred_answer is not None:
            answer = inferred_answer
        candidate = {
            **{key: value for key, value in question.items() if key != "examNumber"},
            "answer": answer,
            "explanation": explanation,
        }
        if is_quality_question(candidate):
            items.append(candidate)
    return items


def reindex_items(items: list[dict]) -> list[dict]:
    remapped: list[dict] = []
    for new_id, item in enumerate(sorted(items, key=lambda question: question["id"]), start=1):
        updated = dict(item)
        updated["id"] = new_id
        remapped.append(updated)
    return remapped


def attach_reference_images(items: list[dict]) -> list[dict]:
    enriched: list[dict] = []
    page_cache: dict[tuple[str, str], int | None] = {}

    for item in items:
        updated = dict(item)
        if FIGURE_PROMPT_PATTERN.search(item["prompt"]):
            cache_key = (item["source"], item["prompt"])
            page_number = page_cache.get(cache_key)
            if page_number is None and cache_key not in page_cache:
                page_number = locate_source_page(item["source"], item["prompt"])
                page_cache[cache_key] = page_number

            if page_number:
                image_path = ensure_question_page_image(item["source"], page_number)
                if image_path:
                    updated["sourcePage"] = page_number
                    updated["image"] = f"./{image_path}"
                    updated["imageAlt"] = f"원본 PDF 페이지 {page_number}"

        enriched.append(updated)

    return enriched


CALC_TOPIC_MAP = [
    ("세제", ("계산문제 특강", "세제관련법규/세무전략")),
    ("양도소득", ("계산문제 특강", "세제관련법규/세무전략")),
    ("금융상품", ("계산문제 특강", "금융상품")),
    ("부동산", ("계산문제 특강", "부동산관련상품")),
    ("대안투자", ("계산문제 특강", "대안투자운용/투자전략")),
    ("해외투자", ("계산문제 특강", "해외 증권투자운용/투자전략")),
    ("투자분석기법", ("계산문제 특강", "투자분석기법")),
    ("리스크관리", ("계산문제 특강", "리스크 관리")),
    ("직무윤리", ("계산문제 특강", "직무윤리")),
    ("자본시장", ("계산문제 특강", "자본시장과 금융투자업에 관한 법률 및 금융위원회규정")),
    ("주식투자운용", ("계산문제 특강", "주식투자운용/투자전략")),
    ("채권투자운용", ("계산문제 특강", "채권투자운용/투자전략")),
    ("파생상품", ("계산문제 특강", "파생상품 투자운용/투자전략")),
    ("투자운용결과분석", ("계산문제 특강", "투자운용결과분석")),
    ("거시경제", ("계산문제 특강", "거시경제")),
    ("분산투자", ("계산문제 특강", "분산투자기법")),
]


def infer_calc_topic(text: str) -> tuple[str, str]:
    cleaned = clean_ocr_line(text)
    for keyword, meta in CALC_TOPIC_MAP:
        if keyword in cleaned:
            return meta
    return ("계산문제 특강", "종합 계산문제")


def extract_calc_note_questions(start_id: int) -> list[dict]:
    if PdfReader is None or not CALC_NOTE_PDF.exists():
        return []

    reader = PdfReader(str(CALC_NOTE_PDF))
    items: list[dict] = []
    next_id = start_id

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if "①" not in text or "②" not in text or "③" not in text or "④" not in text:
            continue

        segments = re.split(r"(?=계산문[제데].{0,40}기출 70題)", text)
        for segment in segments:
            if "기출 70題" not in segment:
                continue
            if "더 알아보기" in segment:
                segment = segment.split("더 알아보기", 1)[0]

            parsed = split_first_four_options(segment)
            if not parsed:
                continue

            prompt, options = parsed
            match1 = re.search("①", segment)
            match2 = re.search("②", segment[match1.end():] if match1 else "")
            match3 = re.search("③", segment[match1.end() + match2.end():] if match1 and match2 else "")
            match4 = re.search("④", segment[match1.end() + match2.end() + match3.end():] if match1 and match2 and match3 else "")
            if not (match1 and match2 and match3 and match4):
                continue

            tail_after_options = segment[segment.rfind("④") + 1 :]
            answer_match = re.search(r"^[^\S\r\nA-Za-z가-힣0-9]*([①②③④])[^\n]*$", tail_after_options, re.M)
            if not answer_match:
                continue

            answer = map_answer_token(answer_match.group(1))
            if answer is None:
                continue

            explanation = shorten_text(clean_ocr_line(tail_after_options), 420)
            if len(explanation) < 6:
                continue

            course, chapter = infer_calc_topic("\n".join(segment.splitlines()[:5]) + " " + prompt)
            candidate = {
                "id": next_id,
                "course": course,
                "chapter": chapter,
                "prompt": clean_question_prompt(prompt),
                "options": options,
                "answer": answer,
                "explanation": explanation,
                "source": f"calc_note/page-{page_number}",
            }
            if "아래 해설 풀이 참고" in " ".join(options) or "아래 해설 풀이 참고" in explanation:
                continue
            if is_quality_question(candidate):
                items.append(candidate)
                next_id += 1

    return items


def build_payload() -> dict:
    base_items = merge_base_questions()
    inline_chapter_items, chapter_review_items = extract_real_question_bank(
        base_items,
        start_id=max(item["id"] for item in base_items) + 1,
    )
    next_id = max(item["id"] for item in (chapter_review_items or inline_chapter_items or base_items)) + 1

    mock_exam_1_questions = parse_mock_exam_questions(
        MOCK_EXAM_1_FILE,
        "최종모의고사 제1회",
        start_id=next_id,
    )
    answers_1, explanations_1 = parse_mock_exam_answers(MOCK_ANSWER_FILE, 549, 560)
    mock_exam_1_items = attach_mock_exam_metadata(
        mock_exam_1_questions,
        answers_1,
        explanations_1,
    )
    next_id = max(item["id"] for item in mock_exam_1_items or chapter_review_items or base_items) + 1

    mock_exam_2_questions = parse_mock_exam_questions(
        MOCK_EXAM_2_FILE,
        "최종모의고사 제2회",
        start_id=next_id,
    )
    answers_2, explanations_2 = parse_mock_exam_answers(MOCK_ANSWER_FILE, 561, 570)
    mock_exam_2_items = attach_mock_exam_metadata(
        mock_exam_2_questions,
        answers_2,
        explanations_2,
    )
    next_id = max(
        item["id"]
        for item in mock_exam_2_items or mock_exam_1_items or chapter_review_items or base_items
    ) + 1

    calc_note_items = extract_calc_note_questions(start_id=next_id)

    extracted_items = (
        inline_chapter_items + chapter_review_items + mock_exam_1_items + mock_exam_2_items + calc_note_items
    )
    items = attach_reference_images(reindex_items(base_items + extracted_items))

    course_counts: dict[str, int] = {}
    chapter_counts: dict[str, int] = {}
    for item in items:
        course_counts[item["course"]] = course_counts.get(item["course"], 0) + 1
        chapter_key = f"{item['course']} / {item['chapter']}"
        chapter_counts[chapter_key] = chapter_counts.get(chapter_key, 0) + 1

    lessons = build_lessons(items)

    return {
        "title": "투자자산운용사 확장 문제은행",
        "description": "기본 100문항, 챕터별 핵심문제·보충문제·말미 문제, 최종모의고사, 계산문제 특강노트를 합친 확장 문제은행",
        "baseQuestionCount": len(base_items),
        "generatedQuestionCount": 0,
        "inlineChapterQuestionCount": len(inline_chapter_items),
        "chapterReviewQuestionCount": len(chapter_review_items),
        "mockExamQuestionCount": len(mock_exam_1_items) + len(mock_exam_2_items),
        "calcNoteQuestionCount": len(calc_note_items),
        "extractedQuestionCount": len(extracted_items),
        "totalQuestions": len(items),
        "courseCounts": course_counts,
        "chapterCounts": chapter_counts,
        "lessonCount": len(lessons),
        "lessons": lessons,
        "questions": items,
    }


def render_question_markdown(items: list[dict], title: str, description: str) -> str:
    lines = [f"# {title}", "", f"- 설명: {description}", "- 형식: 객관식 4지선다", ""]

    current_course = None
    current_chapter = None
    for item in items:
        if item["course"] != current_course:
            current_course = item["course"]
            current_chapter = None
            lines.append(f"## {current_course}")
            lines.append("")

        if item["chapter"] != current_chapter:
            current_chapter = item["chapter"]
            lines.append(f"### {current_chapter}")
            lines.append("")

        lines.append(f"{item['id']}. {item['prompt']}")
        for index, option in enumerate(item["options"], start=1):
            lines.append(f"   {index}. {option}")
        lines.append("")

    lines.extend(["## 정답 및 풀이", ""])

    for item in items:
        lines.append(f"{item['id']}. 정답: {item['answer']}")
        lines.append(
            f"풀이: {item['explanation']} 근거: `{item['source']}`"
        )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    payload = build_payload()
    items = sorted(payload["questions"], key=lambda question: question["id"])

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    GENERATED_BANK_FILE.write_text(
        render_question_markdown(
            items,
            title=payload["title"],
            description=payload["description"],
        ),
        encoding="utf-8",
    )

    print(
        "Wrote "
        f"{payload['totalQuestions']} questions "
        f"({payload['baseQuestionCount']} base + "
        f"{payload['inlineChapterQuestionCount']} inline + "
        f"{payload['chapterReviewQuestionCount']} chapter review + "
        f"{payload['mockExamQuestionCount']} mock + "
        f"{payload['calcNoteQuestionCount']} calc) "
        f"to {OUTPUT_FILE}"
    )
    print(f"Wrote markdown bank to {GENERATED_BANK_FILE}")


if __name__ == "__main__":
    main()
