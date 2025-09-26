import google.generativeai as genai
from django.http import JsonResponse


# helper functions

def get_gemini_feedback(text, question, user_answer, correct_answer, feedback_prompt):
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"""
    Du bist ein Tutor und hilfst einem Schüler bei der Bearbeitung von Übungsaufgaben.
    Der Schüler soll aufgrund deines Feedbacks seine Antwort nochmal überarbeiten.
    Wenn die Antwort korrekt ist, dann lobe ihm und sage ihm, dass er die nächste Aufgabe bearbeiten soll.
    Das ist der Aufgabentext: {text}
    Das ist die Frage: {question}
    Das ist die Antwort des Schülers: {user_answer}
    Das ist ein Hinweis auf die korrekte Antwort: {correct_answer}
    Erstelle ein Feedback nach diesen Vorgaben: {feedback_prompt}.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})



# Füge diese Helferfunktion in views.py ein (oder in utils und dann importieren)
def get_feedback_unified(current_question, user_answer):
    """
    Einheitliches Rückgabeformat:
    {
      "is_correct": True/False/None,
      "correct_answer": str|None,
      "feedback_ai": str|None
    }
    """
    if current_question.gemini_feedback:
        fb = get_gemini_feedback(
            current_question.text,
            current_question.question,
            user_answer,
            current_question.correct_answer,
            current_question.feedback_prompt
        )
        if isinstance(fb, JsonResponse):
            fb = "We had trouble generating feedback. Try again later."
        return {"is_correct": None, "correct_answer": None, "feedback_ai": fb}

    # Exact match
    is_correct = user_answer.lower() == (current_question.correct_answer or "").lower()
    return {
        "is_correct": is_correct,
        "correct_answer": current_question.correct_answer,
        "feedback_ai": None
    }
