from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Candidate
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
    Then, answer all subsequent questions in the same language.

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
    return chain

# Global variable to hold the initialized chatbot
chatbot = initialize_chatbot()


def candidate_list_view(request):
    candidates = Candidate.objects.all()
    return render(request, 'candidate_list.html', {'candidates': candidates})

def chatbot_view(request, slug):
    candidate = get_object_or_404(Candidate, slug=slug)
    curriculum_text = candidate.resume

    if request.method == 'POST':
        question = request.POST.get('question')
        if question:
            text_splitter = CharacterTextSplitter(chunk_size=2000, chunk_overlap=0)
            chunks = text_splitter.split_text(curriculum_text)
            response = ''
            for chunk in chunks:
                response += chatbot.run({'curriculum': chunk, 'question': question})
            return JsonResponse({'response': response})

    return render(request, 'chatbot.html', {'candidate': candidate})
