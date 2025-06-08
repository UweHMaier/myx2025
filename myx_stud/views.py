from django.shortcuts import render, redirect, HttpResponse
from .models import QuizQuestion
from django.conf import settings
from django.http import JsonResponse
from .utils.functions import get_gemini_feedback


# Create your views here.
def home(request):
    return render (request, "home.html")

def quiz_items(request):
    quizitems = QuizQuestion.objects.all()
    return render(request, "quiz/quiz_items.html", {"quizitems": quizitems})


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

        # ✅ Validate that quiz items exist for selected topic & goal
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

        # Store selections in session and start quiz
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

    # If quiz is finished, go to results
    if current_index >= total_questions:
        return redirect('quiz_complete')

    current_question = questions[current_index]
    feedback = None
    user_answer = ''

    if request.method == 'POST':
        if 'next' in request.POST:
            request.session['quiz_index'] = current_index + 1
            return redirect('quiz_view')

        user_answer = request.POST.get('answer', '').strip()

        if current_question.gemini_feedback:
            # Gemini handles feedback; no correctness shown
            feedback_ai = get_gemini_feedback(
                current_question.question,
                user_answer,
                current_question.correct_answer,
                current_question.feedback_prompt 
            )
            if isinstance(feedback_ai, JsonResponse):
                feedback_ai = "We had trouble generating feedback. Try again later."

            feedback = {
                'is_correct': None,  # not shown
                'correct_answer': None,  # not shown
                'feedback_ai': feedback_ai
            }

        else:
            # Exact match grading
            is_correct = user_answer.lower() == current_question.correct_answer.lower()

            if is_correct:
                request.session['correct_count'] = request.session.get('correct_count', 0) + 1

            feedback = {
                'is_correct': is_correct,
                'correct_answer': current_question.correct_answer,
                'feedback_ai': None
            }

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

    # Optionally clear session
    request.session['quiz_index'] = 0
    request.session['correct_count'] = 0

    return render(request, 'quiz/quiz_complete.html', {
        'correct': correct,
        'total': total,
        'topic': topic,
        'goal': goal,
    })


