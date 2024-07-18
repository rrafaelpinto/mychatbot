# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from .models import Candidate, DefaultQuestion
#
# @receiver(post_save, sender=Candidate)
# def create_default_questions(sender, instance, created, **kwargs):
#     if created:
#         resume_text = instance.resume
#         #TODO: ISSO DAQUI PODE FICAR ESTÁTICO POR ENQUANTO.
#         default_prompts = [
#             f"What are the your main strengths?",
#             f"Describe the most relevant work experience mentioned in your resume?",
#             f"What are the key skills highlighted in your resume?"
#         ]
#         for prompt in default_prompts:
#             DefaultQuestion.objects.create(candidate=instance, prompt=prompt)
