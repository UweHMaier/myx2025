import uuid
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404, render
from ..models import QuizQuestion, QuestionLog, Kurse 
from django.utils import timezone
from ..utils.functions import get_feedback_unified
from datetime import datetime

SESSION_KURS_KEY = "current_kurs_id"
SESSION_QUIZ_ID = "quiz_run_id"

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
    Speichert GENAU EIN Rating (vom letzten Versuch) in item_rating.
    Erwartet in meta: session_id, topic, goal, text, image, question, correct_answer,
                      feedback_prompt, gemini_feedback (bool)
    """
    key = _session_key(quiz_id, item_id)
    bucket = request.session.get(key, [])

    # Startzeit vom ersten Anzeigen (kann None sein)
    started_at = _pop_created_at(request, quiz_id, item_id)

    # Letzter Versuch & finales Rating ableiten
    last = bucket[-1] if bucket else None
    final_rating = last.get("rating") if last else None
    # sauber auf int casten (1..5), sonst None
    try:
        final_rating = int(final_rating)
        if not (1 <= final_rating <= 5):
            final_rating = None
    except (TypeError, ValueError):
        final_rating = None

    def attempt(i):
        return bucket[i] if i < len(bucket) else {}

    att1, att2, att3 = attempt(0), attempt(1), attempt(2)

    # Ein einziger Create-Call reicht – leere Strings/None sind okay
    QuestionLog.objects.create(
        session_id=meta["session_id"],
        quiz_id=quiz_id,
        item_id=item_id,
        fach=meta.get("fach", "Default text"),
        kurs=meta.get("kurs", "Default text"),
        level=meta.get("level", "Default text"),
        text=meta.get("text", ""),
        image=meta.get("image"),
        question=meta.get("question", ""),
        correct_answer=meta.get("correct_answer", ""),
        gemini_feedback=meta.get("gemini_feedback", False),
        feedback_prompt=meta.get("feedback_prompt", ""),

        # Versuche (Texte)
        stud_answ1=att1.get("answer", ""),
        feedback1=att1.get("feedback_text", ""),

        stud_answ2=att2.get("answer", ""),
        feedback2=att2.get("feedback_text", ""),

        stud_answ3=att3.get("answer", ""),
        feedback3=att3.get("feedback_text", ""),

        # Zeiten & EIN finales Rating
        # HINWEIS: Dein Model braucht started_at + item_rating Felder!
        started_at=started_at,       # models.DateTimeField(null=True, blank=True)
        item_rating=final_rating,    # models.IntegerField(null=True, blank=True)
    )

    # Bucket leeren
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




# --- Eigentliche Quiz View --- 

def quiz_view(request):


    # Kurs aus der Session holen
    kurs_id = request.session.get(SESSION_KURS_KEY)
    if not kurs_id:
        messages.info(request, "Bitte zuerst einen Kurs auswählen.")
        return redirect("kurswahl")
    
    # quiz_fach/quiz_kurs einmalig aus Kurse setzen (und Run initialisieren)
    if not request.session.get('quiz_fach') or not request.session.get('quiz_kurs'):
        k = get_object_or_404(Kurse, id=kurs_id)
        request.session['quiz_fach'] = k.fach
        request.session['quiz_kurs'] = k.kurs
        request.session['quiz_index'] = 0
        request.session['score_sum'] = 0.0
        request.session['items_scored'] = 0
        request.session[SESSION_QUIZ_ID] = uuid.uuid4().hex
        request.session.modified = True

    fach = request.session.get('quiz_fach')
    kurs = request.session.get('quiz_kurs')

    questions = list(
        QuizQuestion.objects.filter(
            active=True,
            fach=fach,
            kurs=kurs
        ).order_by('id')
    )

    total_questions = len(questions)
    if total_questions == 0:
        messages.warning(request, "Für diesen Kurs sind noch keine aktiven Fragen hinterlegt.")
        return redirect('kurs')
    current_index = request.session.get('quiz_index', 0)

    if current_index >= total_questions:
        return redirect('quiz_complete')

    current_question = questions[current_index]
    feedback = None
    user_answer = ''
    ask_rating = False   # <— NEU: steuert, ob die Sterne angezeigt werden

    # IDs bereitstellen (Session-ID sicherstellen)
    if not request.session.session_key:
        request.session.create()
    session_id = request.session.session_key  # SessionID = Browser-Sitzung

    quiz_id = request.session.get(SESSION_QUIZ_ID)  # QuizID = Run-UUID
    if not quiz_id:
        quiz_id = uuid.uuid4().hex
        request.session[SESSION_QUIZ_ID] = quiz_id

    item_id = str(current_question.item_id)

    # Start der Aufgabe stempeln (nur einmal je Item)
    if request.method == 'GET':
        _set_created_at_once(request, quiz_id, item_id)

    if request.method == 'POST':
        rating_str = request.POST.get("rating")
        rating_int = int(rating_str) if rating_str and rating_str.isdigit() else None

        # 👉 NÄCHSTE FRAGE: Session -> ggf. Rating einfordern -> DB & weiter
        if 'next' in request.POST:
            key = _session_key(quiz_id, item_id)
            bucket = request.session.get(key, [])
            last = bucket[-1] if bucket else None

            # 1) Es gibt einen Versuch, aber noch KEIN Rating und jetzt kommt auch keins → Rating erfragen
            if last and last.get("rating") is None and rating_int is None:
                ask_rating = True
                # Seite NICHT verlassen, sondern Sterne anzeigen
                context = {
                    'question': current_question,
                    'feedback': None,            # i.d.R. gerade fertig, Feedback schon gesehen
                    'user_answer': user_answer,
                    'index': current_index + 1,
                    'total': total_questions,
                    'ask_rating': ask_rating,    # <— Template schaltet Sterne sichtbar
                }
                return render(request, 'quiz/quiz_view.html', context)

            # 2) Es gibt einen Versuch ohne Rating und jetzt kommt eins → EINMALIG setzen
            if last and last.get("rating") is None and rating_int is not None:
                _set_rating_on_last_attempt(request, quiz_id, item_id, rating_int)

            # 3) Score aufsummieren, aber nur wenn es überhaupt einen Versuch gab
            if bucket:
                try:
                    last_score = float((last or {}).get("score", 0.0) or 0.0)
                except (TypeError, ValueError):
                    last_score = 0.0
                request.session['score_sum'] = float(request.session.get('score_sum', 0.0)) + last_score
                request.session['items_scored'] = int(request.session.get('items_scored', 0)) + 1
                request.session.modified = True

            # 4) Persistieren & weiter
            meta = {
                "session_id": session_id,
                "fach": current_question.fach,
                "kurs": current_question.kurs,
                "level": getattr(current_question, "level", ""),
                "text": current_question.text,
                "image": current_question.image,
                "question": current_question.question,
                "correct_answer": current_question.correct_answer,
                "feedback_prompt": getattr(current_question, "feedback_prompt", "") or "",
                "gemini_feedback": bool(getattr(current_question, "gemini_feedback", False)),
            }
            _flush_session_to_questionlog(request, quiz_id, item_id, meta)

            request.session['quiz_index'] = current_index + 1
            return redirect('quiz_view')

        # 👉 ABSENDEN: Feedback berechnen & Versuch in Session speichern
        # WICHTIG: HIER KEIN RATING SPEICHERN!
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

        _append_attempt_to_session(request, quiz_id, item_id, {
            "answer": user_answer,
            "feedback_text": fb.get("feedback_ai", "") or "",
            "correct_answer": fb.get("correct_answer") or "",
            "is_correct": is_correct,
            "score": float(score_val),
            "rating": None,   # <— explizit leer lassen; Rating kommt NUR im NEXT-Flow
        })

        feedback = fb

    context = {
        'question': current_question,
        'feedback': feedback,
        'user_answer': user_answer,
        'index': current_index + 1,
        'total': total_questions,
        'ask_rating': ask_rating,   # <— ins Template geben
    }
    return render(request, 'quiz/quiz_view.html', context)

