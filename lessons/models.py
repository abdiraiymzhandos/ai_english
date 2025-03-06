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
