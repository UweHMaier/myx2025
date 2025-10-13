from django.db import models
import uuid

        

# Tabelle für die Kurse
class Kurse(models.Model):
    # Primärschlüssel als UUID
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # automatisch beim Anlegen gesetzt (Datum + Uhrzeit)
    created_at = models.DateTimeField(auto_now_add=True)
    fach = models.CharField(max_length=200,verbose_name="Fach")
    kurs = models.CharField(max_length=200, verbose_name="Kurs")
    intro = models.TextField(blank=True)
    image = models.ImageField(upload_to='kurs_images/', blank=True, null=True)
    video_url = models.CharField(max_length=200, blank=True)  
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["fach", "kurs"], name="uniq_fach_kurs")
        ]

    def __str__(self):
        return f"{self.fach} – {self.kurs}"



class Konzepte(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) 
    kurs = models.ForeignKey(Kurse, on_delete=models.CASCADE, related_name="konzepte")
    name = models.CharField(max_length=200, blank=True, null=True)
    funny = models.CharField(max_length=200, blank=True, null=True)
    video_url = models.CharField(max_length=200, blank=True, null=True)
    definition = models.TextField(blank=True, default="Um was geht es denn?")
    example = models.TextField(blank=True, default="immer ein Beispiel bringen")
    image = models.ImageField(upload_to='concept_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.kurs} · {self.name or 'ohne Titel'}"



class QuizQuestion(models.Model):
    item_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    konzept = models.ForeignKey(Konzepte, on_delete=models.CASCADE, related_name="quizitems")  # ⬅️ plural
    title = models.CharField(max_length=200)
    text = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to='quiz_images/', blank=True, null=True)
    question = models.CharField(max_length=200, blank=True)
    correct_answer = models.CharField(max_length=200, blank=True)
    gemini_feedback = models.BooleanField(default=False)
    feedback_prompt = models.CharField(max_length=500, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.question or f"QuizQuestion {self.item_id}"


    

# Model for all log info: student answer, feedback
class QuestionLog(models.Model):
    session_id = models.CharField(max_length=200, db_index=True)          # kein Default
    quiz_id    = models.CharField(max_length=200, db_index=True)          # Run-ID
    item_id    = models.CharField(max_length=200, db_index=True)

    fach    = models.CharField(max_length=200, blank=True, verbose_name="Fach")
    kurs    = models.CharField(max_length=200, blank=True, verbose_name="Kurs")
    konzept = models.CharField(max_length=200, blank=True, verbose_name="Konzept")

    text            = models.TextField(blank=True)
    question        = models.TextField(blank=True)
    correct_answer  = models.TextField(blank=True)
    gemini_feedback = models.BooleanField(default=False)
    feedback_prompt = models.TextField(blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    attempts   = models.JSONField(default=list)     # Liste von Versuchen
    item_rating = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["session_id"]),
            models.Index(fields=["quiz_id"]),
            models.Index(fields=["item_id"]),
            models.Index(fields=["quiz_id", "item_id"]),
        ]

    def __str__(self):
        return f"{self.session_id} | quiz={self.quiz_id} | item={self.item_id}"
