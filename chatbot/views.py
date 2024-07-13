from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Candidate, ExternalUser, Interaction
from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.text_splitter import CharacterTextSplitter

# Initialize chatbot once and reuse it
def initialize_chatbot():
    prompt_template = """
    You are a chatbot that will answer questions in the first person, as if you were responding to an interviewer or recruiter.
    Your answers should always be honest, clear, and objective.
    It is important that the answers are precise.
    If you do not know how to answer a question, ask the interviewer to contact the interviewee directly.
    You have access to the interviewee's resume and the interviewer's question.
    Use the information available in the resume to provide detailed and relevant answers.
    
    First, identify the language of the user's question.
    Then, answer the question in the same language.

    Resume:
    {curriculum}

    Question:
    {question}

    Answer in the detected language:
    """

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=['curriculum', 'question']
    )

    llm = OpenAI()
    chain = LLMChain(llm=llm, prompt=prompt)
    print('######### Inicializou')
    return chain

# Global variable to hold the initialized chatbot
chatbot = initialize_chatbot()


def about(request):
    return render(request, 'about.html')

def get_or_create_external_user(request):
    user_id = request.session.get('user_id')
    if not user_id:
        name = request.POST.get('name')
        email = request.POST.get('email')
        user = ExternalUser.objects.create(name=name, email=email)
    else:
        user = ExternalUser.objects.get(id=user_id)

    request.session['user_id'] = user.id
    request.session['user_name'] = user.name
    return user


def candidates(request):
    candidates = Candidate.objects.all()
    return render(request, 'candidates.html', {'candidates': candidates})

def chat(request, slug):
    candidate = get_object_or_404(Candidate, slug=slug)
    curriculum_text = candidate.resume
    if request.method == 'POST':
        user = get_or_create_external_user(request)
        question = request.POST.get('question')
        if question:
            text_splitter = CharacterTextSplitter(chunk_size=2000, chunk_overlap=0)
            chunks = text_splitter.split_text(curriculum_text)
            response = ''
            for chunk in chunks:
                response += chatbot.run({'curriculum': chunk, 'question': question})

            # Salvar a interação no banco de dados
            interaction = Interaction.objects.create(external_user=user, candidate=candidate, question=question, response=response)
            timestamp = interaction.timestamp.strftime('%d/%m/%Y %H:%M:%S')
            return JsonResponse({
                'response': response,
                'user': user.name,
                'candidate': candidate.name,
                'timestamp': timestamp
            })
    user_name = request.session.get('user_name')
    return render(request, 'chat.html', {'candidate': candidate, 'user_name': user_name})
