# 투자자산운용사 퀴즈 사이트

정적 웹사이트는 `docs/` 폴더에 들어 있습니다. GitHub Pages에서 바로 배포할 수 있는 구조입니다.

## 포함된 파일

- `docs/index.html`: 메인 페이지
- `docs/styles.css`: UI 스타일
- `docs/app.js`: 퀴즈 로직
- `docs/data/questions.json`: 웹앱이 읽는 문제 데이터
- `scripts/build_quiz_site_data.py`: 문제 md를 JSON으로 변환하는 스크립트
- `markdown/투자자산운용사_예상문제_100선.md`: 문제 원본

## 데이터 다시 생성하기

문제 md를 수정한 뒤 아래 명령으로 웹용 JSON을 다시 생성합니다.

```bash
python3 scripts/build_quiz_site_data.py
```

## 로컬 실행

```bash
python3 -m http.server 4173 --directory docs
```

그 다음 브라우저에서 `http://127.0.0.1:4173`으로 접속합니다.

## GitHub Pages 배포

1. 이 폴더를 GitHub 저장소에 올립니다.
2. 저장소 Settings > Pages로 이동합니다.
3. Build and deployment의 Source를 `Deploy from a branch`로 설정합니다.
4. 브랜치는 `main`, 폴더는 `/docs`를 선택합니다.
5. 저장하면 몇 분 뒤 Pages URL이 열립니다.

## 기능

- 학습 모드 / 시험 모드
- 과목 및 챕터 필터
- 문제 수 선택
- 문항 순서 섞기
- 오답만 다시 풀기
- 정답, 풀이, 출처 chapter 표시
- 로컬 오답 보관함(localStorage)
