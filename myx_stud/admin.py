from django.contrib import admin
from .models import QuizQuestion, QuestionLog, Kurse, Konzepte


class KonzepteInline(admin.TabularInline):
    model = Konzepte
    extra = 1
    fields = ("sort", "name", "text")
    ordering = ("sort", "id")



# === Kurse ===
@admin.register(Kurse)
class KurseAdmin(admin.ModelAdmin):
    list_display = ['id', 'fach', 'kurs', 'intro']
    list_editable = ['fach', 'kurs', 'intro']
    list_per_page = 20
    search_fields = ['fach', 'kurs']
    list_filter = ['fach', 'kurs']


# === Konzepte ===
@admin.register(Konzepte)
class KonzepteAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "kurs", "funny"]
    list_editable = ["name", "funny"]
    search_fields = ["name", "kurs__fach", "kurs__kurs"]
    list_filter = ["kurs"]          # nach Kurs filtern (FK)
    ordering = ["name", "id"]       # KEIN 'sort' mehr!


# === QuizQuestion ===
@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ['item_id', 'text', 'question', 'image', 'correct_answer', 'gemini_feedback', 'feedback_prompt']
    list_editable = ['text', 'question', 'correct_answer', 'gemini_feedback', 'feedback_prompt']
    list_per_page = 10
    search_fields = ['question', 'konzept']
    list_filter = ['konzept', 'active']


# === QuestionLog ===
@admin.register(QuestionLog)
class QuestionLogAdmin(admin.ModelAdmin):
    list_display = ["id", "session_id", "quiz_id", "item_id", "attempt_count", "item_rating", "created_at"]
    search_fields = ["session_id", "quiz_id", "item_id", "fach", "kurs", "konzept"]
    list_filter = ["fach", "kurs", "konzept", "gemini_feedback"]
    readonly_fields = ["created_at", "started_at"]

    def attempt_count(self, obj):
        return len(obj.attempts or [])