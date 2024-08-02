# chatbot/urls.py
from django.urls import path
from chatbot.views import about, candidates, chat, manager_candidate, profile, format_resume, interactions, view_interaction

urlpatterns = [
    path('', about, name='about'),
    path('about/', about, name='about'),
    path('candidate/', manager_candidate, name='manager_candidate'),
    path('candidates/', candidates, name='candidates'),
    path('interactions/', interactions, name='interactions'),
    path('interactions/view/<int:user_id>/<int:candidate_id>/', view_interaction, name='view_interaction'),
    path('profile/', profile, name='profile'),
    path('format_resume/', format_resume, name='format_resume'),
    path('chat/<slug:slug>/', chat, name='chat'),
]
