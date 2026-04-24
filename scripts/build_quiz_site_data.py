from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BASE_SOURCE_FILE = ROOT / "markdown" / "투자자산운용사_예상문제_100선.md"
GENERATED_BANK_FILE = ROOT / "markdown" / "투자자산운용사_확장_문제은행.md"
OUTPUT_FILE = ROOT / "docs" / "data" / "questions.json"


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_display_text(text: str) -> str:
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"[★☆◦•▪◆◇□■△▽▶◀※]", " ", text)
    text = re.sub(r"\b[FDQGC]+\b", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:;,")


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


def parse_option_prefix(line: str, expected_next: int | None = None) -> tuple[int | None, str | None]:
    stripped = line.strip()
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
    stripped = text.strip()
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


def extract_code_blocks(markdown_text: str) -> list[str]:
    return re.findall(r"```text\n(.*?)```", markdown_text, flags=re.S)


def finalize_question(question: dict | None) -> dict | None:
    if not question:
        return None

    prompt = clean_ocr_line(" ".join(question["prompt_parts"]))
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
        line = raw.strip()
        if line == "정답 및 해설":
            flush_question()
            mode = "answers"
            current_answer_no = None
            continue

        if mode == "questions":
            question_match = re.match(r"^(\d{2})\s+(.+)$", line)
            option_no, option_text = parse_option_prefix(line, expected_next=current_option + 1 if current_option else 1)
            if question_match and option_no is None:
                flush_question()
                current_question = {
                    "number": int(question_match.group(1)),
                    "prompt_parts": [clean_ocr_line(question_match.group(2))],
                    "options": {},
                }
                current_option = None
                continue

            if current_question and option_no is not None and option_text:
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


def extract_real_question_bank(base_items: list[dict], start_id: int) -> list[dict]:
    source_map: dict[str, tuple[str, str]] = {}
    for item in base_items:
        source_map.setdefault(item["source"], (item["course"], item["chapter"]))

    existing_keys = {normalize_question_key(item) for item in base_items}
    extracted: list[dict] = []
    next_id = start_id

    for source, (course, chapter) in source_map.items():
        for item in extract_chapter_review_questions(source, course, chapter):
            item_key = normalize_question_key(item)
            if item_key in existing_keys:
                continue
            existing_keys.add(item_key)
            extracted.append({**item, "id": next_id})
            next_id += 1

    return extracted


def build_payload() -> dict:
    base_items = merge_base_questions()
    extracted_items = extract_real_question_bank(
        base_items,
        start_id=max(item["id"] for item in base_items) + 1,
    )
    items = base_items + extracted_items

    course_counts: dict[str, int] = {}
    chapter_counts: dict[str, int] = {}
    for item in items:
        course_counts[item["course"]] = course_counts.get(item["course"], 0) + 1
        chapter_key = f"{item['course']} / {item['chapter']}"
        chapter_counts[chapter_key] = chapter_counts.get(chapter_key, 0) + 1

    lessons = build_lessons(items)

    return {
        "title": "투자자산운용사 확장 문제은행",
        "description": "기존 chapter markdown의 실제 문제와 기본 100문항을 합친 확장 문제은행",
        "baseQuestionCount": len(base_items),
        "generatedQuestionCount": 0,
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
        f"({payload['baseQuestionCount']} base + {payload['generatedQuestionCount']} generated) "
        f"to {OUTPUT_FILE}"
    )
    print(f"Wrote markdown bank to {GENERATED_BANK_FILE}")


if __name__ == "__main__":
    main()
