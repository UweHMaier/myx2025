from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("kurs/", views.kurs_view, name="kurs_view"),
    path("quiz/view/", views.quiz_view, name="quiz_view"),
    path('quiz/complete/', views.quiz_complete, name='quiz_complete'),
    path('quiz/ajax/get-goals/', views.get_goals_for_topic, name='get_goals_for_topic'),
]