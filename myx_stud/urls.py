from django.urls import path
from .views.views import home, get_goals_for_topic, kurs_view, quiz_complete

from .views.quizview import quiz_view


urlpatterns = [
    path("", home, name="home"),
    path("kurs/", kurs_view, name="kurs_view"),
    path("quiz/view/", quiz_view, name="quiz_view"),
    path('quiz/complete/', quiz_complete, name='quiz_complete'),
    path('quiz/ajax/get-goals/', get_goals_for_topic, name='get_goals_for_topic'),
]