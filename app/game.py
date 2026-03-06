"""
Chinese Room experiment game logic.

The player is inside the room. They receive Chinese messages and must
construct responses using a rulebook of symbol-matching patterns,
without understanding the meaning.
"""

import random

# Each rule maps an input pattern to an output pattern.
# The player sees these as abstract symbol-matching cards.
RULEBOOKS = {
    "greetings": {
        "name": "Greetings & Pleasantries",
        "rules": [
            {"id": "g1", "input": "你好", "output": "你好！很高兴认识你。", "hint": "Two-char greeting → warm reply"},
            {"id": "g2", "input": "你好吗", "output": "我很好，谢谢你！", "hint": "Three-char question → positive response"},
            {"id": "g3", "input": "早上好", "output": "早上好！今天天气不错。", "hint": "Morning pattern → morning + weather"},
            {"id": "g4", "input": "晚上好", "output": "晚上好！今天过得怎么样？", "hint": "Evening pattern → evening + question"},
            {"id": "g5", "input": "再见", "output": "再见，下次再聊！", "hint": "Farewell → farewell + next time"},
            {"id": "g6", "input": "谢谢", "output": "不客气！", "hint": "Thanks → you're welcome"},
        ],
    },
    "questions": {
        "name": "Simple Questions",
        "rules": [
            {"id": "q1", "input": "你叫什么名字", "output": "我叫小明。", "hint": "Name question → name answer"},
            {"id": "q2", "input": "你几岁", "output": "我二十五岁。", "hint": "Age question → age answer"},
            {"id": "q3", "input": "你喜欢什么", "output": "我喜欢读书和音乐。", "hint": "Like-what → hobbies"},
            {"id": "q4", "input": "你在哪里", "output": "我在房间里。", "hint": "Where question → in the room"},
            {"id": "q5", "input": "今天星期几", "output": "今天是星期三。", "hint": "Day question → weekday"},
            {"id": "q6", "input": "现在几点", "output": "现在下午三点。", "hint": "Time question → afternoon"},
        ],
    },
    "feelings": {
        "name": "Emotions & Feelings",
        "rules": [
            {"id": "f1", "input": "你开心吗", "output": "是的，我很开心！", "hint": "Happy question → yes happy"},
            {"id": "f2", "input": "你累吗", "output": "有一点累，但还好。", "hint": "Tired question → a little"},
            {"id": "f3", "input": "你饿吗", "output": "有点饿，想吃东西。", "hint": "Hungry question → want food"},
            {"id": "f4", "input": "你喜欢这里吗", "output": "喜欢，这里很好。", "hint": "Like-here → yes, nice"},
            {"id": "f5", "input": "你无聊吗", "output": "不无聊，我在学习。", "hint": "Bored question → no, studying"},
            {"id": "f6", "input": "你害怕吗", "output": "不害怕，一切都好。", "hint": "Afraid question → no, all good"},
        ],
    },
}

# Difficulty controls how many distractor characters appear in the grid
DIFFICULTY_SETTINGS = {
    "easy": {"grid_cols": 6, "distractors": 4, "time_limit": 60, "max_rules": 3},
    "medium": {"grid_cols": 8, "distractors": 10, "time_limit": 45, "max_rules": 5},
    "hard": {"grid_cols": 10, "distractors": 18, "time_limit": 30, "max_rules": 6},
}

# Common Chinese characters used as distractors
DISTRACTOR_POOL = list(
    "的一是不了人我在有他这中大来上个国到说们为子和你地出会也时要就"
    "可以对生能而都行方面看头经主实家公同工已想利回年走进成长天水发如"
    "体现被高正老因它手机去法当啊用道着动两然但问心前开那情里多没自"
)


def get_rulebook(category: str) -> dict:
    return RULEBOOKS.get(category, RULEBOOKS["greetings"])


def generate_round(category: str, difficulty: str) -> dict:
    """Generate a single game round."""
    settings = DIFFICULTY_SETTINGS.get(difficulty, DIFFICULTY_SETTINGS["easy"])
    rulebook = get_rulebook(category)
    rules = rulebook["rules"][: settings["max_rules"]]

    # Pick one rule as the "active" one for this round
    active_rule = random.choice(rules)

    # Build the character grid: correct answer chars + distractors
    answer_chars = list(active_rule["output"])
    distractor_chars = random.sample(
        [c for c in DISTRACTOR_POOL if c not in answer_chars],
        min(settings["distractors"], len(DISTRACTOR_POOL)),
    )

    grid_chars = answer_chars + distractor_chars
    random.shuffle(grid_chars)

    # Pad grid to fill rows evenly
    cols = settings["grid_cols"]
    while len(grid_chars) % cols != 0:
        extra = random.choice(DISTRACTOR_POOL)
        if extra not in grid_chars:
            grid_chars.append(extra)
        else:
            grid_chars.append(random.choice(DISTRACTOR_POOL))

    return {
        "incoming_message": active_rule["input"],
        "active_rule_id": active_rule["id"],
        "rules": [
            {"id": r["id"], "input": r["input"], "output": r["output"], "hint": r["hint"]}
            for r in rules
        ],
        "grid": grid_chars,
        "grid_cols": cols,
        "expected_answer": active_rule["output"],
        "time_limit": settings["time_limit"],
    }


def check_answer(expected: str, player_answer: str) -> dict:
    """Check the player's constructed answer against the expected one."""
    # Strip whitespace for comparison
    clean_expected = expected.replace(" ", "")
    clean_answer = player_answer.replace(" ", "")

    if clean_answer == clean_expected:
        return {"correct": True, "score": 100, "message": "Perfect match! The symbols align exactly."}

    # Partial credit: check character overlap
    expected_chars = list(clean_expected)
    answer_chars = list(clean_answer)

    correct_positions = sum(
        1 for a, e in zip(answer_chars, expected_chars) if a == e
    )
    max_len = max(len(expected_chars), len(answer_chars), 1)
    similarity = correct_positions / max_len

    if similarity >= 0.8:
        return {"correct": False, "score": int(similarity * 80), "message": "Close! Most symbols matched."}
    elif similarity >= 0.5:
        return {"correct": False, "score": int(similarity * 50), "message": "Partial match. Review the rulebook more carefully."}
    else:
        return {"correct": False, "score": 0, "message": "The symbols don't match. Try following the rule pattern."}


# System prompt for the LLM playing the Chinese speaker
LLM_SYSTEM_PROMPT = """You are a Chinese speaker having a simple conversation.
You are testing whether the person you're talking to understands Chinese.
Keep your messages SHORT (under 10 characters when possible).
Use simple, everyday Chinese. Start with greetings, then ask basic questions.
Only respond in Chinese characters. No pinyin, no English.
If the response you receive seems unnatural, note it but continue the conversation.
After each exchange, internally rate the response 1-5 for naturalness."""


def build_llm_prompt(conversation_history: list[dict]) -> list[dict]:
    """Build the message list for the Ollama API."""
    messages = [{"role": "system", "content": LLM_SYSTEM_PROMPT}]
    messages.extend(conversation_history)
    return messages
