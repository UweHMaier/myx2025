from django.core.management.base import BaseCommand
from myx_stud.models import QuizQuestion
import pandas as pd
import os
from datetime import date
import re

class Command(BaseCommand):
    help = 'Uploads quiz questions from an Excel file and generates unique item_ids'

    def handle(self, *args, **kwargs):
        file_path = os.path.join('myx_stud', 'management', 'files', 'Quizitems.xlsx')

        try:
            df = pd.read_excel(file_path)

            required_columns = {'topic', 'goal', 'question', 'text', 'correct_answer'}
            if not required_columns.issubset(df.columns):
                self.stderr.write(self.style.ERROR(f'Missing columns. Required: {required_columns}'))
                return

            # Find the last used item_id number
            existing_ids = QuizQuestion.objects.filter(item_id__startswith='quiz-')
            max_id = 0
            for q in existing_ids:
                match = re.match(r'quiz-(\d+)', q.item_id)
                if match:
                    max_id = max(max_id, int(match.group(1)))

            quiz_questions = []
            for i, (_, row) in enumerate(df.iterrows(), start=1):
                new_id = f"quiz-{max_id + i:05d}"

                quiz = QuizQuestion(
                    item_id=new_id,
                    title=row['question'][:200],
                    created_at=date.today(),
                    topic=row['topic'],
                    goal=row['goal'],
                    text=row['text'],
                    question=row['question'],
                    correct_answer=row['correct_answer'],
                    feedback_prompt="Default feedback",
                    active=True
                )
                quiz_questions.append(quiz)

            QuizQuestion.objects.bulk_create(quiz_questions)
            self.stdout.write(self.style.SUCCESS(f'Successfully uploaded {len(quiz_questions)} quiz questions.'))

        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f'File not found: {file_path}'))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Unexpected error: {str(e)}'))
