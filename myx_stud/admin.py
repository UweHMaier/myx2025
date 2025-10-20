from django.contrib import admin
from .models import QuizQuestion, QuestionLog, Kurse, Konzepte
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet


# ===== Helpers =====
def allowed_courses_qs(user) -> QuerySet:
    if not user.is_active or not user.is_staff:
        return Kurse.objects.none()
    if user.is_superuser:
        return Kurse.objects.all()
    return Kurse.objects.filter(editors=user)

def user_can_access_course(user, kurs: Kurse) -> bool:
    if not user.is_active or not user.is_staff:
        return False
    if user.is_superuser:
        return True
    return allowed_courses_qs(user).filter(pk=kurs.pk).exists()

def allowed_konzepte_qs(user) -> QuerySet:
    return Konzepte.objects.filter(kurs__in=allowed_courses_qs(user))




# ===== Kurse =====
@admin.register(Kurse)
class KurseAdmin(admin.ModelAdmin):
    list_display   = ['id', 'fach', 'kurs', 'intro']
    list_editable  = ['fach', 'kurs', 'intro']
    list_per_page  = 20
    search_fields  = ['fach', 'kurs', 'intro']   # <- 'name' entfernt
    list_filter    = ['fach', 'kurs']
    filter_horizontal = ["editors"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(pk__in=allowed_courses_qs(request.user).values("pk"))

    # Absicherung gegen Direkt-URL-Zugriffe
    def has_view_permission(self, request, obj=None):
        base = super().has_view_permission(request, obj)
        if not base or obj is None or request.user.is_superuser:
            return base
        return user_can_access_course(request.user, obj)

    def has_change_permission(self, request, obj=None):
        base = super().has_change_permission(request, obj)
        if not base or obj is None or request.user.is_superuser:
            return base
        return user_can_access_course(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        base = super().has_delete_permission(request, obj)
        if not base or obj is None or request.user.is_superuser:
            return base
        return user_can_access_course(request.user, obj)

    def has_add_permission(self, request):
        # Meist kein Kurs-Anlegen für Redakteure
        return request.user.is_superuser


# ===== Konzepte =====
@admin.register(Konzepte)
class KonzepteAdmin(admin.ModelAdmin):
    list_display  = ["id", "name", "kurs", "funny"]
    list_editable = ["name", "funny"]
    search_fields = ["name", "kurs__fach", "kurs__kurs"]
    list_filter   = ["kurs"]
    raw_id_fields = ["kurs"]  # schneller FK-Picker
    # Optional schöner: autocomplete_fields = ["kurs"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(kurs__in=allowed_courses_qs(request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "kurs" and not request.user.is_superuser:
            kwargs["queryset"] = allowed_courses_qs(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not user_can_access_course(request.user, obj.kurs):
            raise PermissionDenied("Du darfst diesem Kurs keine Konzepte zuordnen.")
        super().save_model(request, obj, form, change)

    def has_view_permission(self, request, obj=None):
        base = super().has_view_permission(request, obj)
        if not base or obj is None or request.user.is_superuser:
            return base
        return user_can_access_course(request.user, obj.kurs)

    def has_change_permission(self, request, obj=None):
        base = super().has_change_permission(request, obj)
        if not base or obj is None or request.user.is_superuser:
            return base
        return user_can_access_course(request.user, obj.kurs)

    def has_delete_permission(self, request, obj=None):
        base = super().has_delete_permission(request, obj)
        if not base or obj is None or request.user.is_superuser:
            return base
        return user_can_access_course(request.user, obj.kurs)

    def has_add_permission(self, request):
        base = super().has_add_permission(request)
        if request.user.is_superuser:
            return base
        return base and allowed_courses_qs(request.user).exists()

    def get_model_perms(self, request):
        perms = super().get_model_perms(request)
        if request.user.is_superuser:
            return perms
        return perms if allowed_courses_qs(request.user).exists() else {}
    


# === QuizQuestion ===
@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ['item_id', 'text', 'question', 'image', 'correct_answer', 'gemini_feedback', 'feedback_prompt']
    list_editable = ['text', 'question', 'correct_answer', 'gemini_feedback', 'feedback_prompt']
    list_per_page = 10
    search_fields = ['question', 'konzept']

    list_filter   = ["active", ("konzept", admin.RelatedOnlyFieldListFilter)]
    raw_id_fields = ["konzept"]  # schneller FK-Picker (alternativ: autocomplete_fields)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("konzept__kurs")
        if request.user.is_superuser:
            return qs
        return qs.filter(konzept__kurs__in=allowed_courses_qs(request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "konzept" and not request.user.is_superuser:
            kwargs["queryset"] = allowed_konzepte_qs(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # Absichern gegen manuelles POSTen fremder Konzepte/Kurse
        if not request.user.is_superuser:
            kurs = obj.konzept.kurs
            if not user_can_access_course(request.user, kurs):
                raise PermissionDenied("Du darfst nur Quizfragen deiner freigegebenen Kurse bearbeiten.")
        super().save_model(request, obj, form, change)

    # Objektbezogene Guards (Direkt-URL)
    def has_view_permission(self, request, obj=None):
        base = super().has_view_permission(request, obj)
        if not base or obj is None or request.user.is_superuser:
            return base
        return user_can_access_course(request.user, obj.konzept.kurs)

    def has_change_permission(self, request, obj=None):
        base = super().has_change_permission(request, obj)
        if not base or obj is None or request.user.is_superuser:
            return base
        return user_can_access_course(request.user, obj.konzept.kurs)

    def has_delete_permission(self, request, obj=None):
        base = super().has_delete_permission(request, obj)
        if not base or obj is None or request.user.is_superuser:
            return base
        return user_can_access_course(request.user, obj.konzept.kurs)

    def has_add_permission(self, request):
        base = super().has_add_permission(request)
        if request.user.is_superuser:
            return base
        # „Add“ nur, wenn der User mind. ein Konzept (über freigegebene Kurse) wählen darf
        return base and allowed_konzepte_qs(request.user).exists()

    def get_model_perms(self, request):
        # Modell komplett aus dem Menü ausblenden, wenn der User keine Kurse hat
        perms = super().get_model_perms(request)
        if request.user.is_superuser:
            return perms
        return perms if allowed_courses_qs(request.user).exists() else {}


# === QuestionLog ===
@admin.register(QuestionLog)
class QuestionLogAdmin(admin.ModelAdmin):
    list_display = ["id", "session_id", "quiz_id", "item_id", "attempt_count", "item_rating", "created_at"]
    search_fields = ["session_id", "quiz_id", "item_id", "fach", "kurs", "konzept"]
    list_filter = ["fach", "kurs", "konzept", "gemini_feedback"]
    readonly_fields = ["created_at", "started_at"]

    def attempt_count(self, obj):
        return len(obj.attempts or [])