from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify

class Candidate(models.Model):
    name = models.CharField(max_length=255, verbose_name='Name')
    email = models.EmailField(verbose_name='Email')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Phone')
    linkedin = models.URLField(blank=True, null=True, verbose_name='LinkedIn')
    resume = models.TextField(verbose_name='Resume')
    slug = models.SlugField(unique=True, blank=True, verbose_name='Slug')
    image = models.ImageField(upload_to='candidate_images/', blank=True, null=True, verbose_name="Image")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Candidate'
        verbose_name_plural = 'Candidates'


class Interaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interactions', verbose_name='User')
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='interactions', verbose_name='Candidate')
    question = models.TextField(verbose_name='Question')
    response = models.TextField(verbose_name='Response')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Timestamp')

    def __str__(self):
        return f'Interaction by {self.user.username} with {self.candidate.name} on {self.timestamp.strftime("%d/%m/%Y %H:%M:%S")}'