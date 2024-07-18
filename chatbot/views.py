from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from langchain_text_splitters import CharacterTextSplitter

from .core import resumebot
from .forms import CandidateRegistrationForm
from .models import Candidate, Interaction


def about(request):
    return render(request, 'about.html')

@login_required
def profile(request):
    candidate = get_object_or_404(Candidate, user=request.user)
    return render(request, 'profile.html', {'candidate': candidate})


@login_required
def register_candidate(request):
    if request.method == 'POST':
        form = CandidateRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = request.user
            candidate = form.save(commit=False)
            candidate.user = user
            candidate.save()
            return redirect('profile')
    else:
        form = CandidateRegistrationForm()
    return render(request, 'register_candidate.html', {'form': form})


@login_required
def candidates(request):
    candidates = Candidate.objects.filter(public_profile=True).order_by('name')
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
                response += resumebot.run({'curriculum': chunk, 'question': question})

            interaction = Interaction.objects.create(user=user, candidate=candidate, question=question, response=response)
            timestamp = interaction.timestamp.strftime('%d/%m/%Y %H:%M:%S')
            return JsonResponse({
                'response': response,
                'timestamp': timestamp
            })
    return render(request, 'chat.html', {'candidate': candidate, 'interactions': interactions})
