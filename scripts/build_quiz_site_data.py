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


def unique_topic_pool(topics: list[dict]) -> list[dict]:
    pool: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for topic in topics:
        key = (topic["source"], topic["title"])
        if key in seen:
            continue
        seen.add(key)
        pool.append(topic)
    return pool


def gather_topic_context(lessons: list[dict]) -> list[dict]:
    contexts: list[dict] = []
    for lesson in lessons:
        lesson_key = f"{lesson['course']} / {lesson['chapter']}"
        for index, topic in enumerate(lesson["topics"]):
            title = shorten_text(topic["title"], 54)
            summary = shorten_text(topic["summary"], 110)
            if len(title) < 2 or len(summary) < 18:
                continue
            contexts.append(
                {
                    "lessonKey": lesson_key,
                    "course": lesson["course"],
                    "chapter": lesson["chapter"],
                    "displayTitle": lesson["displayTitle"],
                    "source": lesson["source"],
                    "page": topic.get("page", ""),
                    "topicIndex": index,
                    "title": title,
                    "summary": summary,
                }
            )
    return contexts


def select_other_topics(target: dict, all_topics: list[dict], count: int) -> list[dict]:
    same_lesson = [
        topic
        for topic in all_topics
        if topic["lessonKey"] == target["lessonKey"] and topic["title"] != target["title"]
    ]
    same_course = [
        topic
        for topic in all_topics
        if topic["course"] == target["course"]
        and topic["lessonKey"] != target["lessonKey"]
        and topic["title"] != target["title"]
    ]
    others = [
        topic
        for topic in all_topics
        if topic["course"] != target["course"] and topic["title"] != target["title"]
    ]

    ordered = unique_topic_pool(same_lesson + same_course + others)
    return ordered[:count]


def build_options(correct: str, distractors: list[str], seed: int) -> tuple[list[str], int]:
    picked = [shorten_text(item, 96) for item in distractors[:3]]
    options = picked[:]
    answer_index = seed % 4
    options.insert(answer_index, shorten_text(correct, 96))
    while len(options) < 4:
        options.append("해당 사항 없음")
    return options[:4], answer_index + 1


def generated_explanation(topic: dict) -> str:
    page = f" PDF {topic['page']}쪽 부근에서" if topic.get("page") else ""
    return (
        f"{topic['title']}는 {topic['chapter']} 챕터에서{page} "
        f"{topic['summary']}를 중심으로 정리되는 개념이다."
    )


def generate_supplemental_questions(lessons: list[dict], start_id: int) -> list[dict]:
    all_topics = gather_topic_context(lessons)
    supplemental: list[dict] = []
    next_id = start_id

    for topic in all_topics:
        distractor_topics = select_other_topics(topic, all_topics, 3)
        if len(distractor_topics) < 3:
            continue

        title_options, title_answer = build_options(
            topic["title"],
            [candidate["title"] for candidate in distractor_topics],
            seed=next_id,
        )
        supplemental.append(
            {
                "id": next_id,
                "course": topic["course"],
                "chapter": topic["chapter"],
                "prompt": (
                    "다음 설명과 가장 관련된 개념으로 가장 적절한 것은? "
                    f"{topic['summary']}"
                ),
                "options": title_options,
                "answer": title_answer,
                "explanation": generated_explanation(topic),
                "source": topic["source"],
            }
        )
        next_id += 1

        summary_options, summary_answer = build_options(
            topic["summary"],
            [candidate["summary"] for candidate in distractor_topics],
            seed=next_id,
        )
        supplemental.append(
            {
                "id": next_id,
                "course": topic["course"],
                "chapter": topic["chapter"],
                "prompt": f"다음 중 {topic['title']}에 대한 설명으로 가장 적절한 것은?",
                "options": summary_options,
                "answer": summary_answer,
                "explanation": generated_explanation(topic),
                "source": topic["source"],
            }
        )
        next_id += 1

    return supplemental


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


def build_payload() -> dict:
    base_items = merge_base_questions()
    seed_lessons = build_lessons(base_items)
    supplemental_items = generate_supplemental_questions(
        seed_lessons,
        start_id=max(item["id"] for item in base_items) + 1,
    )
    items = base_items + supplemental_items

    course_counts: dict[str, int] = {}
    chapter_counts: dict[str, int] = {}
    for item in items:
        course_counts[item["course"]] = course_counts.get(item["course"], 0) + 1
        chapter_key = f"{item['course']} / {item['chapter']}"
        chapter_counts[chapter_key] = chapter_counts.get(chapter_key, 0) + 1

    lessons = build_lessons(items)

    return {
        "title": "투자자산운용사 확장 문제은행",
        "description": "기존 chapter markdown과 기본 100문항을 바탕으로 확장한 다문항 퀴즈 세트",
        "baseQuestionCount": len(base_items),
        "generatedQuestionCount": len(supplemental_items),
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
