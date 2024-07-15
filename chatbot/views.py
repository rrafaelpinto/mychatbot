from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from langchain_text_splitters import CharacterTextSplitter

from .models import Candidate, Interaction
from .core import chatbot

def about(request):
    return render(request, 'about.html')

@login_required
def candidates(request):
    candidates = Candidate.objects.all()
    return render(request, 'candidates.html', {'candidates': candidates})


@login_required
def chat(request, slug):
    candidate = get_object_or_404(Candidate, slug=slug)
    user = request.user
    interactions = Interaction.objects.filter(user=user, candidate=candidate).order_by('timestamp')

    if request.method == 'POST':
        question = request.POST.get('question')
        if question:
            text_splitter = CharacterTextSplitter(chunk_size=2000, chunk_overlap=0)
            chunks = text_splitter.split_text(candidate.resume)
            response = ''
            for chunk in chunks:
                response += chatbot.run({'curriculum': chunk, 'question': question})

            interaction = Interaction.objects.create(user=user, candidate=candidate, question=question, response=response)
            timestamp = interaction.timestamp.strftime('%d/%m/%Y %H:%M:%S')
            return JsonResponse({
                'response': response,
                'timestamp': timestamp
            })
    return render(request, 'chat.html', {'candidate': candidate, 'interactions': interactions})
