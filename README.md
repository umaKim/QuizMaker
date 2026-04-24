# 투자자산운용사 퀴즈 사이트

정적 웹사이트는 `docs/` 폴더에 들어 있습니다. GitHub Pages에서 바로 배포할 수 있는 구조입니다.

## 포함된 파일

- `docs/index.html`: 메인 페이지
- `docs/styles.css`: UI 스타일
- `docs/app.js`: 퀴즈 로직
- `docs/data/questions.json`: 웹앱이 읽는 문제 데이터
- `scripts/build_quiz_site_data.py`: 기본 문제와 chapter md를 바탕으로 확장 문제은행을 생성하는 스크립트
- `markdown/투자자산운용사_예상문제_100선.md`: 기본 100문항 원본
- `markdown/투자자산운용사_확장_문제은행.md`: 생성된 확장 문제은행

## 데이터 다시 생성하기

문제 md나 chapter md를 수정한 뒤 아래 명령으로 웹용 JSON과 확장형 문제은행 md를 다시 생성합니다.

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
3. Build and deployment의 Source를 `GitHub Actions`로 설정합니다.
4. 이 저장소에는 `.github/workflows/deploy-pages.yml`이 포함되어 있으므로 이후 `main` 브랜치 푸시마다 자동 배포됩니다.
5. 저장하면 몇 분 뒤 Pages URL이 열립니다.

## 기능

- 학습 모드 / 시험 모드
- 과목 및 챕터 필터
- 문제 수 선택
- 문항 순서 섞기
- 오답만 다시 풀기
- 챕터별 핵심 개념 학습
- 정답, 풀이, 출처 chapter 표시
- 로컬 오답 보관함(localStorage)
- 오답노트 저장 및 해결 상태 관리
