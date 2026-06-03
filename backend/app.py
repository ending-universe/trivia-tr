from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import html
import time
import os
import random
from deep_translator import GoogleTranslator

app = Flask(__name__)
CORS(app)

OPENTDB_BASE = "https://opentdb.com/api.php"
OPENTDB_CATEGORIES = "https://opentdb.com/api_category.php"

# ── Cache ─────────────────────────────────────────────────────
_cache = {}
_cache_enabled = True

def cache_get(key):
    if not _cache_enabled: return None
    entry = _cache.get(key)
    if not entry: return None
    if time.time() > entry["expires"]:
        del _cache[key]; return None
    return entry["value"]

def cache_set(key, value, ttl=86400):
    if not _cache_enabled: return
    _cache[key] = {"value": value, "expires": time.time() + ttl}

def cache_stats():
    now = time.time()
    valid = sum(1 for e in _cache.values() if now <= e["expires"])
    return {"enabled": _cache_enabled, "total": len(_cache), "valid": valid, "expired": len(_cache) - valid}

# ── Translation ───────────────────────────────────────────────
def translate_batch(texts):
    if not texts: return []
    translator = GoogleTranslator(source="en", target="tr")
    results = []
    for text in texts:
        try:
            t = translator.translate(text)
            results.append(t or text)
        except Exception as e:
            print(f"[translate] failed: {e}")
            results.append(text)
        time.sleep(0.15)
    return results

# ── Routes ────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")})

@app.route("/api/categories")
def categories():
    cached = cache_get("categories")
    if cached: return jsonify({"success": True, "categories": cached})
    try:
        data = requests.get(OPENTDB_CATEGORIES, timeout=10).json()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    raw_cats = data.get("trivia_categories", [])
    names = [c["name"] for c in raw_cats]
    tr_names = translate_batch(names)
    result = [{"id": c["id"], "name": tr_names[i], "nameOriginal": c["name"]} for i, c in enumerate(raw_cats)]
    cache_set("categories", result, ttl=7*86400)
    return jsonify({"success": True, "categories": result})

@app.route("/api/questions")
def questions():
    amount   = max(5, min(30, int(request.args.get("amount", 10))))
    category = request.args.get("category", "")
    difficulty = request.args.get("difficulty", "")
    q_type   = request.args.get("type", "mixed")

    cache_key = f"q:{amount}:{category}:{difficulty}:{q_type}"
    cached = cache_get(cache_key)
    if cached: return jsonify({"success": True, "count": len(cached), "questions": cached})

    # Fetch raw questions
    fetched_raw = []
    if q_type == "mixed":
        half = amount // 2
        for t, n in [("multiple", half), ("boolean", amount - half)]:
            p = {"amount": n, "type": t}
            if category: p["category"] = category
            if difficulty: p["difficulty"] = difficulty
            try:
                d = requests.get(OPENTDB_BASE, params=p, timeout=10).json()
                if d.get("response_code") == 0:
                    fetched_raw.extend(d["results"])
            except Exception as e:
                print(f"[fetch] {t} failed: {e}")
        random.shuffle(fetched_raw)
    else:
        p = {"amount": amount, "type": q_type}
        if category: p["category"] = category
        if difficulty: p["difficulty"] = difficulty
        try:
            d = requests.get(OPENTDB_BASE, params=p, timeout=10).json()
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        if d.get("response_code") != 0:
            return jsonify({"error": f"OpenTDB error {d.get('response_code')}"}), 400
        fetched_raw = d["results"]

    # Decode
    raw = [{
        "type": q["type"],
        "category": html.unescape(q["category"]),
        "difficulty": q["difficulty"],
        "question": html.unescape(q["question"]),
        "correct": html.unescape(q["correct_answer"]),
        "incorrect": [html.unescape(a) for a in q["incorrect_answers"]],
    } for q in fetched_raw]

    # Translate only questions + multiple-choice answers (not True/False)
    texts_to_translate = []
    for q in raw:
        texts_to_translate.append(q["question"])
        if q["type"] == "multiple":
            texts_to_translate.append(q["correct"])
            texts_to_translate.extend(q["incorrect"])

    translated = translate_batch(texts_to_translate)

    # Re-map
    idx = 0
    questions_out = []
    for q in raw:
        t_question = translated[idx]; idx += 1
        if q["type"] == "boolean":
            questions_out.append({
                "type": "boolean",
                "question": t_question,
                "questionOriginal": q["question"],
                "correctAnswer": q["correct"],          # "True" / "False"
                "answers": ["True", "False"],
                "difficulty": q["difficulty"],
                "category": q["category"],
            })
        else:
            t_correct = translated[idx]; idx += 1
            t_incorrect = [translated[idx + j] for j in range(len(q["incorrect"]))]
            idx += len(q["incorrect"])
            answers = t_incorrect + [t_correct]
            random.shuffle(answers)
            questions_out.append({
                "type": "multiple",
                "question": t_question,
                "questionOriginal": q["question"],
                "correctAnswer": t_correct,
                "correctAnswerOriginal": q["correct"],
                "answers": answers,
                "answersOriginal": {t_incorrect[i]: q["incorrect"][i] for i in range(len(t_incorrect))} | {t_correct: q["correct"]},
                "difficulty": q["difficulty"],
                "category": q["category"],
            })

    cache_set(cache_key, questions_out)
    return jsonify({"success": True, "count": len(questions_out), "questions": questions_out})

# ── Settings ─────────────────────────────────────────────────
@app.route("/api/settings")
def get_settings():
    return jsonify({"cache": cache_stats()})

@app.route("/api/settings/cache", methods=["POST"])
def toggle_cache():
    global _cache_enabled
    body = request.get_json()
    if not isinstance(body.get("enabled"), bool):
        return jsonify({"error": "'enabled' must be boolean"}), 400
    _cache_enabled = body["enabled"]
    if not _cache_enabled: _cache.clear()
    return jsonify({"success": True, "cache": cache_stats()})

@app.route("/api/settings/cache", methods=["DELETE"])
def clear_cache():
    _cache.clear()
    return jsonify({"success": True, "cache": cache_stats()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 4000)), debug=False)
