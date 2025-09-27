import uuid
from django.shortcuts import render, redirect, HttpResponse
from .models import QuizQuestion, QuestionLog
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .utils.functions import get_feedback_unified
from datetime import datetime


# -------- Session-Bucket Helpers --------

def _session_key(quiz_id, item_id):
    """Key für die Session-Zwischenspeicher pro (Quizlauf, Item)."""
    return f"qlog_{quiz_id}_{item_id}"

def _append_attempt_to_session(request, quiz_id, item_id, attempt):
    key = _session_key(quiz_id, item_id)
    bucket = request.session.get(key, [])
    bucket.append(attempt)
    request.session[key] = bucket
    request.session.modified = True

def _set_rating_on_last_attempt(request, quiz_id, item_id, rating_int):
    key = _session_key(quiz_id, item_id)
    bucket = request.session.get(key, [])
    if bucket:
        bucket[-1]["rating"] = rating_int
        request.session[key] = bucket
        request.session.modified = True

def _flush_session_to_questionlog(request, quiz_id, item_id, meta):
    """
    Persistiert bis zu 3 Versuche aus der Session in QuestionLog.
    Legt auch einen Minimal-Datensatz an, wenn kein Versuch vorhanden ist.
    Erwartet in meta: session_id, topic, goal, text, image, question, correct_answer,
                      feedback_prompt, gemini_feedback (bool)
    """
    key = _session_key(quiz_id, item_id)
    bucket = request.session.get(key, [])

    created_at = _pop_created_at(request, quiz_id, item_id)
    
    # Minimal-Log, wenn kein Versuch existiert (z. B. nur 'Next' gedrückt)
    if not bucket:
        QuestionLog.objects.create(
            session_id = meta["session_id"],        # Django-Session-Key
            quiz_id    = quiz_id,                   # 👈 Lauf-spezifische UUID
            item_id    = item_id,
            topic = meta.get("topic","Default text"),
            goal = meta.get("goal","Default text"),
            text = meta.get("text",""),
            image = meta.get("image"),
            question = meta.get("question",""),
            correct_answer = meta.get("correct_answer",""),
            gemini_feedback = meta.get("gemini_feedback", False),
            feedback_prompt = meta.get("feedback_prompt",""),
            stud_answ1 = "", feedback1 = "", feedback1_rating = None,
            stud_answ2 = "", feedback2 = "", feedback2_rating = None,
            stud_answ3 = "", feedback3 = "", feedback3_rating = None,
            # ⬇️ NEU:
            created_at = created_at,
        )
        if key in request.session:
            del request.session[key]
            request.session.modified = True
        return

    # Sicherer Zugriff auf bis zu 3 Versuche
    def attempt(i): 
        return bucket[i] if i < len(bucket) else {}
    att1, att2, att3 = attempt(0), attempt(1), attempt(2)

    QuestionLog.objects.create(
        session_id = meta["session_id"],           # Django-Session-Key
        quiz_id    = quiz_id,                      # 👈 Lauf-spezifische UUID
        item_id    = item_id,
        topic = meta.get("topic","Default text"),
        goal = meta.get("goal","Default text"),
        text = meta.get("text",""),
        image = meta.get("image"),
        question = meta.get("question",""),
        correct_answer = meta.get("correct_answer",""),
        gemini_feedback = meta.get("gemini_feedback", False),
        feedback_prompt = meta.get("feedback_prompt",""),

        stud_answ1 = att1.get("answer",""),
        feedback1  = att1.get("feedback_text",""),
        feedback1_rating = att1.get("rating"),

        stud_answ2 = att2.get("answer",""),
        feedback2  = att2.get("feedback_text",""),
        feedback2_rating = att2.get("rating"),

        stud_answ3 = att3.get("answer",""),
        feedback3  = att3.get("feedback_text",""),
        feedback3_rating = att3.get("rating"),
        # ⬇️ NEU:
        created_at = created_at,
    )

    # Bucket löschen
    if key in request.session:
        del request.session[key]
        request.session.modified = True


def _started_key(quiz_id, item_id):
    # separater Key neben dem Bucket
    return f"{_session_key(quiz_id, item_id)}_created_at"

def _set_created_at_once(request, quiz_id, item_id):
    """Setzt created_at nur, wenn noch nicht vorhanden (beim ersten Anzeigen der Aufgabe)."""
    skey = _started_key(quiz_id, item_id)
    if not request.session.get(skey):
        request.session[skey] = timezone.now().isoformat()
        request.session.modified = True

def _pop_created_at(request, quiz_id, item_id):
    """Liest created_at aus der Session und entfernt ihn danach."""
    skey = _started_key(quiz_id, item_id)
    iso = request.session.pop(skey, None)
    if iso:
        # robust nach datetime konvertieren (aware bevorzugt)
        try:
            dt = datetime.fromisoformat(iso)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
        except Exception:
            return timezone.now()  # Fallback
    return None


# -------- Views --------

def home(request):
    return render (request, "home.html")


def get_goals_for_topic(request):
    topic = request.GET.get('topic')
    goals = QuizQuestion.objects.filter(
        active=True,
        topic=topic
    ).values_list('goal', flat=True).distinct()
    return JsonResponse({'goals': list(goals)})

def quiz_start(request):
    topics = QuizQuestion.objects.filter(active=True).values_list('topic', flat=True).distinct()
    goals = QuizQuestion.objects.filter(active=True).values_list('goal', flat=True).distinct()

    if request.method == 'POST':
        selected_topic = request.POST.get('topic')
        selected_goal = request.POST.get('goal')

        quiz_exists = QuizQuestion.objects.filter(
            active=True,
            topic=selected_topic,
            goal=selected_goal
        ).exists()

        if not quiz_exists:
            return render(request, 'quiz/quiz_start.html', {
                'topics': topics,
                'goals': goals,
                'error': 'No quiz items found for the selected topic and goal.',
                'selected_topic': selected_topic,
                'selected_goal': selected_goal,
            })

        # 👇 NEU: pro Quiz-Durchlauf eine frische UUID erzeugen und in Session ablegen
        request.session['quiz_run_id'] = uuid.uuid4().hex

        # Startdaten in Session
        request.session['quiz_topic'] = selected_topic
        request.session['quiz_goal'] = selected_goal
        request.session['quiz_index'] = 0
        request.session['correct_count'] = 0

        return redirect('quiz_view')

    return render(request, 'quiz/quiz_start.html', {
        'topics': topics,
        'goals': goals,
    })



def quiz_view(request):
    topic = request.session.get('quiz_topic')
    goal = request.session.get('quiz_goal')

    questions = list(
        QuizQuestion.objects.filter(
            active=True,
            topic=topic,
            goal=goal
        ).order_by('id')
    )
    total_questions = len(questions)
    current_index = request.session.get('quiz_index', 0)

    if current_index >= total_questions:
        return redirect('quiz_complete')

    current_question = questions[current_index]
    feedback = None
    user_answer = ''

    # 👉 IDs bereitstellen
    session_id = request.session.session_key or request.session.cycle_key()  # SessionID = Browser-Sitzung
    quiz_id = request.session.get('quiz_run_id')                             # QuizID = Run-UUID
    if not quiz_id:
        # Fallback: sollte nicht passieren, aber zur Sicherheit
        quiz_id = uuid.uuid4().hex
        request.session['quiz_run_id'] = quiz_id

    item_id = str(current_question.id)

    # ⬇️ HIER: Start der Aufgabe stempeln (nur einmal je Item)
    if request.method == 'GET':
        _set_created_at_once(request, quiz_id, item_id)
    # ⬆️

    if request.method == 'POST':
        rating_str = request.POST.get("rating")
        rating_int = int(rating_str) if rating_str and rating_str.isdigit() else None

        # 👉 NÄCHSTE FRAGE: Session -> DB & weiter
        if 'next' in request.POST:
            if rating_int is not None:
                _set_rating_on_last_attempt(request, quiz_id, item_id, rating_int)

            meta = {
                "session_id": session_id,
                "topic": current_question.topic,
                "goal": current_question.goal,
                "text": current_question.text,
                "image": current_question.image,       # File/None
                "question": current_question.question,
                "correct_answer": current_question.correct_answer,
                "feedback_prompt": getattr(current_question, "feedback_prompt", "") or "",
                "gemini_feedback": bool(getattr(current_question, "gemini_feedback", False)),
            }
            _flush_session_to_questionlog(request, quiz_id, item_id, meta)

            request.session['quiz_index'] = current_index + 1
            return redirect('quiz_view')

        # 👉 ABSENDEN: Feedback berechnen & Versuch in Session speichern
        user_answer = (request.POST.get('answer') or '').strip()
        fb = get_feedback_unified(current_question, user_answer)

        if fb["is_correct"] is True:
            request.session['correct_count'] = request.session.get('correct_count', 0) + 1

        _append_attempt_to_session(request, quiz_id, item_id, {
            "answer": user_answer,
            "feedback_text": fb.get("feedback_ai", "") or "",
            "correct_answer": fb.get("correct_answer", "") or "",
            "is_correct": fb.get("is_correct"),
            "rating": rating_int,
        })

        feedback = fb

    context = {
        'question': current_question,
        'feedback': feedback,
        'user_answer': user_answer,
        'index': current_index + 1,
        'total': total_questions,
    }
    return render(request, 'quiz/quiz_view.html', context)


def quiz_complete(request):
    correct = request.session.get('correct_count', 0)
    topic = request.session.get('quiz_topic')
    goal = request.session.get('quiz_goal')

    total = QuizQuestion.objects.filter(
        active=True,
        topic=topic,
        goal=goal
    ).count()

    # Optionally reset Fortschritt
    request.session['quiz_index'] = 0
    request.session['correct_count'] = 0

    return render(request, 'quiz/quiz_complete.html', {
        'correct': correct,
        'total': total,
        'topic': topic,
        'goal': goal,
    })
