import google.generativeai as genai
from django.http import JsonResponse


# helper functions

def get_gemini_feedback(text, question, user_answer, correct_answer, feedback_prompt):
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"""
    Du bist ein Tutor und hilfst einem Schüler bei der Bearbeitung von Übungsaufgaben.
    Gibt dem Schüler ein Feedback, sage aber nicht die korrekte Lösung.
    Der Schüler soll aufgrund deines Feedbacks seine Antwort nochmal überarbeiten.
    Wenn die Antwort korrekt ist, dann lobe ihm und sage ihm, dass er die nächste Aufgabe bearbeiten soll.
    Das ist der Aufgabentext: {text}
    Das ist die Frage: {question}
    Das ist die Antwort des Schülers: {user_answer}
    Das ist ein Hinweis auf die korrekte Antwort: {correct_answer}
    Überlege selbst, was die korrekte Antwort ist, wenn hier kein Hinweis steht.
    Erstelle ein Feedback nach diesen Vorgaben: {feedback_prompt}.
    Gib nur das Feedback zurück, nicht deine Überlegungen.
    Das Feedback soll den Schüler zum Nachdenken anregen.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})
