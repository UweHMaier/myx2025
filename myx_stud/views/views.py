from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from ..models import QuizQuestion, Kurse
from django.http import JsonResponse


SESSION_KURS_KEY = "current_kurs_id"
SESSION_QUIZ_ID  = "quiz_run_id"   # konsistent benutzen


# -------- Views --------
# (ohne quiz view, wurde ausgelagert)

def home(request):
    return render (request, "home.html")



def get_kurse_for_fach(request):
    fach = request.GET.get("fach", "")
    kurse = (Kurse.objects
             .filter(fach=fach)
             .values_list("kurs", flat=True)
             .order_by("kurs")
             .distinct())
    return JsonResponse({"kurse": list(kurse)})



def kurswahl(request):
    if request.method == "POST":
        fach = request.POST.get("fach")
        kurs = request.POST.get("kurs")
        if not fach or not kurs:
            messages.warning(request, "Bitte zuerst Fach und dann Kurs auswählen.")
            return redirect("kurswahl")
        
        # 1) Alten Quiz-Session-State wegwerfen
        _clear_quiz_session(request)

        # 2) Neuen Kurs setzen
        k = get_object_or_404(Kurse, fach=fach, kurs=kurs)
        request.session[SESSION_KURS_KEY] = str(k.id)
        request.session.modified = True
        return redirect("kurs")

    faecher = Kurse.objects.values_list("fach", flat=True).order_by("fach").distinct()
    return render(request, "kurswahl.html", {"faecher": faecher})



def kurs(request):
    kurs_id = request.session.get(SESSION_KURS_KEY)
    if not kurs_id:
        messages.info(request, "Bitte zuerst einen Kurs auswählen.")
        return redirect("kurswahl")
    k = get_object_or_404(Kurse, id=kurs_id)
    return render(request, "kurs.html", {"kurs": k})



def quiz_complete(request):
    correct = int(request.session.get('correct_count', 0))

    # aus dem Lauf übernehmen
    fach  = request.session.get('quiz_fach')
    kurs  = request.session.get('quiz_kurs')
    level = request.session.get('quiz_level')  # optional; nur gesetzt, wenn du's vorher speicherst

    # Anzahl Aufgaben zu diesem Fach/Kurs (und ggf. Level)
    qs = QuizQuestion.objects.filter(active=True, fach=fach, kurs=kurs)
    if level:
        qs = qs.filter(level=level)
    total = qs.count()

    # Score-Ergebnis
    score_sum    = float(request.session.get('score_sum', 0.0))
    items_scored = int(request.session.get('items_scored', 0))
    avg_score    = (score_sum / items_scored) if items_scored > 0 else 0.0

    # Optional: Lauf zurücksetzen (Index/Counter). Run-ID & Auswahl lässt du i. d. R. stehen.
    request.session['quiz_index']    = 0
    request.session['correct_count'] = 0
    request.session['score_sum']     = 0.0
    request.session['items_scored']  = 0

    return render(request, 'quiz/quiz_complete.html', {
        'correct': correct,
        'total': total,
        'fach': fach,
        'kurs': kurs,
        'level': level,  # optional, im Template einfach mit |default:"" absichern
        'score_sum': round(score_sum, 3),
        'avg_score': round(avg_score, 3),
    })


def _clear_quiz_session(request):
    # Feste Keys leeren
    keys_to_drop = [
        'quiz_fach', 'quiz_kurs', 'quiz_level',
        'quiz_index', 'correct_count',
        'score_sum', 'items_scored',
        SESSION_QUIZ_ID,
    ]
    for k in keys_to_drop:
        if k in request.session:
            del request.session[k]

    # Alle Attempts & Timestamps (qlog_... und ..._created_at) entfernen
    for k in list(request.session.keys()):
        if k.startswith('qlog_') or k.endswith('_created_at'):
            del request.session[k]

    request.session.modified = True