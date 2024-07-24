import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect

from langchain_text_splitters import CharacterTextSplitter

from mychatbot.utils import process_resume
from .prompts import resumebot, extraction_prompt
from .forms import CandidateRegistrationForm
from .models import Candidate, Interaction


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        # user_id = text_data_json["user_id"]  # Assuming user_id is passed in the WebSocket message
        user_id = 1

        candidate = await self.get_candidate(user_id)

        if candidate:
            resume = candidate.resume
            # Print the resume for debugging
            print(resume)
            try:
                complete_result = ""
                async for chunk in extraction_prompt.astream_events({'resume': resume}, version="v1"):
                    print(f'chunk: {chunk}')
                    if chunk["event"] in ["on_llm_start", "on_llm_stream", "on_chain_stream"]:
                        await self.send(text_data=json.dumps(chunk))
                    if chunk["event"] == "on_llm_end":
                        # Save the final result to the candidate's resume
                        result = chunk.get("data", {}).get("output", {}).get("generations", [])[0][0].get("text", "")
                        complete_result += result

                if complete_result:
                    print('####################################')
                    print(complete_result)
                    await self.save_candidate_resume(candidate, complete_result)
                    await self.send(text_data=json.dumps({'result': complete_result, 'message': 'Resume updated successfully.'}))
                else:
                    print("Resultado não encontrado no chunk.")
                    await self.send(text_data=json.dumps({'error': 'Result not found in the chunks.'}))

            except Exception as e:
                print(e)
                await self.send(text_data=json.dumps({'error': str(e)}))
        else:
            await self.send(text_data=json.dumps({'error': 'Candidate not found'}))

    @sync_to_async
    def get_candidate(self, user_id):
        try:
            user = User.objects.get(pk=user_id)
            candidate = Candidate.objects.get(user=user)
            print(f'Encontrou: {candidate}')
            return candidate
        except User.DoesNotExist:
            return None
        except Candidate.DoesNotExist:
            return None

    @sync_to_async
    def save_candidate_resume(self, candidate, resume):
        candidate.resume = resume
        print('salvando')
        candidate.save()


@login_required
def format_resume(request):
    candidate = get_object_or_404(Candidate, user=request.user)
    resume = extraction_prompt.run({'resume': candidate.resume})
    candidate.resume = resume
    candidate.save()
    messages.success(request, 'Resume well formated successfully.')
    return redirect('profile')


def about(request):
    return render(request, 'about.html')

@login_required
def profile(request):
    candidate = get_object_or_404(Candidate, user=request.user)
    return render(request, 'profile.html', {'candidate': candidate})


@login_required
def manager_candidate(request):
    try:
        candidate = Candidate.objects.get(user=request.user)
        title = 'Edit profile'
    except Candidate.DoesNotExist:
        candidate = None
        title = 'Register as candidate'
    if request.method == 'POST':
        form = CandidateRegistrationForm(request.POST or None, request.FILES, instance=candidate)
        if form.is_valid():
            try:
                candidate = form.save(commit=False)
                candidate.user = request.user

                # Process the uploaded resume file
                resume_file = request.FILES.get('resume_file')
                if resume_file:
                    fs = FileSystemStorage()
                    filename = fs.save(resume_file.name, resume_file)
                    uploaded_file_path = fs.path(filename)

                    # Extract text from the resume file
                    candidate.resume = process_resume(uploaded_file_path)
                    candidate.save()

                messages.success(request, 'Profile updated successfully.')
                return redirect('profile')
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}', extra_tags='danger')
        else:
            messages.error(request, 'Please correct the error below.', extra_tags='danger')
    else:
        form = CandidateRegistrationForm(request.GET or None, instance=candidate)


    return render(request, 'manager_candidate.html', {'form': form, 'title': title})


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
                response += resumebot.run({'resume': chunk, 'question': question})

            interaction = Interaction.objects.create(user=user, candidate=candidate, question=question, response=response)
            timestamp = interaction.timestamp.strftime('%d/%m/%Y %H:%M:%S')
            return JsonResponse({
                'response': response,
                'timestamp': timestamp
            })
    return render(request, 'chat.html', {'candidate': candidate, 'interactions': interactions})
