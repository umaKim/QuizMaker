from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_FILE = ROOT / "markdown" / "투자자산운용사_예상문제_100선.md"
OUTPUT_FILE = ROOT / "docs" / "data" / "questions.json"


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


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
            if re.match(r"^\d+\. 정답: [1-4]\s*$", current.strip()) or current.startswith("### ") or current.startswith("## "):
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


def build_payload() -> dict:
    text = SOURCE_FILE.read_text(encoding="utf-8")
    question_part, explanation_part = text.split("## 정답 및 풀이", 1)
    questions = parse_questions(question_part)
    explanations = parse_explanations(explanation_part)

    if len(questions) != 100:
        raise ValueError(f"Expected 100 questions, got {len(questions)}")
    if len(explanations) != 100:
        raise ValueError(f"Expected 100 explanations, got {len(explanations)}")

    items = []
    for question in questions:
        extra = explanations.get(question["id"])
        if extra is None:
            raise ValueError(f"Missing explanation for question {question['id']}")
        items.append({**question, **extra})

    course_counts: dict[str, int] = {}
    chapter_counts: dict[str, int] = {}
    for item in items:
        course_counts[item["course"]] = course_counts.get(item["course"], 0) + 1
        chapter_key = f"{item['course']} / {item['chapter']}"
        chapter_counts[chapter_key] = chapter_counts.get(chapter_key, 0) + 1

    return {
        "title": "투자자산운용사 예상문제 100선",
        "description": "기존 chapter markdown을 바탕으로 정리한 100문항 퀴즈 세트",
        "totalQuestions": len(items),
        "courseCounts": course_counts,
        "chapterCounts": chapter_counts,
        "questions": items,
    }


def main() -> None:
    payload = build_payload()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {payload['totalQuestions']} questions to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
