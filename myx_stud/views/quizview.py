import uuid
from datetime import datetime

from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404, render
from django.utils import timezone

from ..models import QuizQuestion, QuestionLog, Kurse
from ..utils.functions import get_feedback_unified


SESSION_KURS_KEY = "current_kurs_id"
SESSION_KONZEPT_KEY = "current_konzept_id"
SESSION_QUIZ_ID = "quiz_run_id"


# =========================
# Session-Bucket Helpers
# =========================

def _session_key(quiz_id, item_id):
    """Key für die Session-Zwischenspeicher pro (Quizlauf, Item)."""
    return f"qlog_{quiz_id}_{item_id}"


def _append_attempt_to_session(request, quiz_id, item_id, attempt):
    """Versuch im Session-Bucket ablegen; nummerieren + Zeit stempeln."""
    key = _session_key(quiz_id, item_id)
    bucket = request.session.get(key, [])
    attempt_no = len(bucket) + 1
    attempt = {
        "n": attempt_no,
        "submitted_at": timezone.now().isoformat(),
        **attempt,
    }
    bucket.append(attempt)
    request.session[key] = bucket
    request.session.modified = True


def _set_rating_on_last_attempt(request, quiz_id, item_id, rating_int):
    """Rating auf den letzten Versuch setzen (nur in der Session)."""
    key = _session_key(quiz_id, item_id)
    bucket = request.session.get(key, [])
    if bucket:
        bucket[-1]["rating"] = rating_int
        request.session[key] = bucket
        request.session.modified = True


def _started_key(quiz_id, item_id):
    return f"{_session_key(quiz_id, item_id)}_created_at"


def _set_created_at_once(request, quiz_id, item_id):
    """Setzt die Startzeit nur einmal beim ersten Anzeigen des Items."""
    skey = _started_key(quiz_id, item_id)
    if not request.session.get(skey):
        request.session[skey] = timezone.now().isoformat()
        request.session.modified = True


def _pop_created_at(request, quiz_id, item_id):
    """Liest die Startzeit aus der Session und entfernt sie danach."""
    skey = _started_key(quiz_id, item_id)
    iso = request.session.pop(skey, None)
    if iso:
        try:
            dt = datetime.fromisoformat(iso)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
        except Exception:
            return timezone.now()
    return None


def _flush_session_to_questionlog(request, quiz_id, item_id, meta):
    """
    Persistiert ALLE Versuche aus der Session in QuestionLog.attempts (JSON-Liste).
    Speichert EIN finales Rating (vom letzten Versuch) in item_rating.
    Erwartet in meta: session_id, fach, kurs, konzept, text, image (str/None),
                      question, correct_answer, feedback_prompt, gemini_feedback (bool)
    """
    key = _session_key(quiz_id, item_id)
    bucket = request.session.get(key, [])

    # nichts zu persistieren → Startzeit ggf. aufräumen und raus
    if not bucket:
        _pop_created_at(request, quiz_id, item_id)
        if key in request.session:
            del request.session[key]
            request.session.modified = True
        return

    started_at = _pop_created_at(request, quiz_id, item_id)

    last = bucket[-1] if bucket else None
    final_rating = last.get("rating") if last else None
    try:
        final_rating = int(final_rating)
        if not (1 <= final_rating <= 5):
            final_rating = None
    except (TypeError, ValueError):
        final_rating = None

    # Normierung / Fallbacks
    normalized_attempts = []
    for idx, a in enumerate(bucket, start=1):
        normalized_attempts.append({
            "n": a.get("n") or idx,
            "answer": a.get("answer", ""),
            "feedback": a.get("feedback_text", ""),
            "correct_answer": a.get("correct_answer", ""),
            "is_correct": bool(a.get("is_correct", False)),
            "score": float(a.get("score", 0.0) or 0.0),
            "submitted_at": a.get("submitted_at"),
        })

    # Ein Create mit JSON-Liste
    QuestionLog.objects.create(
        session_id=meta["session_id"],
        quiz_id=quiz_id,
        item_id=item_id,

        fach=meta.get("fach", ""),
        kurs=meta.get("kurs", ""),
        konzept=meta.get("konzept", ""),

        text=meta.get("text", ""),
        question=meta.get("question", ""),
        correct_answer=meta.get("correct_answer", ""),
        gemini_feedback=bool(meta.get("gemini_feedback", False)),
        feedback_prompt=meta.get("feedback_prompt", ""),

        started_at=started_at,
        attempts=normalized_attempts,
        item_rating=final_rating,
    )

    # Session-Bucket leeren
    if key in request.session:
        del request.session[key]
        request.session.modified = True


# =========================
# Eigentliche Quiz-View
# =========================

def quiz_view(request):
    # Kurs aus der Session holen
    kurs_id = request.session.get(SESSION_KURS_KEY)
    if not kurs_id:
        messages.info(request, "Bitte zuerst einen Kurs auswählen.")
        return redirect("kurswahl")
    

    # Run/Progress initialisieren (fach/kurs NICHT mehr in Session nötig)
    if request.session.get('quiz_index') is None:
        request.session['quiz_index'] = 0
        request.session['score_sum'] = 0.0
        request.session['items_scored'] = 0
        request.session.modified = True

    quiz_id = request.session.get(SESSION_QUIZ_ID)
    if not quiz_id:
        quiz_id = uuid.uuid4().hex
        request.session[SESSION_QUIZ_ID] = quiz_id
        request.session.modified = True

    # Fragen zum Kurs laden
    # === NEU: Erst versuchen, über KONZEPT zu filtern ===
    konzept_id = request.session.get(SESSION_KONZEPT_KEY)
    if konzept_id:
        questions_qs = QuizQuestion.objects.filter(
            active=True,
            konzept_id=konzept_id
        ).order_by('id')
    else:
        # Fallback: alle Fragen des Kurses
        questions_qs = QuizQuestion.objects.filter(
            active=True,
            konzept__kurs_id=kurs_id
        ).order_by('id')

    questions = list(questions_qs)

    # Prüfen ob Fragen da
    total_questions = len(questions)
    if total_questions == 0:
        messages.warning(request, "Für diesen Kurs sind noch keine aktiven Fragen hinterlegt.")
        return redirect('kurs')

    current_index = request.session.get('quiz_index', 0)
    if current_index >= total_questions:
        return redirect('quiz_complete')

    current_question = questions[current_index]

    # Session-ID sicherstellen
    if not request.session.session_key:
        request.session.create()
    session_id = request.session.session_key

    item_id = str(current_question.item_id)
    feedback = None
    user_answer = ""
    ask_rating = False

    # Start der Aufgabe stempeln (nur einmal je Item)
    if request.method == 'GET':
        _set_created_at_once(request, quiz_id, item_id)

    if request.method == 'POST':
        rating_str = request.POST.get("rating")
        rating_int = int(rating_str) if rating_str and rating_str.isdigit() else None

        # 👉 NEXT gedrückt
        if 'next' in request.POST:
            key = _session_key(quiz_id, item_id)
            bucket = request.session.get(key, [])
            last = bucket[-1] if bucket else None

            # Kein Rating abgegeben, aber erforderlich → Sterne anzeigen
            if last and last.get("rating") is None and rating_int is None:
                ask_rating = True
                context = {
                    'question': current_question,
                    'feedback': None,
                    'user_answer': user_answer,
                    'index': current_index + 1,
                    'total': total_questions,
                    'ask_rating': ask_rating,
                }
                return render(request, 'quiz/quiz_view.html', context)

            # Rating jetzt gesetzt → auf letzten Versuch schreiben
            if last and last.get("rating") is None and rating_int is not None:
                _set_rating_on_last_attempt(request, quiz_id, item_id, rating_int)

            # Score aggregieren (nur wenn es überhaupt einen Versuch gab)
            if bucket:
                try:
                    last_score = float((last or {}).get("score", 0.0) or 0.0)
                except (TypeError, ValueError):
                    last_score = 0.0
                request.session['score_sum'] = float(request.session.get('score_sum', 0.0)) + last_score
                request.session['items_scored'] = int(request.session.get('items_scored', 0)) + 1
                request.session.modified = True

            # Metadaten fürs Log (aus Kurs/Konzept/Fraag)
            kurs_obj = current_question.konzept.kurs
            meta = {
                "session_id": session_id,
                "fach": kurs_obj.fach,
                "kurs": kurs_obj.kurs,
                "konzept": (current_question.konzept.name or ""),
                "text": current_question.text,
                # nur Dateiname/Path speichern (string) oder None
                "image": (current_question.image.name if current_question.image else None),
                "question": current_question.question,
                "correct_answer": current_question.correct_answer,
                "feedback_prompt": getattr(current_question, "feedback_prompt", "") or "",
                "gemini_feedback": bool(getattr(current_question, "gemini_feedback", False)),
            }
            _flush_session_to_questionlog(request, quiz_id, item_id, meta)

            # nächste Frage
            request.session['quiz_index'] = current_index + 1
            request.session.modified = True
            return redirect('quiz_view')

        # 👉 ABSENDEN: Antwort bewerten & Versuch (ohne Rating) in Session ablegen
        user_answer = (request.POST.get('answer') or '').strip()
        fb = get_feedback_unified(current_question, user_answer)

        score_val = fb.get("score")
        try:
            score_val = float(score_val)
        except (TypeError, ValueError):
            score_val = 0.0
        score_val = min(max(score_val, 0.0), 1.0)

        is_correct = fb.get("is_correct")
        if is_correct is None:
            is_correct = (score_val > 0.8)

        if is_correct is True:
            request.session['correct_count'] = request.session.get('correct_count', 0) + 1
            request.session.modified = True

        _append_attempt_to_session(request, quiz_id, item_id, {
            "answer": user_answer,
            "feedback_text": fb.get("feedback_ai", "") or "",
            "correct_answer": fb.get("correct_answer") or "",
            "is_correct": bool(is_correct),
            "score": float(score_val),
            "rating": None,  # Rating kommt erst im NEXT-Flow
        })

        feedback = fb

    # Render
    context = {
        'question': current_question,
        'feedback': feedback,
        'user_answer': user_answer,
        'index': current_index + 1,
        'total': total_questions,
        'ask_rating': ask_rating,
    }
    return render(request, 'quiz/quiz_view.html', context)
