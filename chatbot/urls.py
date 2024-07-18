# chatbot/urls.py
from django.urls import path
from chatbot.views import about, candidates, chat, manager_candidate, profile

urlpatterns = [
    path('', about, name='about'),
    path('about/', about, name='about'),
    path('candidate/', manager_candidate, name='manager_candidate'),
    path('candidates/', candidates, name='candidates'),
    path('profile/', profile, name='profile'),
    path('chat/<slug:slug>/', chat, name='chat'),

]

