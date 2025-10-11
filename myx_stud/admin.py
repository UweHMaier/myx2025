from django.contrib import admin
from .models import QuizQuestion, QuestionLog, Kurse


# === Kurse ===
@admin.register(Kurse)
class KurseAdmin(admin.ModelAdmin):
    list_display = ['id', 'fach', 'kurs', 'intro']
    list_editable = ['fach', 'kurs', 'intro']
    list_per_page = 20
    search_fields = ['fach', 'kurs']
    list_filter = ['fach', 'kurs']

# === QuizQuestion ===
@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ['item_id', 'fach', 'kurs', 'level', 'text', 'question', 'image', 'correct_answer', 'gemini_feedback', 'feedback_prompt']
    list_editable = ['level', 'text', 'question', 'correct_answer', 'gemini_feedback', 'feedback_prompt']
    list_per_page = 10
    search_fields = ['question', 'fach', 'kurs', 'level']
    list_filter = ['fach', 'kurs', 'active']


# === QuestionLog ===
@admin.register(QuestionLog)
class QuestionLogAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'quiz_id', 'item_id', 'fach', 'kurs', 'level', 'gemini_feedback')
    list_filter = ('fach', 'kurs', 'gemini_feedback')
    search_fields = ('session_id', 'quiz_id', 'item_id', 'question', 'text')
    list_per_page = 10

