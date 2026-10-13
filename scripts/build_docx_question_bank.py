from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DOCX = Path("/Users/uma/Downloads/투운사 정리본.docx")
OUTPUT_QUESTIONS = ROOT / "docs" / "data" / "questions.json"
OUTPUT_STUDY_GUIDE = ROOT / "docs" / "data" / "study-guide.json"
OUTPUT_MARKDOWN = ROOT / "markdown" / "투자자산운용사_확장_문제은행.md"

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

COURSE_NAMES = {
    "1과목": "제1과목 금융상품 및 세제",
    "2과목": "제2과목 투자운용 및 전략 II 및 투자분석",
    "3과목": "제3과목 직무윤리 및 법규/투자운용 및 전략 I 등",
}

CHAPTER_MAP = {
    "세제 및 절세전략": "1. 세제관련법규/세무전략",
    "금융상품": "2. 금융상품",
    "부동산상품": "3. 부동산관련상품",
    "대안투자": "4. 대안투자운용/투자전략",
    "해외투자": "5. 해외 증권투자운용/투자전략",
    "투자분석기법": "6. 투자분석기법",
    "리스크관리": "7. 리스크 관리",
    "직무윤리": "8. 직무윤리",
    "자본시장법 및 금융위원회 규정": "9. 자본시장과 금융투자업에 관한 법률 및 금융위원회규정",
    "협회규정": "10. 한국금융투자협회규정",
    "주식투자운용": "11. 주식투자운용/투자전략",
    "채권투자운용": "12. 채권투자운용/투자전략",
    "파생상품투자운용": "13. 파생상품 투자운용/투자전략",
    "투자운용결과분석": "14. 투자운용결과분석",
    "거시경제": "15. 거시경제",
    "분산투자이론": "16. 분산투자기법",
}

EXAM_BLUEPRINT = [
    ("1. 세제관련법규/세무전략", 7),
    ("2. 금융상품", 8),
    ("3. 부동산관련상품", 5),
    ("4. 대안투자운용/투자전략", 5),
    ("5. 해외 증권투자운용/투자전략", 5),
    ("6. 투자분석기법", 12),
    ("7. 리스크 관리", 8),
    ("8. 직무윤리", 5),
    ("9. 자본시장과 금융투자업에 관한 법률 및 금융위원회규정", 11),
    ("10. 한국금융투자협회규정", 3),
    ("11. 주식투자운용/투자전략", 6),
    ("12. 채권투자운용/투자전략", 6),
    ("13. 파생상품 투자운용/투자전략", 6),
    ("14. 투자운용결과분석", 4),
    ("15. 거시경제", 4),
    ("16. 분산투자기법", 5),
]


@dataclass
class Topic:
    title: str
    facts: list[str] = field(default_factory=list)
    pairs: list[tuple[str, str]] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class Chapter:
    raw_title: str
    course: str
    chapter: str
    topics: list[Topic] = field(default_factory=list)


def clean_text(text: str) -> str:
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("ㅇ", "O").replace("x", "X")
    text = text.replace("->", "→")
    text = re.sub(r"^\*+\s*", "", text)
    text = re.sub(r"[★☆◦•▪◆◇□■△▽▶◀※]", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" \t-–—:;*")
    text = re.sub(r"^→\s*", "", text)
    return text.strip()


def slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "-", text).strip("-")[:80] or "section"


def normalize_key(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def docx_blocks(path: Path) -> list[tuple[str, str | list[list[str]]]]:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find("w:body", NS)
    if body is None:
        return []

    blocks: list[tuple[str, str | list[list[str]]]] = []
    for child in list(body):
        tag = child.tag.split("}")[-1]
        if tag == "p":
            raw_text = "".join(t.text or "" for t in child.findall(".//w:t", NS)).strip()
            text = clean_text(raw_text)
            if raw_text.startswith("*") and text:
                text = f"* {text}"
            if text:
                blocks.append(("p", text))
        elif tag == "tbl":
            rows: list[list[str]] = []
            for tr in child.findall("./w:tr", NS):
                cells: list[str] = []
                for tc in tr.findall("./w:tc", NS):
                    cell_parts: list[str] = []
                    for p in tc.findall("./w:p", NS):
                        cell_text = clean_text("".join(t.text or "" for t in p.findall(".//w:t", NS)))
                        if cell_text:
                            cell_parts.append(cell_text)
                    cells.append(clean_text(" / ".join(cell_parts)))
                if any(cells):
                    rows.append(cells)
            if rows:
                blocks.append(("tbl", rows))
    return blocks


def parse_chapter_heading(text: str) -> str | None:
    match = re.match(r"^\*\s*(.+?)\s+\d+문항", text)
    if not match:
        return None
    return clean_text(match.group(1))


def parse_topic_heading(text: str) -> str | None:
    match = re.match(r"^(\d{1,2})\.\s+(.+)$", text)
    if not match:
        return None
    title = clean_text(match.group(2))
    if len(title) < 2:
        return None
    return title


def should_keep_fact(text: str) -> bool:
    text = clean_text(text)
    if len(text) < 8 or len(text) > 180:
        return False
    if text.count("(") != text.count(")"):
        return False
    blocked = [
        "문항",
        "목차",
        "예시:",
        "소송을 위해서라면",
        "구분 |",
        "내용 |",
        "항목 |",
        "표 ",
    ]
    if any(token in text for token in blocked):
        return False
    if re.fullmatch(r"[0-9.,%~ /()A-Za-z]+", text):
        return False
    return True


def parse_pair(text: str) -> tuple[str, str] | None:
    candidates = [
        r"^([^:：]{2,36})[:：]\s*(.{2,130})$",
        r"^(.{2,36}?)\s*-\s*(.{2,130})$",
        r"^(.{2,28}?)\s{2,}(.{2,130})$",
    ]
    for pattern in candidates:
        match = re.match(pattern, text)
        if not match:
            continue
        key = clean_text(match.group(1))
        value = clean_text(match.group(2))
        if not key or not value:
            continue
        if key in {"예외", "단", "비고", "상황", "종류", "구분"}:
            continue
        if len(key) > 36 or len(value) > 130:
            continue
        return key, value
    return None


def table_to_facts(rows: list[list[str]]) -> tuple[list[str], list[tuple[str, str]]]:
    facts: list[str] = []
    pairs: list[tuple[str, str]] = []
    if not rows:
        return facts, pairs

    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    header = padded[0]
    has_header = sum(1 for cell in header if cell) >= 2

    for row_index, row in enumerate(padded[1:] if has_header else padded):
        cells = [clean_text(cell) for cell in row if clean_text(cell)]
        if len(cells) < 2:
            continue
        if has_header and row_index < 12:
            for col_index, cell in enumerate(row):
                if not cell or col_index >= len(header) or not header[col_index]:
                    continue
                key = clean_text(f"{header[col_index]} {cells[0]}" if col_index else cells[0])
                value = clean_text(cell)
                if key != value and len(value) <= 130:
                    pairs.append((key, value))
        joined = " | ".join(cells)
        if should_keep_fact(joined):
            facts.append(joined)
    return facts, pairs


def parse_docx(path: Path) -> list[Chapter]:
    chapters: list[Chapter] = []
    current_course = ""
    current_chapter: Chapter | None = None
    current_topic: Topic | None = None

    for block_type, value in docx_blocks(path):
        if block_type == "p":
            text = value if isinstance(value, str) else ""
            if text in COURSE_NAMES:
                current_course = COURSE_NAMES[text]
                continue

            chapter_raw = parse_chapter_heading(text)
            if chapter_raw:
                mapped = CHAPTER_MAP.get(chapter_raw, chapter_raw)
                current_chapter = Chapter(chapter_raw, current_course, mapped)
                chapters.append(current_chapter)
                current_topic = None
                continue

            if current_topic and re.match(r"^\*\s*[^*].{2,50}$", text):
                sub_title = clean_text(text)
                if not re.search(r"[.。!?]$", sub_title):
                    current_topic = Topic(sub_title)
                    current_chapter.topics.append(current_topic)
                    continue

            topic_title = parse_topic_heading(text)
            if topic_title and current_chapter:
                current_topic = Topic(topic_title)
                current_chapter.topics.append(current_topic)
                continue

            if current_topic and should_keep_fact(text):
                text = clean_text(text)
                pair = parse_pair(text)
                current_topic.facts.append(text)
                if pair:
                    current_topic.pairs.append(pair)

        elif block_type == "tbl" and current_topic:
            rows = value if isinstance(value, list) else []
            current_topic.tables.append(rows)
            facts, pairs = table_to_facts(rows)
            current_topic.facts.extend(facts)
            current_topic.pairs.extend(pairs)

    for chapter in chapters:
        chapter.topics = [topic for topic in chapter.topics if topic.facts or topic.pairs]
    return chapters


def unique_options(options: list[str]) -> bool:
    keys = [normalize_key(option)[:90] for option in options]
    return len(options) == 4 and len(set(keys)) == 4 and all(len(key) >= 2 for key in keys)


def shuffled(items: list, seed: str) -> list:
    copy = list(items)
    random.Random(seed).shuffle(copy)
    return copy


def make_source(chapter: Chapter, topic: Topic) -> str:
    return f"docx/투운사 정리본.docx#{slug(chapter.chapter)}#{slug(topic.title)}"


def reference_facts(topic: Topic, priority: list[str] | None = None, limit: int = 12) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for fact in (priority or []) + topic.facts:
        fact = clean_text(fact)
        key = normalize_key(fact)
        if not fact or key in seen:
            continue
        seen.add(key)
        result.append(fact)
        if len(result) >= limit:
            break
    return result


def create_pair_question(
    chapter: Chapter,
    topic: Topic,
    pair: tuple[str, str],
    chapter_pairs: list[tuple[Topic, tuple[str, str]]],
    question_id: int,
) -> dict | None:
    key, value = pair
    if len(value) > 90:
        return None
    same_topic_pairs = [
        (other_topic, other_pair)
        for other_topic, other_pair in chapter_pairs
        if other_topic.title == topic.title
    ]
    distractors = [
        other_pair[1]
        for other_topic, other_pair in shuffled(same_topic_pairs, f"pair-{chapter.chapter}-{topic.title}-{key}")
        if other_pair != pair
        and 3 <= len(other_pair[1]) <= 90
        and normalize_key(other_pair[1]) != normalize_key(value)
    ]
    if len(distractors) < 3:
        return None
    options = shuffled([value] + distractors[:3], f"pair-options-{chapter.chapter}-{topic.title}-{key}")
    if not unique_options(options):
        return None
    answer = options.index(value) + 1
    return {
        "id": question_id,
        "course": chapter.course,
        "chapter": chapter.chapter,
        "prompt": f"다음 중 '{key}'에 대한 설명으로 옳은 것은?",
        "options": options,
        "answer": answer,
        "explanation": f"정리본의 '{topic.title}' 항목에서는 '{key}'를 '{value}'로 정리한다.",
        "referenceFacts": reference_facts(topic, [f"{key}: {value}"]),
        "source": make_source(chapter, topic),
    }


def create_statement_question(
    chapter: Chapter,
    topic: Topic,
    fact: str,
    chapter_facts: list[tuple[Topic, str]],
    question_id: int,
) -> dict | None:
    if len(fact) > 120:
        return None
    distractors = [
        other_fact
        for other_topic, other_fact in shuffled(chapter_facts, f"fact-{chapter.chapter}-{topic.title}-{fact}")
        if other_topic.title != topic.title
        and 8 <= len(other_fact) <= 120
        and normalize_key(other_fact) != normalize_key(fact)
    ]
    if len(distractors) < 3:
        return None
    options = shuffled([fact] + distractors[:3], f"fact-options-{chapter.chapter}-{topic.title}-{fact}")
    if not unique_options(options):
        return None
    answer = options.index(fact) + 1
    return {
        "id": question_id,
        "course": chapter.course,
        "chapter": chapter.chapter,
        "prompt": f"다음 중 '{topic.title}'에 관한 설명으로 옳은 것은?",
        "options": options,
        "answer": answer,
        "explanation": f"정리본의 '{topic.title}' 항목에서는 '{fact}'로 정리되어 있다.",
        "referenceFacts": reference_facts(topic, [fact]),
        "source": make_source(chapter, topic),
    }


def create_odd_question(
    chapter: Chapter,
    topic: Topic,
    facts: list[str],
    chapter_facts: list[tuple[Topic, str]],
    question_id: int,
) -> dict | None:
    usable = [fact for fact in facts if 8 <= len(fact) <= 100]
    if len(usable) < 3:
        return None
    wrong_candidates = [
        other_fact
        for other_topic, other_fact in shuffled(chapter_facts, f"odd-{chapter.chapter}-{topic.title}")
        if other_topic.title != topic.title and 8 <= len(other_fact) <= 100
    ]
    if not wrong_candidates:
        return None
    correct_facts = shuffled(usable, f"odd-correct-{chapter.chapter}-{topic.title}")[:3]
    wrong = wrong_candidates[0]
    options = shuffled(correct_facts + [wrong], f"odd-options-{chapter.chapter}-{topic.title}")
    if not unique_options(options):
        return None
    answer = options.index(wrong) + 1
    return {
        "id": question_id,
        "course": chapter.course,
        "chapter": chapter.chapter,
        "prompt": f"다음 중 '{topic.title}'에 관한 설명으로 가장 거리가 먼 것은?",
        "options": options,
        "answer": answer,
        "explanation": f"{answer}번은 같은 챕터의 다른 항목에 관한 설명이다. '{topic.title}'의 핵심 내용은 정리본 해당 항목을 확인한다.",
        "referenceFacts": reference_facts(topic, correct_facts),
        "source": make_source(chapter, topic),
    }


def dedupe_question(question: dict, seen: set[str]) -> bool:
    key = normalize_key(
        question["prompt"] + "|" + "|".join(question["options"]) + "|" + str(question["answer"])
    )
    if key in seen:
        return False
    seen.add(key)
    return True


def generate_questions(chapters: list[Chapter]) -> list[dict]:
    questions: list[dict] = []
    seen: set[str] = set()
    question_id = 1
    desired_by_chapter = {chapter: count * 5 for chapter, count in EXAM_BLUEPRINT}

    for chapter in chapters:
        chapter_facts = [
            (topic, fact)
            for topic in chapter.topics
            for fact in topic.facts
            if should_keep_fact(fact)
        ]
        chapter_pairs = [
            (topic, pair)
            for topic in chapter.topics
            for pair in topic.pairs
            if 2 <= len(pair[0]) <= 36 and 2 <= len(pair[1]) <= 130
        ]
        candidates: list[dict] = []

        for topic, pair in shuffled(chapter_pairs, f"pairs-{chapter.chapter}"):
            question = create_pair_question(chapter, topic, pair, chapter_pairs, 0)
            if question:
                candidates.append(question)

        for topic, fact in shuffled(chapter_facts, f"facts-{chapter.chapter}"):
            question = create_statement_question(chapter, topic, fact, chapter_facts, 0)
            if question:
                candidates.append(question)

        for topic in chapter.topics:
            question = create_odd_question(chapter, topic, topic.facts, chapter_facts, 0)
            if question:
                candidates.append(question)

        desired = desired_by_chapter.get(chapter.chapter, 12)
        for candidate in shuffled(candidates, f"candidates-{chapter.chapter}"):
            candidate["id"] = question_id
            if not dedupe_question(candidate, seen):
                continue
            questions.append(candidate)
            question_id += 1
            if sum(1 for item in questions if item["chapter"] == chapter.chapter) >= desired:
                break

    return questions


def lesson_overview(chapter: Chapter) -> str:
    topics = [topic.title for topic in chapter.topics[:5]]
    preview = ", ".join(topics)
    return f"{chapter.chapter}은 정리본의 {preview} 등을 중심으로 학습합니다. 문제는 이 정리본의 문장과 표에서만 구성했습니다."


def build_lessons(chapters: list[Chapter], questions: list[dict]) -> list[dict]:
    grouped_ids: dict[str, list[int]] = {}
    for question in questions:
        grouped_ids.setdefault(question["chapter"], []).append(question["id"])

    lessons = []
    for chapter in chapters:
        question_ids = grouped_ids.get(chapter.chapter, [])
        topics = []
        for topic in chapter.topics[:24]:
            bullets = topic.facts[:5]
            summary = " ".join(bullets[:2]) or f"{topic.title}의 핵심 개념을 정리합니다."
            topics.append(
                {
                    "title": topic.title,
                    "summary": summary[:260],
                    "page": "",
                }
            )
        lessons.append(
            {
                "source": f"docx/{slug(chapter.chapter)}",
                "displayTitle": f"정리본 - {chapter.chapter}",
                "course": chapter.course,
                "chapter": chapter.chapter,
                "overview": lesson_overview(chapter),
                "topics": topics,
                "questionIds": question_ids,
                "questionCount": len(question_ids),
                "notionSectionTitle": "",
                "notionHighlightCount": 0,
                "notionHighlights": [],
            }
        )
    return lessons


def build_study_guide(chapters: list[Chapter]) -> dict:
    sections = []
    for chapter in chapters:
        topics = []
        for topic in chapter.topics:
            bullets = topic.facts[:20]
            if not bullets:
                continue
            topics.append(
                {
                    "topic": topic.title,
                    "context": f"{chapter.chapter} > {topic.title}",
                    "summary": f"{topic.title}은 {chapter.chapter}에서 정리본이 강조한 핵심 항목입니다. 아래 문장을 정의, 요건, 숫자 기준, 예외로 나누어 확인합니다.",
                    "examTip": "보기에서는 숫자 기준, 예외, 반대 개념을 바꾸어 출제되기 쉽습니다.",
                    "bullets": bullets,
                    "source": "투운사 정리본.docx",
                }
            )
        sections.append(
            {
                "id": slug(f"{chapter.course}-{chapter.chapter}"),
                "course": chapter.course,
                "chapter": chapter.chapter,
                "title": chapter.raw_title,
                "source": "투운사 정리본.docx",
                "factCount": sum(len(topic["bullets"]) for topic in topics),
                "topics": topics,
            }
        )
    return {
        "title": "투자자산운용사 지식 정리",
        "description": "첨부 DOCX 정리본만 사용해 만든 챕터별 지식 정리",
        "sectionCount": len(sections),
        "sections": sections,
    }


def build_exam_sets(questions: list[dict]) -> list[dict]:
    by_chapter: dict[str, list[int]] = {}
    for question in questions:
        by_chapter.setdefault(question["chapter"], []).append(question["id"])

    blueprint_ids: list[int] = []
    for chapter, count in EXAM_BLUEPRINT:
        blueprint_ids.extend(by_chapter.get(chapter, [])[:count])

    all_ids = [question["id"] for question in questions]
    return [
        {
            "id": "docx-real-100",
            "title": "정리본 기반 실전 100문항",
            "description": "투자자산운용사 시험 배점 흐름에 맞춰 DOCX 정리본 문항을 챕터별로 배치한 세트입니다.",
            "questionIds": blueprint_ids[:100],
            "timerMinutes": 120,
        },
        {
            "id": "docx-all",
            "title": "정리본 전체 문제은행",
            "description": "첨부한 정리본에서 만든 전체 문항입니다.",
            "questionIds": all_ids,
            "timerMinutes": 0,
        },
    ]


def course_counts(questions: list[dict]) -> dict[str, int]:
    result: dict[str, int] = {}
    for question in questions:
        result[question["course"]] = result.get(question["course"], 0) + 1
    return result


def chapter_counts(questions: list[dict]) -> dict[str, int]:
    result: dict[str, int] = {}
    for question in questions:
        key = f"{question['course']} / {question['chapter']}"
        result[key] = result.get(key, 0) + 1
    return result


def render_markdown(questions: list[dict]) -> str:
    lines = [
        "# 투자자산운용사 DOCX 기반 문제은행",
        "",
        "- 원천 자료: 투운사 정리본.docx",
        "- 노션 자료는 사용하지 않음",
        "",
    ]
    current_course = ""
    current_chapter = ""
    for question in questions:
        if question["course"] != current_course:
            current_course = question["course"]
            lines.extend([f"## {current_course}", ""])
        if question["chapter"] != current_chapter:
            current_chapter = question["chapter"]
            lines.extend([f"### {current_chapter}", ""])
        lines.append(f"{question['id']}. {question['prompt']}")
        for index, option in enumerate(question["options"], start=1):
            lines.append(f"   {index}. {option}")
        lines.extend(["", f"정답: {question['answer']}번", f"풀이: {question['explanation']}", ""])
    return "\n".join(lines)


def main() -> None:
    if not SOURCE_DOCX.exists():
        raise FileNotFoundError(SOURCE_DOCX)

    chapters = parse_docx(SOURCE_DOCX)
    questions = generate_questions(chapters)
    lessons = build_lessons(chapters, questions)
    study_guide = build_study_guide(chapters)
    exam_sets = build_exam_sets(questions)

    payload = {
        "title": "투자자산운용사 DOCX 기반 문제은행",
        "description": "첨부한 투운사 정리본.docx만 사용해 생성한 문제은행입니다. Notion 자료는 제외했습니다.",
        "baseQuestionCount": 0,
        "generatedQuestionCount": len(questions),
        "inlineChapterQuestionCount": 0,
        "chapterReviewQuestionCount": 0,
        "mockExamQuestionCount": 0,
        "calcNoteQuestionCount": 0,
        "supplementalQuestionCount": 0,
        "extractedQuestionCount": 0,
        "notionGeneratedQuestionCount": 0,
        "totalQuestions": len(questions),
        "courseCounts": course_counts(questions),
        "chapterCounts": chapter_counts(questions),
        "lessonCount": len(lessons),
        "notionSourceUrl": "",
        "notionBlockCount": 0,
        "docxSource": str(SOURCE_DOCX),
        "examBlueprint": [
            {"chapter": chapter, "count": count}
            for chapter, count in EXAM_BLUEPRINT
        ],
        "lessons": lessons,
        "examSets": exam_sets,
        "questions": questions,
    }

    OUTPUT_QUESTIONS.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MARKDOWN.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_QUESTIONS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_STUDY_GUIDE.write_text(json.dumps(study_guide, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_MARKDOWN.write_text(render_markdown(questions), encoding="utf-8")
    print(
        f"Wrote {len(questions)} DOCX-only questions, {len(lessons)} lessons, "
        f"{study_guide['sectionCount']} study sections"
    )


if __name__ == "__main__":
    main()
