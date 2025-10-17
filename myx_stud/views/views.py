from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from ..models import QuizQuestion, Kurse, Konzepte
from django.http import JsonResponse


SESSION_KURS_KEY = "current_kurs_id"
SESSION_KONZEPT_KEY = "current_konzept_id"
SESSION_QUIZ_ID  = "quiz_run_id"   # konsistent benutzen



def home(request):
    return render (request, "home.html")



def get_kurse_for_fach(request):
    """AJAX: gibt Kursnamen zu einem Fach zurück (für das Dropdown)."""
    fach = (request.GET.get("fach") or "").strip()
    if not fach:
        return JsonResponse({"kurse": []})

    kurse = (Kurse.objects
             .filter(fach=fach)
             .values_list("kurs", flat=True)
             .order_by("kurs")
             .distinct())

    return JsonResponse({"kurse": list(kurse)})


def kurswahl(request):
    """Fach/Kurs auswählen. POST setzt Kurs in Session und leert alten Quiz-Run."""
    if request.method == "POST":
        fach = (request.POST.get("fach") or "").strip()
        kurs = (request.POST.get("kurs") or "").strip()

        if not fach or not kurs:
            messages.warning(request, "Bitte zuerst Fach und dann Kurs auswählen.")
            return redirect("kurswahl")

        # 1) Alten Quiz-Session-State wegwerfen
        _clear_quiz_session(request)

        # 2) Neuen Kurs setzen (UniqueConstraint auf (fach, kurs) hilft hier)
        k = get_object_or_404(Kurse, fach=fach, kurs=kurs)
        request.session[SESSION_KURS_KEY] = str(k.id)
        # >>> HIER: altes Konzept vergessen, weil Kurs gewechselt
        request.session.pop(SESSION_KONZEPT_KEY, None)
        request.session.modified = True
        return redirect("kurs")

    faecher = (Kurse.objects
               .values_list("fach", flat=True)
               .order_by("fach")
               .distinct())

    return render(request, "kurswahl.html", {"faecher": faecher})


def kurs(request):
    """Kurs-Detailseite (zeigt z. B. Konzepte via kurs.konzepte.all)."""
    kurs_id = request.session.get(SESSION_KURS_KEY)
    if not kurs_id:
        messages.info(request, "Bitte zuerst einen Kurs auswählen.")
        return redirect("kurswahl")

    k = get_object_or_404(Kurse, id=kurs_id)
    return render(request, "kurs.html", {"kurs": k})



def konzept(request, konzept_id):
    k = get_object_or_404(Konzepte, id=konzept_id)
    # Auswahl merken (für quiz_view)
    request.session[SESSION_KONZEPT_KEY] = str(k.id)
    request.session.modified = True
    has_quiz = QuizQuestion.objects.filter(konzept=k, active=True).exists()
    return render(request, "konzept.html", {
        "konzept": k, 
        "kurs": k.kurs,
        "has_quiz": has_quiz,
        })




def quiz_complete(request):
    # Aktuellen Kurs holen (wie in quiz_view)
    kurs_id = request.session.get(SESSION_KURS_KEY)
    if not kurs_id:
        messages.info(request, "Bitte zuerst einen Kurs auswählen.")
        return redirect("konzept")

    # Konzept muss vorhanden sein, damit wir zurücknavigieren können
    konzept_id = request.session.get(SESSION_KONZEPT_KEY)
    if not konzept_id:
        messages.info(request, "Bitte zuerst ein Konzept auswählen.")
        return redirect("kurs")  # oder eigene Konzeptliste

    # Korrekte gemerkte Antworten (Zähler kam aus der quiz_view)
    correct = int(request.session.get('correct_count', 0))

    # Anzahl aktiver Aufgaben im Kurs (neues Modell!)
    total = QuizQuestion.objects.filter(
        active=True,
        konzept__kurs_id=kurs_id
    ).count()

    # Score-Ergebnis (Durchschnitt aus den tatsächlich bewerteten Items)
    score_sum    = float(request.session.get('score_sum', 0.0))
    items_scored = int(request.session.get('items_scored', 0))
    avg_score    = (score_sum / items_scored) if items_scored > 0 else 0.0

    # Labels nur für Anzeige (optional, falls du sie im Template zeigen willst)
    fach_label = request.session.get('quiz_fach')  # evtl. nicht mehr gesetzt
    kurs_label = request.session.get('quiz_kurs')  # evtl. nicht mehr gesetzt

    # Soft-Reset für einen neuen Durchlauf im selben Kurs
    request.session['quiz_index']    = 0
    request.session['correct_count'] = 0
    request.session['score_sum']     = 0.0
    request.session['items_scored']  = 0
    request.session.modified = True

    return render(request, 'quiz/quiz_complete.html', {
        'correct': correct,
        'total': total,
        'avg_score': round(avg_score, 3),
        'score_sum': round(score_sum, 3),
        'konzept_id': konzept_id
    })


def _clear_quiz_session(request):
    """Optional: ALLES zum Quizlauf aus der Session entfernen (harte Rücksetzung)."""
    # Feste Keys leeren
    keys_to_drop = [
        'quiz_fach', 'quiz_kurs', 'quiz_level',  # evtl. gar nicht mehr genutzt
        'quiz_index', 'correct_count',
        'score_sum', 'items_scored',
        SESSION_QUIZ_ID
    ]
    for k in keys_to_drop:
        if k in request.session:
            del request.session[k]

    # Alle Attempts & Timestamps (qlog_... und ..._created_at) entfernen
    for k in list(request.session.keys()):
        if k.startswith('qlog_') or k.endswith('_created_at'):
            del request.session[k]

    request.session.modified = True


