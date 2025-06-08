import google.generativeai as genai
from django.http import JsonResponse


# helper functions

def get_gemini_feedback(question, user_answer, correct_answer, feedback_prompt):
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"""
    Question: {question}
    User Answer: {user_answer}
    Correct Answer: {correct_answer}
    Feedback Prompt: {feedback_prompt}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})
