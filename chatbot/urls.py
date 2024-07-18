# chatbot/urls.py
from django.urls import path
from chatbot.views import about, candidates, chat, register_candidate, profile

urlpatterns = [
    path('', about, name='about'),
    path('about/', about, name='about'),
    path('candidates/', candidates, name='candidates'),
    path('chat/<slug:slug>/', chat, name='chat'),
    path('register_candidate/', register_candidate, name='register_candidate'),
    path('profile/', profile, name='profile'),
]

