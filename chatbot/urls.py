# chatbot/urls.py
from django.urls import path
from chatbot.views import about, candidates, chat

urlpatterns = [
    path('candidates/', candidates, name='candidates'),
    path('', about, name='about'),
    path('about/', about, name='about'),
    path('<slug:slug>/', chat, name='chat'),
]

