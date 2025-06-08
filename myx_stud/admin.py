from django.contrib import admin
from .models import QuizQuestion

# Register your models here.

class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ['item_id', 'topic', 'goal', 'text', 'question', 'image', 'correct_answer', 'gemini_feedback', 'feedback_prompt']
    list_editable = ['text', 'question', 'correct_answer', 'gemini_feedback', 'feedback_prompt']
    list_per_page = 100  # Optional: number of rows per page
    search_fields = ['question', 'topic', 'goal']
    list_filter = ['topic', 'goal', 'active']

admin.site.register(QuizQuestion, QuizQuestionAdmin)
