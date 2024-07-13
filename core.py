from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.text_splitter import CharacterTextSplitter


def load_curriculum(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


def create_chatbot(curriculum_text):
    # Define a template para o prompt
    prompt_template = """
    Você é um chatbot que responderá perguntas em primeira pessoa, como se estivesse respondendo a um entrevistador ou recrutador. 
    Suas respostas devem ser sempre honestas, claras e objetivas. 
    É importante que as respostas sejam precisas. 
    Se não souber responder alguma pergunta, peça para o entrevistador entrar em contato diretamente com o entrevistado. 
    Você tem acesso ao currículo do entrevistado e à pergunta do entrevistador. 
    Use as informações disponíveis no currículo para fornecer respostas detalhadas e relevantes.

    Currículo:
    {curriculum}

    Pergunta:
    {question}

    Resposta:
    """

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["curriculum", "question"]
    )

    # Inicialize o modelo OpenAI
    llm = OpenAI()

    # Crie a cadeia LLM
    chain = LLMChain(llm=llm, prompt=prompt)

    return chain


def main():
    # Carregar o currículo
    curriculum_text = load_curriculum('chatbot/fixtures/rafael_CV.json')

    # Criar o chatbot
    chatbot = create_chatbot(curriculum_text)

    # Loop para fazer perguntas
    while True:
        question = input("Faça uma pergunta sobre o currículo (ou digite 'sair' para encerrar): ")
        if question.lower() == 'sair':
            break

        # Dividir o texto do currículo se for muito longo
        text_splitter = CharacterTextSplitter(chunk_size=2000, chunk_overlap=0)
        chunks = text_splitter.split_text(curriculum_text)

        # Processar cada chunk
        for chunk in chunks:
            response = chatbot.run({"curriculum": chunk, "question": question})
            print(response)


if __name__ == "__main__":
    main()
