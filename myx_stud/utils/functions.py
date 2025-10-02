import google.generativeai as genai
import re

SCORE_THRESHOLD = 0.8  # ggf. anpassen


def get_gemini_feedback(text, question, user_answer, correct_answer, feedback_prompt):
    """
    Ruft Gemini auf und liefert:
      {"feedback": <str>, "score": <float|None>, "error": <optional str>}
    Parser erwartet Antwort im Format:
        FEEDBACK: ...
        SCORE: 0.87
    und ist tolerant bzgl. Komma/Dezimalpunkt, zusätzlichem Text etc.
    """
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""
        Du bist ein Tutor und gibst konstruktives, kurzes Feedback. 
        Der Schüler darf seine Antwort nach deinem Feedback überarbeiten.

        Aufgabentext: {text}
        Frage: {question}
        Antwort des Schülers: {user_answer}
        Hinweis auf die korrekte Antwort: {correct_answer}

        Erstelle dein Feedback nach diesen Vorgaben: {feedback_prompt}

        Zusätzlich: Schätze die Korrektheit der Schüler-Antwort als Score zwischen 0 und 1:
        - 1.0 = vollkommen korrekt
        - 0.0 = völlig falsch
        - dazwischen = teilweise korrekt

        Antworte AUSSCHLIESSLICH in genau diesem Format (ohne Zusatztext davor/danach):

        FEEDBACK: <dein kurzer Feedbacktext>
        SCORE: <Zahl zwischen 0 und 1>
        """.strip()

    def _clamp_score(x):
        try:
            v = float(x)
        except (TypeError, ValueError):
            return None
        if v < 0.0:
            v = 0.0
        if v > 1.0:
            v = 1.0
        return v

    try:
        response = model.generate_content(prompt)

        # Text robust extrahieren
        text_out = (getattr(response, "text", None) or "").strip()
        if not text_out and getattr(response, "candidates", None):
            parts = []
            for p in getattr(response.candidates[0].content, "parts", []):
                t = getattr(p, "text", None)
                if t:
                    parts.append(t)
            text_out = "\n".join(parts).strip()

        # FEEDBACK:
        fb_match = re.search(r"FEEDBACK:\s*(.*?)(?=SCORE:|$)", text_out, re.S | re.IGNORECASE)
        feedback = (fb_match.group(1).strip() if fb_match else "") or "Feedback konnte nicht extrahiert werden."

        # SCORE:
        score_match = re.search(r"SCORE:\s*([-+]?\d*[\.,]?\d+)", text_out, re.IGNORECASE)
        score = None
        if score_match:
            raw = score_match.group(1).replace(",", ".")
            score = _clamp_score(raw)

        return {"feedback": feedback, "score": score}

    except Exception as e:
        return {"feedback": "We had trouble generating feedback. Try again later.", "score": None, "error": str(e)}


def get_feedback_unified(current_question, user_answer):
    """
    Einheitliches Rückgabeformat:
      - Bei Gemini (gemini_feedback=True):
          { "is_correct": bool|None, "feedback_ai": str, "score": float|None }
        (KEIN 'correct_answer' Key)
      - Ohne Gemini:
          { "is_correct": bool, "correct_answer": str, "feedback_ai": None, "score": 0.0|1.0 }
    """
    use_gemini = bool(getattr(current_question, "gemini_feedback", False))

    if use_gemini:
        fb = get_gemini_feedback(
            getattr(current_question, "text", "") or "",
            getattr(current_question, "question", "") or "",
            user_answer or "",
            getattr(current_question, "correct_answer", "") or "",
            getattr(current_question, "feedback_prompt", "") or "",
        )

        score = fb.get("score")
        is_correct = None if score is None else (score > SCORE_THRESHOLD)

        return {
            "is_correct": is_correct,
            "feedback_ai": fb.get("feedback") or "",
            "score": score
            # bewusst KEIN 'correct_answer'
        }

    # --- Fallback (exakter Vergleich) ---
    ua = (user_answer or "").strip().lower()
    ca = (getattr(current_question, "correct_answer", "") or "").strip().lower()
    is_correct = (ua == ca)

    return {
        "is_correct": is_correct,
        "correct_answer": getattr(current_question, "correct_answer", "") or "",
        "feedback_ai": None,
        "score": 1.0 if is_correct else 0.0,
    }