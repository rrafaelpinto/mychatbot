# chatbot/urls.py
from django.urls import path
from chatbot.views import candidate_list_view, chatbot_view

urlpatterns = [
    path('chat/<slug:slug>/', chatbot_view, name='chatbot'),
    path('candidates/', candidate_list_view, name='candidate_list'),
]

