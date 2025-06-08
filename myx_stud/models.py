from django.db import models
from datetime import date

# Create your models here.
class QuizQuestion(models.Model):
    item_id = models.CharField(max_length=200, default="Default  text")
    title = models.CharField(max_length=200, default="Default title")
    created_at = models.DateField(default=date.today)
    topic = models.CharField(max_length=200, default="Default  text")
    goal = models.CharField(max_length=200, default="Default  text")
    text = models.CharField(max_length=1000, default="Default  text")
    image = models.ImageField(upload_to='quiz_images/', blank=True, null=True)
    question = models.CharField(max_length=1000, default="Default  text")
    correct_answer = models.CharField(max_length=1000, default="Default  text")
    gemini_feedback = models.BooleanField(default=False)
    feedback_prompt = models.CharField(max_length=1000, default="Default  text")
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.question
