from django.db import models
import uuid
from datetime import date


# Create your models here.
class QuizQuestion(models.Model):
    # Primärschlüssel als UUID

    item_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Stabile, externe UUID für die Frage"
    )
    # automatisch beim Anlegen gesetzt (Datum + Uhrzeit)
    created_at = models.DateTimeField(auto_now_add=True)

    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=200)
    goal = models.CharField(max_length=200)
    text = models.CharField(max_length=1000, blank=True)
    image = models.ImageField(upload_to='quiz_images/', blank=True, null=True)
    question = models.CharField(max_length=1000, blank=True)
    correct_answer = models.CharField(max_length=1000, blank=True)
    gemini_feedback = models.BooleanField(default=False)
    feedback_prompt = models.CharField(max_length=1000, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.question or f"QuizQuestion {self.item_id}"
    


# Model for all log info: student answer, feedback
class QuestionLog(models.Model):
    session_id = models.CharField(max_length=200, default="Default text")   # Django-Session-Key
    quiz_id = models.CharField(max_length=200, default="Default text")      # für jeden Quiz Durchgang
    item_id = models.CharField(max_length=200, default="Default text")
    topic = models.CharField(max_length=200, default="Default text")
    goal = models.CharField(max_length=200, default="Default text")
    text = models.CharField(max_length=1000, default="Default text")
    image = models.ImageField(upload_to='quiz_images/', blank=True, null=True)
    question = models.CharField(max_length=1000, default="Default text")
    correct_answer = models.CharField(max_length=1000, default="Default text")
    gemini_feedback = models.BooleanField(default=False)
    feedback_prompt = models.CharField(max_length=1000, default="Default text")

    created_at = models.DateTimeField(auto_now_add=True)  # Startzeit (Start Quiz)

    stud_answ1 = models.CharField(max_length=1000, blank=True, default="")
    feedback1 = models.CharField(max_length=1000, blank=True, default="")
    feedback1_rating = models.IntegerField(null=True, blank=True)

    stud_answ2 = models.CharField(max_length=1000, blank=True, default="")
    feedback2 = models.CharField(max_length=1000, blank=True, default="")
    feedback2_rating = models.IntegerField(null=True, blank=True)

    stud_answ3 = models.CharField(max_length=1000, blank=True, default="")
    feedback3 = models.CharField(max_length=1000, blank=True, default="")
    feedback3_rating = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.session_id} | quiz={self.quiz_id} | item={self.item_id}"