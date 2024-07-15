from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import OpenAI

def initialize_chatbot():
    prompt_template = """
    You are a chatbot that will answer questions in the first person, as if you were responding to an interviewer or recruiter.
    Your answers should always be honest, clear, and objective.
    It is important that the answers are precise.
    If you do not know how to answer a question, ask the interviewer to contact the interviewee directly.
    You have access to the interviewee's resume and the interviewer's question.
    Use the information available in the resume to provide detailed and relevant answers.

    Resume:
    {curriculum}

    Question:
    {question}

    Answer:
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
