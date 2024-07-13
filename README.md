Primeiro, crie sua KEY_API no site da OpenAI

Depois sete no seu ambiente a variável, através da chave KEY.

Exemplo no Ubunto/Mac

echo "export OPENAI_API_KEY='abcxyz'" >> ~/.zshrc

Em seguida carregue a variável cadastrada

source ~/.zshrc

Com um script simples, você já conseguirá visualizar se a variável está ativa:

python core.py

import os
print(os.environ.get("OPENAI_API_KEY"))


Visualizando a variável cadastrada, você já poderá chamar o código inicial da OpenAI, que por padrão tentará chamar a variável setada no seu ambiente.


from openai import OpenAI
client = OpenAI()