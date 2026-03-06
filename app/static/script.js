const API = '';
let state = {
    sessionId: null,
    answer: [],
    score: 0,
    round: 1,
    timer: null,
    timeLeft: 0,
    conversationLog: [],
    mode: 'rulebook',
};

// DOM refs
const screens = {
    menu: document.getElementById('menu-screen'),
    game: document.getElementById('game-screen'),
};

// --- Screen management ---
function showScreen(name) {
    Object.values(screens).forEach(s => s.classList.remove('active'));
    screens[name].classList.add('active');
}

// --- Menu ---
async function initMenu() {
    try {
        const resp = await fetch(`${API}/api/config`);
        const config = await resp.json();

        const catSelect = document.getElementById('category-select');
        catSelect.innerHTML = '';
        for (const [key, name] of Object.entries(config.categories)) {
            const opt = document.createElement('option');
            opt.value = key;
            opt.textContent = name;
            catSelect.appendChild(opt);
        }

        const diffSelect = document.getElementById('difficulty-select');
        diffSelect.innerHTML = '';
        for (const d of config.difficulties) {
            const opt = document.createElement('option');
            opt.value = d;
            opt.textContent = d.charAt(0).toUpperCase() + d.slice(1);
            diffSelect.appendChild(opt);
        }
    } catch (e) {
        console.error('Failed to load config:', e);
    }
}

// --- Start game (rulebook mode) ---
async function startRulebookGame() {
    const category = document.getElementById('category-select').value;
    const difficulty = document.getElementById('difficulty-select').value;

    try {
        const resp = await fetch(`${API}/api/game/new`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category, difficulty }),
        });
        const data = await resp.json();

        state.sessionId = data.session_id;
        state.round = data.round;
        state.score = 0;
        state.answer = [];
        state.mode = 'rulebook';
        state.conversationLog = [];

        renderGame(data);
        showScreen('game');
    } catch (e) {
        alert('Failed to start game: ' + e.message);
    }
}

// --- Start game (LLM mode) ---
async function startLLMGame() {
    const category = document.getElementById('category-select').value;
    const difficulty = document.getElementById('difficulty-select').value;

    const loadingEl = document.getElementById('llm-loading');
    loadingEl.style.display = 'block';

    try {
        const resp = await fetch(`${API}/api/llm/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category, difficulty }),
        });
        const data = await resp.json();

        state.sessionId = data.session_id;
        state.round = 1;
        state.score = 0;
        state.answer = [];
        state.mode = 'llm';
        state.conversationLog = [{ role: 'outside', text: data.llm_message }];

        renderGame({
            incoming_message: data.llm_message,
            rules: data.rules,
            grid: data.grid,
            grid_cols: data.grid_cols,
            time_limit: data.time_limit,
            round: 1,
        });
        showScreen('game');
    } catch (e) {
        alert('Failed to connect to LLM. Is Ollama running? ' + e.message);
    } finally {
        loadingEl.style.display = 'none';
    }
}

// --- Render game state ---
function renderGame(data) {
    // Mode badge
    const modeBadge = document.getElementById('mode-badge');
    modeBadge.textContent = state.mode === 'llm' ? 'LLM Mode' : 'Rulebook Mode';
    modeBadge.className = `mode-badge ${state.mode === 'llm' ? 'llm-mode' : 'rulebook-mode'}`;

    // Status bar
    document.getElementById('score-display').textContent = state.score;
    document.getElementById('round-display').textContent = state.round;

    // Incoming message
    document.getElementById('incoming-msg').textContent = data.incoming_message;

    // Rulebook
    const rulebookEl = document.getElementById('rulebook-rules');
    rulebookEl.innerHTML = '';
    data.rules.forEach(rule => {
        const card = document.createElement('div');
        card.className = 'rule-card';
        card.dataset.ruleId = rule.id;
        card.innerHTML = `
            <div class="rule-input">${rule.input}</div>
            <div class="rule-arrow">--- maps to ---</div>
            <div class="rule-output">${rule.output}</div>
            <div class="rule-hint">${rule.hint}</div>
        `;
        card.addEventListener('click', () => selectRule(card, rule));
        rulebookEl.appendChild(card);
    });

    // Character grid
    const gridEl = document.getElementById('char-grid');
    gridEl.innerHTML = '';
    gridEl.style.gridTemplateColumns = `repeat(${data.grid_cols}, 48px)`;

    data.grid.forEach((char, idx) => {
        const cell = document.createElement('div');
        cell.className = 'char-cell';
        cell.textContent = char;
        cell.dataset.idx = idx;
        cell.addEventListener('click', () => pickChar(char, cell));
        gridEl.appendChild(cell);
    });

    // Clear answer
    state.answer = [];
    renderAnswer();

    // Timer
    startTimer(data.time_limit);

    // Hide feedback
    document.getElementById('feedback').classList.remove('active');

    // Render conversation log
    renderConversation();
}

function selectRule(cardEl, rule) {
    document.querySelectorAll('.rule-card').forEach(c => c.classList.remove('selected'));
    cardEl.classList.add('selected');
}

function pickChar(char, cellEl) {
    state.answer.push(char);
    cellEl.classList.add('picked');
    renderAnswer();
}

function removeAnswerChar(index) {
    state.answer.splice(index, 1);
    renderAnswer();
    // Reset grid picked states based on current answer
    resetGridHighlights();
}

function resetGridHighlights() {
    const remaining = [...state.answer];
    document.querySelectorAll('.char-cell').forEach(cell => {
        cell.classList.remove('picked');
    });
    // Re-mark cells that are still in the answer
    document.querySelectorAll('.char-cell').forEach(cell => {
        const idx = remaining.indexOf(cell.textContent);
        if (idx !== -1) {
            cell.classList.add('picked');
            remaining.splice(idx, 1);
        }
    });
}

function clearAnswer() {
    state.answer = [];
    renderAnswer();
    document.querySelectorAll('.char-cell').forEach(c => c.classList.remove('picked'));
}

function renderAnswer() {
    const slotsEl = document.getElementById('answer-slots');
    slotsEl.innerHTML = '';
    state.answer.forEach((char, idx) => {
        const el = document.createElement('div');
        el.className = 'answer-char';
        el.textContent = char;
        el.addEventListener('click', () => removeAnswerChar(idx));
        slotsEl.appendChild(el);
    });
}

// --- Timer ---
function startTimer(seconds) {
    if (state.timer) clearInterval(state.timer);
    state.timeLeft = seconds;
    updateTimerDisplay();

    state.timer = setInterval(() => {
        state.timeLeft--;
        updateTimerDisplay();
        if (state.timeLeft <= 0) {
            clearInterval(state.timer);
            submitAnswer(); // Auto-submit on timeout
        }
    }, 1000);
}

function updateTimerDisplay() {
    const el = document.getElementById('timer-display');
    el.textContent = state.timeLeft;
    el.style.color = state.timeLeft <= 10 ? '#e74c3c' : '#c8d6e5';
}

// --- Submit answer ---
async function submitAnswer() {
    if (state.timer) clearInterval(state.timer);

    const answer = state.answer.join('');

    if (state.mode === 'rulebook') {
        await submitRulebookAnswer(answer);
    } else {
        await submitLLMAnswer(answer);
    }
}

async function submitRulebookAnswer(answer) {
    try {
        const resp = await fetch(`${API}/api/game/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.sessionId, answer }),
        });
        const data = await resp.json();

        state.score = data.total_score;
        state.round = data.round;

        // Add to conversation log
        const incomingMsg = document.getElementById('incoming-msg').textContent;
        state.conversationLog.push({ role: 'outside', text: incomingMsg });
        state.conversationLog.push({ role: 'you', text: answer });

        showFeedback(data.result, data.expected_answer, () => {
            renderGame({
                incoming_message: data.incoming_message,
                rules: data.rules,
                grid: data.grid,
                grid_cols: data.grid_cols,
                time_limit: data.time_limit,
            });
        });
    } catch (e) {
        alert('Error submitting answer: ' + e.message);
    }
}

async function submitLLMAnswer(answer) {
    if (!answer) return;

    state.conversationLog.push({ role: 'you', text: answer });
    renderConversation();

    try {
        const resp = await fetch(`${API}/api/game/freemode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.sessionId, message: answer }),
        });
        const data = await resp.json();

        state.conversationLog.push({ role: 'outside', text: data.reply });
        state.round++;

        // Generate a new round for the grid/rules based on the new LLM message
        const newRound = await fetch(`${API}/api/game/new`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                category: document.getElementById('category-select').value,
                difficulty: document.getElementById('difficulty-select').value,
            }),
        });
        const roundData = await newRound.json();

        // Keep the same session but update the display
        renderGame({
            incoming_message: data.reply,
            rules: roundData.rules,
            grid: roundData.grid,
            grid_cols: roundData.grid_cols,
            time_limit: roundData.time_limit,
        });
    } catch (e) {
        alert('LLM error: ' + e.message);
    }
}

// --- Feedback ---
function showFeedback(result, expected, onContinue) {
    const el = document.getElementById('feedback');
    el.classList.add('active');
    el.className = `feedback active ${result.correct ? 'correct' : 'incorrect'}`;

    document.getElementById('feedback-icon').textContent = result.correct ? '+' : 'X';
    document.getElementById('feedback-msg').textContent = result.message;
    document.getElementById('feedback-score').textContent = `+${result.score} points`;
    document.getElementById('feedback-expected').innerHTML =
        `Expected: <span>${expected}</span>`;

    const btn = document.getElementById('feedback-continue');
    btn.onclick = () => {
        el.classList.remove('active');
        onContinue();
    };
}

// --- Conversation log ---
function renderConversation() {
    const el = document.getElementById('conversation-log');
    el.innerHTML = '';
    state.conversationLog.forEach(msg => {
        const div = document.createElement('div');
        div.className = 'conv-msg';
        div.innerHTML = `
            <div class="conv-role ${msg.role}">${msg.role === 'outside' ? 'Outside the Room' : 'Your Response'}</div>
            <div>${msg.text}</div>
        `;
        el.appendChild(div);
    });
    el.scrollTop = el.scrollHeight;
}

// --- Back to menu ---
function backToMenu() {
    if (state.timer) clearInterval(state.timer);
    showScreen('menu');
}

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    initMenu();
    showScreen('menu');
});
