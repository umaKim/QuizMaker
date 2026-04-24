const STORAGE_KEYS = {
  wrongBank: "quizmaker-wrong-bank",
  wrongNotebook: "quizmaker-wrong-notebook",
  settings: "quizmaker-settings",
};

const state = {
  data: null,
  courses: [],
  chapters: [],
  lessons: [],
  lessonMap: new Map(),
  questionMap: new Map(),
  selectedCourses: new Set(),
  selectedChapters: new Set(),
  wrongBank: new Set(),
  wrongNotebook: new Map(),
  session: null,
  mode: "study",
  activeLessonKey: null,
};

const elements = {
  heroTotal: document.querySelector("#hero-total"),
  heroWrongCount: document.querySelector("#hero-wrong-count"),
  heroAccuracy: document.querySelector("#hero-accuracy"),
  modePicker: document.querySelector("#mode-picker"),
  questionCount: document.querySelector("#question-count"),
  shuffleToggle: document.querySelector("#shuffle-toggle"),
  wrongOnlyToggle: document.querySelector("#wrong-only-toggle"),
  lessonSelect: document.querySelector("#lesson-select"),
  openLesson: document.querySelector("#open-lesson"),
  startLessonQuiz: document.querySelector("#start-lesson-quiz"),
  openNotebook: document.querySelector("#open-notebook"),
  courseFilters: document.querySelector("#course-filters"),
  chapterFilters: document.querySelector("#chapter-filters"),
  selectAllCourses: document.querySelector("#select-all-courses"),
  selectAllChapters: document.querySelector("#select-all-chapters"),
  clearAllChapters: document.querySelector("#clear-all-chapters"),
  startQuiz: document.querySelector("#start-quiz"),
  resetStorage: document.querySelector("#reset-storage"),
  loadingView: document.querySelector("#loading-view"),
  emptyView: document.querySelector("#empty-view"),
  welcomeView: document.querySelector("#welcome-view"),
  lessonView: document.querySelector("#lesson-view"),
  quizView: document.querySelector("#quiz-view"),
  resultView: document.querySelector("#result-view"),
  notebookView: document.querySelector("#notebook-view"),
  lessonTitle: document.querySelector("#lesson-title"),
  lessonOverview: document.querySelector("#lesson-overview"),
  lessonMeta: document.querySelector("#lesson-meta"),
  lessonTopicList: document.querySelector("#lesson-topic-list"),
  lessonStartQuiz: document.querySelector("#lesson-start-quiz"),
  lessonOpenNotebook: document.querySelector("#lesson-open-notebook"),
  lessonBackHome: document.querySelector("#lesson-back-home"),
  notebookSummary: document.querySelector("#notebook-summary"),
  notebookList: document.querySelector("#notebook-list"),
  notebookReviewAll: document.querySelector("#notebook-review-all"),
  notebookBackHome: document.querySelector("#notebook-back-home"),
  questionIndex: document.querySelector("#question-index"),
  questionMeta: document.querySelector("#question-meta"),
  scoreCorrect: document.querySelector("#score-correct"),
  scoreWrong: document.querySelector("#score-wrong"),
  progressBar: document.querySelector("#progress-bar"),
  questionBadge: document.querySelector("#question-badge"),
  questionPrompt: document.querySelector("#question-prompt"),
  options: document.querySelector("#options"),
  explanationCard: document.querySelector("#explanation-card"),
  answerPill: document.querySelector("#answer-pill"),
  explanationText: document.querySelector("#explanation-text"),
  sourceChip: document.querySelector("#source-chip"),
  checkAnswer: document.querySelector("#check-answer"),
  nextQuestion: document.querySelector("#next-question"),
  finishQuiz: document.querySelector("#finish-quiz"),
  resultScore: document.querySelector("#result-score"),
  resultSummary: document.querySelector("#result-summary"),
  resultAccuracy: document.querySelector("#result-accuracy"),
  resultWrong: document.querySelector("#result-wrong"),
  resultFilterSummary: document.querySelector("#result-filter-summary"),
  resultCourseBreakdown: document.querySelector("#result-course-breakdown"),
  retryWrong: document.querySelector("#retry-wrong"),
  restartQuiz: document.querySelector("#restart-quiz"),
};

const timeFormatter = new Intl.DateTimeFormat("ko-KR", {
  dateStyle: "medium",
  timeStyle: "short",
});

function readJSONStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function persistSettings() {
  const payload = {
    version: 2,
    mode: state.mode,
    count: elements.questionCount.value,
    shuffle: elements.shuffleToggle.checked,
    wrongOnly: elements.wrongOnlyToggle.checked,
    courses: [...state.selectedCourses],
    chapters: [...state.selectedChapters],
    activeLessonKey: state.activeLessonKey,
  };
  localStorage.setItem(STORAGE_KEYS.settings, JSON.stringify(payload));
}

function renderQuestionCountOptions(totalQuestions) {
  const candidates = [10, 20, 30, 50, 100, 150, 200, 300, 500];
  const saved = readJSONStorage(STORAGE_KEYS.settings, null);
  const preferred = saved?.count || "all";

  elements.questionCount.innerHTML = "";
  for (const count of candidates) {
    if (count >= totalQuestions) continue;
    const option = document.createElement("option");
    option.value = String(count);
    option.textContent = `${count}문항`;
    elements.questionCount.appendChild(option);
  }

  if (totalQuestions > 0) {
    const full = document.createElement("option");
    full.value = String(totalQuestions);
    full.textContent = `${totalQuestions}문항`;
    elements.questionCount.appendChild(full);
  }

  const all = document.createElement("option");
  all.value = "all";
  all.textContent = `전체 문제은행 (${totalQuestions}문항)`;
  elements.questionCount.appendChild(all);

  const validValues = new Set(
    [...elements.questionCount.querySelectorAll("option")].map((option) => option.value),
  );
  const shouldMigrateLegacy100 =
    saved &&
    saved.version !== 2 &&
    saved.count === "100" &&
    totalQuestions > 100;

  elements.questionCount.value =
    shouldMigrateLegacy100
      ? "all"
      : validValues.has(preferred)
        ? preferred
        : "all";
}

function persistWrongState() {
  localStorage.setItem(
    STORAGE_KEYS.wrongBank,
    JSON.stringify([...state.wrongBank].sort((a, b) => a - b)),
  );
  localStorage.setItem(
    STORAGE_KEYS.wrongNotebook,
    JSON.stringify(
      [...state.wrongNotebook.values()].sort((a, b) =>
        String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")),
      ),
    ),
  );
  updateHeroStats();
}

function shuffle(array) {
  const copy = [...array];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function getChapterKey(item) {
  return `${item.course} / ${item.chapter}`;
}

function getVisibleLessons() {
  return state.lessons.filter((lesson) => state.selectedCourses.has(lesson.course));
}

function createCourseModel() {
  const courseMap = new Map();
  const chapterCounts = new Map();

  for (const question of state.data.questions) {
    const chapterKey = getChapterKey(question);
    if (!courseMap.has(question.course)) {
      courseMap.set(question.course, new Set());
    }
    courseMap.get(question.course).add(chapterKey);
    chapterCounts.set(chapterKey, (chapterCounts.get(chapterKey) || 0) + 1);
  }

  state.courses = [...courseMap.keys()];
  state.lessons = (state.data.lessons || []).map((lesson) => ({
    ...lesson,
    key: getChapterKey(lesson),
  }));
  state.lessonMap = new Map(state.lessons.map((lesson) => [lesson.key, lesson]));
  state.questionMap = new Map(state.data.questions.map((question) => [question.id, question]));

  state.chapters = state.data.questions.reduce((acc, question) => {
    const key = getChapterKey(question);
    if (acc.some((entry) => entry.key === key)) return acc;
    const lesson = state.lessonMap.get(key);
    acc.push({
      key,
      course: question.course,
      chapter: question.chapter,
      displayTitle: lesson?.displayTitle || question.chapter,
      questionCount: chapterCounts.get(key) || 0,
    });
    return acc;
  }, []);
}

function restoreSettings() {
  const savedWrongBank = readJSONStorage(STORAGE_KEYS.wrongBank, []);
  state.wrongBank = new Set(
    savedWrongBank.filter((id) => Number.isInteger(id) && state.questionMap.has(id)),
  );

  const notebookRaw = readJSONStorage(STORAGE_KEYS.wrongNotebook, []);
  state.wrongNotebook = new Map();
  for (const record of notebookRaw) {
    if (!record || !Number.isInteger(record.id) || !state.questionMap.has(record.id)) continue;
    state.wrongNotebook.set(record.id, record);
    if (!record.resolved) {
      state.wrongBank.add(record.id);
    }
  }

  const saved = readJSONStorage(STORAGE_KEYS.settings, null);
  state.mode = saved?.mode === "exam" ? "exam" : "study";
  elements.questionCount.value = saved?.count || "100";
  elements.shuffleToggle.checked = saved?.shuffle ?? true;
  elements.wrongOnlyToggle.checked = saved?.wrongOnly ?? false;

  const validCourses = new Set(state.courses);
  state.selectedCourses = new Set(
    (saved?.courses || []).filter((course) => validCourses.has(course)),
  );
  if (state.selectedCourses.size === 0) {
    state.selectedCourses = new Set(state.courses);
  }

  const validChapters = new Set(state.chapters.map((entry) => entry.key));
  state.selectedChapters = new Set(
    (saved?.chapters || []).filter((chapter) => validChapters.has(chapter)),
  );
  if (state.selectedChapters.size === 0) {
    state.selectedChapters = new Set(state.chapters.map((entry) => entry.key));
  }

  const visibleLessons = getVisibleLessons();
  const lessonKeys = new Set(state.lessons.map((lesson) => lesson.key));
  if (saved?.activeLessonKey && lessonKeys.has(saved.activeLessonKey)) {
    state.activeLessonKey = saved.activeLessonKey;
  } else {
    state.activeLessonKey = visibleLessons[0]?.key || state.lessons[0]?.key || null;
  }
}

function updateModeUI() {
  [...elements.modePicker.querySelectorAll(".segment")].forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === state.mode);
  });
}

function updateHeroStats() {
  elements.heroTotal.textContent = state.data ? String(state.data.totalQuestions) : "-";
  elements.heroWrongCount.textContent = String(state.wrongBank.size);

  if (!state.session || state.session.answers.length === 0) {
    elements.heroAccuracy.textContent = "-";
    return;
  }

  const accuracy = Math.round(
    (state.session.correctCount / state.session.answers.length) * 100,
  );
  elements.heroAccuracy.textContent = `${accuracy}%`;
}

function renderCourseFilters() {
  elements.courseFilters.innerHTML = "";
  for (const course of state.courses) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.textContent = course;
    button.classList.toggle("active", state.selectedCourses.has(course));
    button.addEventListener("click", () => {
      if (state.selectedCourses.has(course) && state.selectedCourses.size > 1) {
        state.selectedCourses.delete(course);
      } else {
        state.selectedCourses.add(course);
      }

      const visibleChapterKeys = new Set(
        state.chapters
          .filter((entry) => state.selectedCourses.has(entry.course))
          .map((entry) => entry.key),
      );

      state.selectedChapters = new Set(
        [...state.selectedChapters].filter((key) => visibleChapterKeys.has(key)),
      );

      if (state.selectedChapters.size === 0) {
        state.selectedChapters = visibleChapterKeys;
      }

      const visibleLessons = getVisibleLessons();
      if (!visibleLessons.some((lesson) => lesson.key === state.activeLessonKey)) {
        state.activeLessonKey = visibleLessons[0]?.key || null;
      }

      renderCourseFilters();
      renderChapterFilters();
      renderLessonSelect();
      persistSettings();
    });
    elements.courseFilters.appendChild(button);
  }
}

function renderChapterFilters() {
  const visibleChapters = state.chapters.filter((entry) =>
    state.selectedCourses.has(entry.course),
  );

  elements.chapterFilters.innerHTML = "";
  for (const entry of visibleChapters) {
    const wrapper = document.createElement("div");
    wrapper.className = "chapter-item";

    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selectedChapters.has(entry.key);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        state.selectedChapters.add(entry.key);
      } else {
        state.selectedChapters.delete(entry.key);
      }
      persistSettings();
    });

    const textWrap = document.createElement("div");
    const course = document.createElement("div");
    course.className = "chapter-course";
    course.textContent = entry.course;
    const chapter = document.createElement("div");
    chapter.textContent = entry.chapter;
    const meta = document.createElement("div");
    meta.className = "chapter-meta";
    meta.textContent = `${entry.questionCount}문항`;

    textWrap.append(course, chapter, meta);
    label.append(checkbox, textWrap);
    wrapper.appendChild(label);
    elements.chapterFilters.appendChild(wrapper);
  }
}

function renderLessonSelect() {
  const visibleLessons = getVisibleLessons();
  elements.lessonSelect.innerHTML = "";

  if (visibleLessons.length === 0) {
    const option = document.createElement("option");
    option.textContent = "선택 가능한 챕터가 없습니다.";
    option.value = "";
    elements.lessonSelect.appendChild(option);
    elements.lessonSelect.disabled = true;
    elements.openLesson.disabled = true;
    elements.startLessonQuiz.disabled = true;
    return;
  }

  if (!visibleLessons.some((lesson) => lesson.key === state.activeLessonKey)) {
    state.activeLessonKey = visibleLessons[0].key;
  }

  for (const lesson of visibleLessons) {
    const option = document.createElement("option");
    option.value = lesson.key;
    option.textContent = `${lesson.displayTitle} · ${lesson.questionCount}문항`;
    option.selected = lesson.key === state.activeLessonKey;
    elements.lessonSelect.appendChild(option);
  }

  elements.lessonSelect.disabled = false;
  elements.openLesson.disabled = false;
  elements.startLessonQuiz.disabled = false;
}

function showView(view) {
  for (const section of [
    elements.loadingView,
    elements.emptyView,
    elements.welcomeView,
    elements.lessonView,
    elements.quizView,
    elements.resultView,
    elements.notebookView,
  ]) {
    section.classList.add("hidden");
  }
  view.classList.remove("hidden");
}

function getFilteredQuestions({
  wrongOnly = elements.wrongOnlyToggle.checked,
  chapterKeys = null,
  questionIds = null,
} = {}) {
  const chapterSet = chapterKeys ? new Set(chapterKeys) : null;
  const idSet = questionIds ? new Set(questionIds) : null;

  return state.data.questions.filter((question) => {
    const chapterKey = getChapterKey(question);
    if (idSet && !idSet.has(question.id)) return false;
    if (chapterSet && !chapterSet.has(chapterKey)) return false;

    if (!idSet && !chapterSet) {
      if (!state.selectedCourses.has(question.course)) return false;
      if (!state.selectedChapters.has(chapterKey)) return false;
    }

    if (wrongOnly && !state.wrongBank.has(question.id)) return false;
    return true;
  });
}

function buildSession({
  wrongOnly = elements.wrongOnlyToggle.checked,
  chapterKeys = null,
  questionIds = null,
  useAll = false,
  filterSummary = "",
} = {}) {
  let questions = getFilteredQuestions({ wrongOnly, chapterKeys, questionIds });
  if (questions.length === 0) return null;

  if (elements.shuffleToggle.checked && questions.length > 1) {
    questions = shuffle(questions);
  }

  if (!useAll && elements.questionCount.value !== "all") {
    const count = Number(elements.questionCount.value);
    questions = questions.slice(0, count);
  }

  return {
    questions,
    answers: [],
    index: 0,
    revealed: false,
    selectedChoice: null,
    correctCount: 0,
    wrongCount: 0,
    startedWithWrongOnly: wrongOnly,
    filterSummary,
  };
}

function currentQuestion() {
  return state.session.questions[state.session.index];
}

function renderQuestion() {
  const question = currentQuestion();
  const progress = ((state.session.index + 1) / state.session.questions.length) * 100;

  elements.questionIndex.textContent = `${state.session.index + 1} / ${state.session.questions.length}`;
  elements.questionMeta.textContent = `${question.course} / ${question.chapter}`;
  elements.questionBadge.textContent = `Question ${question.id}`;
  elements.questionPrompt.textContent = question.prompt;
  elements.scoreCorrect.textContent = String(state.session.correctCount);
  elements.scoreWrong.textContent = String(state.session.wrongCount);
  elements.progressBar.style.width = `${progress}%`;

  elements.options.innerHTML = "";
  question.options.forEach((option, index) => {
    const choice = document.createElement("button");
    choice.type = "button";
    choice.className = "choice-button";
    choice.dataset.index = String(index + 1);
    choice.innerHTML = `
      <span class="choice-number">${index + 1}</span>
      <span>${option}</span>
    `;

    choice.classList.toggle("selected", state.session.selectedChoice === index + 1);

    if (state.session.revealed) {
      if (index + 1 === question.answer) {
        choice.classList.add("correct");
      } else if (index + 1 === state.session.selectedChoice) {
        choice.classList.add("wrong");
      }
      choice.disabled = true;
    } else {
      choice.addEventListener("click", () => {
        state.session.selectedChoice = index + 1;
        renderQuestion();
      });
    }

    elements.options.appendChild(choice);
  });

  if (state.session.revealed) {
    elements.explanationCard.classList.remove("hidden");
    elements.answerPill.textContent = `정답 ${question.answer}번`;
    elements.explanationText.textContent = question.explanation;
    elements.sourceChip.textContent = question.source
      ? `근거: ${question.source}`
      : "근거 정보 없음";
    elements.checkAnswer.classList.add("hidden");
    elements.nextQuestion.classList.toggle(
      "hidden",
      state.session.index === state.session.questions.length - 1,
    );
  } else {
    elements.explanationCard.classList.add("hidden");
    elements.checkAnswer.classList.remove("hidden");
    elements.nextQuestion.classList.add("hidden");
  }

  updateHeroStats();
}

function updateWrongNotebook(question, selectedChoice, isCorrect) {
  const now = new Date().toISOString();
  const existing = state.wrongNotebook.get(question.id);

  if (isCorrect) {
    state.wrongBank.delete(question.id);
    if (existing) {
      state.wrongNotebook.set(question.id, {
        ...existing,
        selectedChoice,
        selectedOption: question.options[selectedChoice - 1] || "",
        resolved: true,
        resolvedAt: now,
        updatedAt: now,
        lastResult: "correct",
      });
    }
    persistWrongState();
    return;
  }

  state.wrongBank.add(question.id);
  state.wrongNotebook.set(question.id, {
    id: question.id,
    course: question.course,
    chapter: question.chapter,
    prompt: question.prompt,
    selectedChoice,
    selectedOption: question.options[selectedChoice - 1] || "",
    correctAnswer: question.answer,
    correctOption: question.options[question.answer - 1] || "",
    explanation: question.explanation,
    source: question.source,
    attempts: (existing?.attempts || 0) + 1,
    createdAt: existing?.createdAt || now,
    updatedAt: now,
    resolved: false,
    resolvedAt: null,
    lastResult: "wrong",
  });
  persistWrongState();
}

function gradeCurrentQuestion() {
  if (!state.session || state.session.revealed) return;
  if (state.session.selectedChoice == null) {
    alert("보기 하나를 먼저 선택하세요.");
    return;
  }

  const question = currentQuestion();
  const isCorrect = state.session.selectedChoice === question.answer;

  state.session.answers.push({
    id: question.id,
    course: question.course,
    chapter: question.chapter,
    isCorrect,
  });

  if (isCorrect) {
    state.session.correctCount += 1;
  } else {
    state.session.wrongCount += 1;
  }

  updateWrongNotebook(question, state.session.selectedChoice, isCorrect);
  state.session.revealed = true;
  renderQuestion();
}

function goToNextQuestion() {
  if (!state.session) return;
  if (state.session.index >= state.session.questions.length - 1) {
    finishSession();
    return;
  }

  state.session.index += 1;
  state.session.revealed = false;
  state.session.selectedChoice = null;
  renderQuestion();
}

function renderResults() {
  const total = state.session.questions.length;
  const accuracy = total
    ? Math.round((state.session.correctCount / total) * 100)
    : 0;

  elements.resultScore.textContent = `${state.session.correctCount} / ${total}`;
  elements.resultSummary.textContent =
    state.mode === "exam"
      ? "시험 모드 세션이 종료되었습니다. 과목별 약점을 확인하고 오답을 다시 풀 수 있습니다."
      : "학습 모드 세션이 종료되었습니다. 틀린 문제는 오답노트에 저장되고, 다시 맞힌 문제는 해결됨으로 표시됩니다.";
  elements.resultAccuracy.textContent = `${accuracy}%`;
  elements.resultWrong.textContent = String(state.session.wrongCount);
  elements.resultFilterSummary.textContent = state.session.filterSummary || (
    state.session.startedWithWrongOnly
      ? "오답 보관함 기준"
      : `${state.selectedCourses.size}개 과목 / ${state.selectedChapters.size}개 챕터`
  );

  const breakdown = new Map();
  for (const answer of state.session.answers) {
    if (!breakdown.has(answer.course)) {
      breakdown.set(answer.course, { total: 0, correct: 0 });
    }
    const entry = breakdown.get(answer.course);
    entry.total += 1;
    if (answer.isCorrect) entry.correct += 1;
  }

  elements.resultCourseBreakdown.innerHTML = "";
  for (const [course, summary] of breakdown.entries()) {
    const item = document.createElement("div");
    item.className = "breakdown-item";
    const accuracyLabel = Math.round((summary.correct / summary.total) * 100);
    item.innerHTML = `
      <span>${course}</span>
      <strong>${summary.correct} / ${summary.total} · ${accuracyLabel}%</strong>
    `;
    elements.resultCourseBreakdown.appendChild(item);
  }

  updateHeroStats();
}

function finishSession() {
  if (!state.session) return;
  renderResults();
  showView(elements.resultView);
}

function startSession({
  wrongOnly = elements.wrongOnlyToggle.checked,
  chapterKeys = null,
  questionIds = null,
  useAll = false,
  filterSummary = "",
} = {}) {
  const session = buildSession({
    wrongOnly,
    chapterKeys,
    questionIds,
    useAll,
    filterSummary,
  });
  if (!session) {
    showView(elements.emptyView);
    return;
  }

  state.session = session;
  persistSettings();
  showView(elements.quizView);
  renderQuestion();
}

function renderLessonView() {
  const lesson = state.lessonMap.get(state.activeLessonKey);
  if (!lesson) {
    showView(elements.emptyView);
    return;
  }

  elements.lessonSelect.value = lesson.key;
  elements.lessonTitle.textContent = lesson.displayTitle;
  elements.lessonOverview.textContent = lesson.overview;

  elements.lessonMeta.innerHTML = "";
  for (const text of [
    lesson.course,
    `핵심 개념 ${lesson.topics.length}개`,
    `관련 문제 ${lesson.questionCount}문항`,
    lesson.source ? `출처 ${lesson.source}` : "",
  ]) {
    if (!text) continue;
    const badge = document.createElement("div");
    badge.className = "lesson-meta-chip";
    badge.textContent = text;
    elements.lessonMeta.appendChild(badge);
  }

  elements.lessonTopicList.innerHTML = "";
  for (const topic of lesson.topics) {
    const card = document.createElement("article");
    card.className = "lesson-topic-card";

    const head = document.createElement("div");
    head.className = "lesson-topic-head";

    const title = document.createElement("h3");
    title.textContent = topic.title;
    head.appendChild(title);

    if (topic.page) {
      const page = document.createElement("span");
      page.className = "topic-page";
      page.textContent = `PDF ${topic.page}p`;
      head.appendChild(page);
    }

    const summary = document.createElement("p");
    summary.textContent = topic.summary;

    card.append(head, summary);
    elements.lessonTopicList.appendChild(card);
  }

  showView(elements.lessonView);
}

function formatTimestamp(value) {
  if (!value) return "";
  try {
    return timeFormatter.format(new Date(value));
  } catch {
    return "";
  }
}

function renderNotebookView() {
  const records = [...state.wrongNotebook.values()].sort((a, b) => {
    if (a.resolved !== b.resolved) return a.resolved ? 1 : -1;
    return String(b.updatedAt || "").localeCompare(String(a.updatedAt || ""));
  });

  const unresolvedCount = records.filter((record) => !record.resolved).length;
  const resolvedCount = records.length - unresolvedCount;

  elements.notebookSummary.innerHTML = "";
  for (const text of [
    `미해결 ${unresolvedCount}`,
    `해결됨 ${resolvedCount}`,
    `누적 ${records.length}`,
  ]) {
    const badge = document.createElement("div");
    badge.className = "lesson-meta-chip";
    badge.textContent = text;
    elements.notebookSummary.appendChild(badge);
  }

  elements.notebookList.innerHTML = "";
  if (records.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-note";
    empty.textContent = "아직 저장된 오답이 없습니다. 문제를 풀면서 틀린 항목이 여기에 누적됩니다.";
    elements.notebookList.appendChild(empty);
    showView(elements.notebookView);
    return;
  }

  for (const record of records) {
    const card = document.createElement("article");
    card.className = "notebook-card";

    const top = document.createElement("div");
    top.className = "notebook-card-top";

    const status = document.createElement("span");
    status.className = `notebook-status ${record.resolved ? "resolved" : "active"}`;
    status.textContent = record.resolved ? "해결됨" : "미해결";

    const meta = document.createElement("div");
    meta.className = "notebook-card-meta";
    meta.textContent = `${record.course} / ${record.chapter} · ${formatTimestamp(record.updatedAt)}`;

    top.append(status, meta);

    const title = document.createElement("h3");
    title.textContent = record.prompt;

    const answer = document.createElement("p");
    answer.className = "notebook-copy";
    answer.textContent = `내 답 ${record.selectedChoice}번 · 정답 ${record.correctAnswer}번`;

    const detail = document.createElement("p");
    detail.className = "notebook-copy";
    detail.textContent = `오답 이유: ${record.explanation}`;

    const aux = document.createElement("p");
    aux.className = "notebook-aux";
    aux.textContent = `시도 ${record.attempts || 1}회${record.source ? ` · 근거 ${record.source}` : ""}`;

    const actions = document.createElement("div");
    actions.className = "quiz-actions";

    const retryButton = document.createElement("button");
    retryButton.type = "button";
    retryButton.className = "secondary-button";
    retryButton.textContent = "이 문제 다시 풀기";
    retryButton.addEventListener("click", () => {
      startSession({
        questionIds: [record.id],
        useAll: true,
        filterSummary: "오답노트 단일 문제",
      });
    });

    const conceptButton = document.createElement("button");
    conceptButton.type = "button";
    conceptButton.className = "ghost-button";
    conceptButton.textContent = "관련 개념 보기";
    conceptButton.addEventListener("click", () => {
      state.activeLessonKey = getChapterKey(record);
      persistSettings();
      renderLessonView();
    });

    actions.append(retryButton, conceptButton);
    card.append(top, title, answer, detail, aux, actions);
    elements.notebookList.appendChild(card);
  }

  showView(elements.notebookView);
}

function startLessonQuiz() {
  const lesson = state.lessonMap.get(state.activeLessonKey);
  if (!lesson) {
    alert("먼저 학습할 챕터를 선택하세요.");
    return;
  }

  startSession({
    questionIds: lesson.questionIds,
    useAll: true,
    filterSummary: `${lesson.displayTitle} 관련 문제`,
  });
}

function attachEvents() {
  elements.modePicker.addEventListener("click", (event) => {
    const button = event.target.closest("[data-mode]");
    if (!button) return;
    state.mode = button.dataset.mode;
    updateModeUI();
    persistSettings();
  });

  elements.lessonSelect.addEventListener("change", () => {
    state.activeLessonKey = elements.lessonSelect.value;
    persistSettings();
  });

  elements.openLesson.addEventListener("click", () => {
    state.activeLessonKey = elements.lessonSelect.value;
    persistSettings();
    renderLessonView();
  });

  elements.startLessonQuiz.addEventListener("click", () => {
    state.activeLessonKey = elements.lessonSelect.value;
    persistSettings();
    startLessonQuiz();
  });

  elements.openNotebook.addEventListener("click", renderNotebookView);
  elements.lessonStartQuiz.addEventListener("click", startLessonQuiz);
  elements.lessonOpenNotebook.addEventListener("click", renderNotebookView);
  elements.lessonBackHome.addEventListener("click", () => {
    state.session = null;
    updateHeroStats();
    showView(elements.welcomeView);
  });

  elements.notebookReviewAll.addEventListener("click", () => {
    if (state.wrongBank.size === 0) {
      alert("현재 미해결 오답이 없습니다.");
      return;
    }
    elements.wrongOnlyToggle.checked = true;
    startSession({
      wrongOnly: true,
      useAll: true,
      filterSummary: "오답노트 전체 복습",
    });
  });

  elements.notebookBackHome.addEventListener("click", () => {
    state.session = null;
    updateHeroStats();
    showView(elements.welcomeView);
  });

  elements.selectAllCourses.addEventListener("click", () => {
    state.selectedCourses = new Set(state.courses);
    state.selectedChapters = new Set(state.chapters.map((entry) => entry.key));
    if (!state.activeLessonKey) {
      state.activeLessonKey = state.lessons[0]?.key || null;
    }
    renderCourseFilters();
    renderChapterFilters();
    renderLessonSelect();
    persistSettings();
  });

  elements.selectAllChapters.addEventListener("click", () => {
    const visible = state.chapters
      .filter((entry) => state.selectedCourses.has(entry.course))
      .map((entry) => entry.key);
    state.selectedChapters = new Set(visible);
    renderChapterFilters();
    persistSettings();
  });

  elements.clearAllChapters.addEventListener("click", () => {
    state.selectedChapters.clear();
    renderChapterFilters();
    persistSettings();
  });

  elements.startQuiz.addEventListener("click", () => startSession());
  elements.checkAnswer.addEventListener("click", gradeCurrentQuestion);
  elements.nextQuestion.addEventListener("click", goToNextQuestion);
  elements.finishQuiz.addEventListener("click", finishSession);

  elements.retryWrong.addEventListener("click", () => {
    if (state.wrongBank.size === 0) {
      alert("현재 미해결 오답이 없습니다.");
      return;
    }
    elements.wrongOnlyToggle.checked = true;
    startSession({
      wrongOnly: true,
      useAll: true,
      filterSummary: "오답 보관함 기준",
    });
  });

  elements.restartQuiz.addEventListener("click", () => {
    state.session = null;
    updateHeroStats();
    showView(elements.welcomeView);
  });

  elements.resetStorage.addEventListener("click", () => {
    state.wrongBank.clear();
    state.wrongNotebook.clear();
    persistWrongState();
    elements.wrongOnlyToggle.checked = false;
    renderNotebookView();
    alert("오답 기록과 오답노트를 비웠습니다.");
  });

  elements.questionCount.addEventListener("change", persistSettings);
  elements.shuffleToggle.addEventListener("change", persistSettings);
  elements.wrongOnlyToggle.addEventListener("change", persistSettings);

  document.addEventListener("keydown", (event) => {
    if (!state.session || elements.quizView.classList.contains("hidden")) return;

    if (!state.session.revealed && /^[1-4]$/.test(event.key)) {
      state.session.selectedChoice = Number(event.key);
      renderQuestion();
    }

    if (event.key === "Enter") {
      if (!state.session.revealed) {
        gradeCurrentQuestion();
      } else {
        goToNextQuestion();
      }
    }
  });
}

async function init() {
  attachEvents();

  try {
    const response = await fetch("./data/questions.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Failed to fetch data: ${response.status}`);
    }

    state.data = await response.json();
    createCourseModel();
    renderQuestionCountOptions(state.data.totalQuestions);
    restoreSettings();
    updateModeUI();
    renderCourseFilters();
    renderChapterFilters();
    renderLessonSelect();
    updateHeroStats();
    showView(elements.welcomeView);
  } catch (error) {
    console.error(error);
    elements.loadingView.innerHTML = `
      <p class="loading-title">데이터를 읽지 못했습니다.</p>
      <p class="loading-copy">docs/data/questions.json 파일이 있는지 확인하세요.</p>
    `;
    showView(elements.loadingView);
  }
}

init();
