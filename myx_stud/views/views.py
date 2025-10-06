import uuid
from django.shortcuts import render, redirect
from ..models import QuizQuestion
from django.http import JsonResponse



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



def kurs_view(request):
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
            return render(request, 'kurs.html', {
                'topics': topics,
                'goals': goals,
                'error': 'No quiz items found for the selected topic and goal.',
                'selected_topic': selected_topic,
                'selected_goal': selected_goal,
            })

        # Pro Quiz-Durchlauf eine frische UUID erzeugen und in Session ablegen
        request.session['quiz_run_id'] = uuid.uuid4().hex

        # Startdaten in Session
        request.session['quiz_topic'] = selected_topic
        request.session['quiz_goal'] = selected_goal
        request.session['quiz_index'] = 0
        request.session['correct_count'] = 0
        # Score-Tracking
        request.session['score_sum'] = 0.0
        request.session['items_scored'] = 0

        return redirect('quiz_view')

    return render(request, 'kurs.html', {
        'topics': topics,
        'goals': goals,
    })






def quiz_complete(request):
    correct = request.session.get('correct_count', 0)
    topic = request.session.get('quiz_topic')
    goal  = request.session.get('quiz_goal')

    total = QuizQuestion.objects.filter(
        active=True, topic=topic, goal=goal
    ).count()

    # ⬇️ NEU: Score-Ergebnis
    score_sum = float(request.session.get('score_sum', 0.0))
    items_scored = int(request.session.get('items_scored', 0))
    avg_score = (score_sum / items_scored) if items_scored > 0 else 0.0

    # Optional: zurücksetzen
    request.session['quiz_index'] = 0
    request.session['correct_count'] = 0
    request.session['score_sum'] = 0.0
    request.session['items_scored'] = 0

    return render(request, 'quiz/quiz_complete.html', {
        'correct': correct,
        'total': total,
        'topic': topic,
        'goal': goal,
        'score_sum': round(score_sum, 3),     # ⬅️ NEU
        'avg_score': round(avg_score, 3),     # ⬅️ NEU
    })

