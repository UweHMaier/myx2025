from django.urls import path
from .views.views import home, kurs, get_kurse_for_fach, kurswahl, quiz_complete

from .views.quizview import quiz_view


urlpatterns = [
    path("", home, name="home"),
    path("kurswahl/", kurswahl, name="kurswahl"),
    path("kurs/", kurs, name="kurs"),
    path("quiz/view/", quiz_view, name="quiz_view"),
    path('quiz/complete/', quiz_complete, name='quiz_complete'),
    path("quiz/ajax/get-kurse/", get_kurse_for_fach, name="get_kurse_for_fach"),
]