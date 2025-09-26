from django.contrib import admin
from .models import QuizQuestion, QuestionLog

# === QuizQuestion ===
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ['item_id', 'topic', 'goal', 'text', 'question', 'image', 'correct_answer', 'gemini_feedback', 'feedback_prompt']
    list_editable = ['text', 'question', 'correct_answer', 'gemini_feedback', 'feedback_prompt']
    list_per_page = 100
    search_fields = ['question', 'topic', 'goal']
    list_filter = ['topic', 'goal', 'active']

admin.site.register(QuizQuestion, QuizQuestionAdmin)

# === QuestionLog ===
class QuestionLogAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'quiz_id', 'item_id', 'topic', 'goal', 'gemini_feedback')
    list_filter = ('topic', 'goal', 'gemini_feedback')
    search_fields = ('session_id', 'quiz_id', 'item_id', 'question', 'text')
    list_per_page = 100

admin.site.register(QuestionLog, QuestionLogAdmin)
