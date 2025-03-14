from django.db import models


class Lesson(models.Model):
    title = models.CharField(max_length=255, verbose_name="Сабақ атауы")
    content = models.TextField(verbose_name="Сабақ мәтіні")
    vocabulary = models.TextField(verbose_name="Сөздік")
    grammar = models.TextField(verbose_name="Грамматика")
    dialogue = models.TextField(verbose_name="Диалог")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Құру уақыты")

    def __str__(self):
        return self.title


class QuizQuestion(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="quiz_questions")
    english_word = models.CharField(max_length=100, verbose_name="Ағылшынша сөз")
    kazakh_translation = models.CharField(max_length=255, verbose_name="Қазақша аударма")

    def __str__(self):
        return f"{self.english_word} - {self.kazakh_translation}"


class QuizAttempt(models.Model):
    user_id = models.CharField(max_length=255, verbose_name="Қолданушы ID")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="quiz_attempts")
    score = models.IntegerField(default=0, verbose_name="Ұпай саны")
    attempts = models.IntegerField(default=0, verbose_name="Қателер саны")
    completed = models.BooleanField(default=False, verbose_name="Өтіп болды ма?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Өту уақыты")
    is_passed = models.BooleanField(default=False, verbose_name="Тест сәтті өтті ме?")

    def __str__(self):
        return f"{self.user_id} - {self.lesson.title} ({self.score} ұпай)"

    def increase_attempts(self):
        self.attempts += 1
        if self.attempts >= 3:
            self.score = 0
            self.attempts = 0
        self.save()

    def add_score(self):
        self.score += 1
        self.save()

    def check_pass(self):
        total_questions = self.lesson.quiz_questions.count()
        # Егер барлық сұрақтарға жауап берілсе
        if (self.score + self.attempts) >= total_questions:
            if self.attempts < 3:
                self.is_passed = True
                self.completed = True
            else:
                self.is_passed = False
            self.save()
