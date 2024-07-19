from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import OpenAI

def initialize_extraction_prompt():
    prompt_template = """
    You are an AI that extracts structured information from resumes.
    Your task is to extract the following information from the given resume and return it in a JSON format:
    - Name
    - Email
    - Phone number
    - LinkedIn profile
    - Education
    - Work experience
    - Skills

    Resume:
    {resume}

    Extracted Information (in JSON format):
    """
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=['resume']
    )
    llm = OpenAI()
    chain = LLMChain(llm=llm, prompt=prompt)
    print('######### Extraction prompt initialized')
    return chain

# Initialize the extraction prompt once and reuse it
extraction_prompt = initialize_extraction_prompt()


def initialize_resumebot():
    prompt_template = """
    You are a chatbot that answers questions in the first person, as if you were the interviewee.
    Your answers should always be honest, clear, and objective.
    It is important that the answers are precise and reflect the information available in the resume.
    If you do not know how to answer a question based on the resume, simply say "I do not have information on that topic in my resume."
    
    Assume the identity of the interviewee and answer the following question based on the resume provided.

    Resume:
    {resume}

    Question:
    {question}

    Answer as the interviewee:
    """

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=['resume', 'question']
    )

    llm = OpenAI()
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain

# Global variable to hold the initialized chatbot
resumebot = initialize_resumebot()
