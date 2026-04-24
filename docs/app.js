const STORAGE_KEYS = {
  wrongBank: "quizmaker-wrong-bank",
  settings: "quizmaker-settings",
};

const state = {
  data: null,
  courses: [],
  chapters: [],
  selectedCourses: new Set(),
  selectedChapters: new Set(),
  wrongBank: new Set(),
  session: null,
  mode: "study",
};

const elements = {
  heroTotal: document.querySelector("#hero-total"),
  heroWrongCount: document.querySelector("#hero-wrong-count"),
  heroAccuracy: document.querySelector("#hero-accuracy"),
  modePicker: document.querySelector("#mode-picker"),
  questionCount: document.querySelector("#question-count"),
  shuffleToggle: document.querySelector("#shuffle-toggle"),
  wrongOnlyToggle: document.querySelector("#wrong-only-toggle"),
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
  quizView: document.querySelector("#quiz-view"),
  resultView: document.querySelector("#result-view"),
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
    mode: state.mode,
    count: elements.questionCount.value,
    shuffle: elements.shuffleToggle.checked,
    wrongOnly: elements.wrongOnlyToggle.checked,
    courses: [...state.selectedCourses],
    chapters: [...state.selectedChapters],
  };
  localStorage.setItem(STORAGE_KEYS.settings, JSON.stringify(payload));
}

function persistWrongBank() {
  localStorage.setItem(
    STORAGE_KEYS.wrongBank,
    JSON.stringify([...state.wrongBank].sort((a, b) => a - b)),
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

function getChapterKey(question) {
  return `${question.course} / ${question.chapter}`;
}

function createCourseModel() {
  const courseMap = new Map();
  for (const question of state.data.questions) {
    if (!courseMap.has(question.course)) {
      courseMap.set(question.course, new Set());
    }
    courseMap.get(question.course).add(getChapterKey(question));
  }
  state.courses = [...courseMap.keys()];
  state.chapters = state.data.questions.reduce((acc, question) => {
    const key = getChapterKey(question);
    if (acc.some((entry) => entry.key === key)) return acc;
    acc.push({
      key,
      course: question.course,
      chapter: question.chapter,
    });
    return acc;
  }, []);
}

function restoreSettings() {
  state.wrongBank = new Set(readJSONStorage(STORAGE_KEYS.wrongBank, []));

  const saved = readJSONStorage(STORAGE_KEYS.settings, null);
  if (!saved) {
    state.mode = "study";
    state.selectedCourses = new Set(state.courses);
    state.selectedChapters = new Set(state.chapters.map((entry) => entry.key));
    return;
  }

  state.mode = saved.mode === "exam" ? "exam" : "study";
  elements.questionCount.value = saved.count || "100";
  elements.shuffleToggle.checked = saved.shuffle ?? true;
  elements.wrongOnlyToggle.checked = saved.wrongOnly ?? false;

  const validCourses = new Set(state.courses);
  state.selectedCourses = new Set(
    (saved.courses || []).filter((course) => validCourses.has(course)),
  );
  if (state.selectedCourses.size === 0) {
    state.selectedCourses = new Set(state.courses);
  }

  const validChapters = new Set(state.chapters.map((entry) => entry.key));
  state.selectedChapters = new Set(
    (saved.chapters || []).filter((chapter) => validChapters.has(chapter)),
  );
  if (state.selectedChapters.size === 0) {
    state.selectedChapters = new Set(state.chapters.map((entry) => entry.key));
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

      renderCourseFilters();
      renderChapterFilters();
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

    textWrap.append(course, chapter);
    label.append(checkbox, textWrap);
    wrapper.appendChild(label);
    elements.chapterFilters.appendChild(wrapper);
  }
}

function showView(view) {
  for (const section of [
    elements.loadingView,
    elements.emptyView,
    elements.welcomeView,
    elements.quizView,
    elements.resultView,
  ]) {
    section.classList.add("hidden");
  }
  view.classList.remove("hidden");
}

function getFilteredQuestions({ wrongOnly = elements.wrongOnlyToggle.checked } = {}) {
  return state.data.questions.filter((question) => {
    const chapterKey = getChapterKey(question);
    if (!state.selectedCourses.has(question.course)) return false;
    if (!state.selectedChapters.has(chapterKey)) return false;
    if (wrongOnly && !state.wrongBank.has(question.id)) return false;
    return true;
  });
}

function buildSession({ wrongOnly = elements.wrongOnlyToggle.checked } = {}) {
  let questions = getFilteredQuestions({ wrongOnly });
  if (questions.length === 0) return null;

  if (elements.shuffleToggle.checked) {
    questions = shuffle(questions);
  }

  const countValue = elements.questionCount.value;
  if (countValue !== "all") {
    const count = Number(countValue);
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
    state.wrongBank.delete(question.id);
  } else {
    state.session.wrongCount += 1;
    state.wrongBank.add(question.id);
  }

  persistWrongBank();
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
      ? "시험 모드 세션이 종료되었습니다. 과목별 약점을 확인하고 오답만 다시 풀 수 있습니다."
      : "학습 모드 세션이 종료되었습니다. 해설을 확인한 문제들을 기반으로 오답 보관함이 갱신되었습니다.";
  elements.resultAccuracy.textContent = `${accuracy}%`;
  elements.resultWrong.textContent = String(state.session.wrongCount);
  elements.resultFilterSummary.textContent = state.session.startedWithWrongOnly
    ? "오답 보관함 기준"
    : `${state.selectedCourses.size}개 과목 / ${state.selectedChapters.size}개 챕터`;

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

function startSession({ wrongOnly = elements.wrongOnlyToggle.checked } = {}) {
  const session = buildSession({ wrongOnly });
  if (!session) {
    showView(elements.emptyView);
    return;
  }

  state.session = session;
  persistSettings();
  showView(elements.quizView);
  renderQuestion();
}

function attachEvents() {
  elements.modePicker.addEventListener("click", (event) => {
    const button = event.target.closest("[data-mode]");
    if (!button) return;
    state.mode = button.dataset.mode;
    updateModeUI();
    persistSettings();
  });

  elements.selectAllCourses.addEventListener("click", () => {
    state.selectedCourses = new Set(state.courses);
    state.selectedChapters = new Set(state.chapters.map((entry) => entry.key));
    renderCourseFilters();
    renderChapterFilters();
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
    elements.wrongOnlyToggle.checked = true;
    startSession({ wrongOnly: true });
  });

  elements.restartQuiz.addEventListener("click", () => {
    state.session = null;
    updateHeroStats();
    showView(elements.welcomeView);
  });

  elements.resetStorage.addEventListener("click", () => {
    state.wrongBank.clear();
    persistWrongBank();
    elements.wrongOnlyToggle.checked = false;
    alert("오답 기록을 비웠습니다.");
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
    restoreSettings();
    updateModeUI();
    renderCourseFilters();
    renderChapterFilters();
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
