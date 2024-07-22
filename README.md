# ResumeBot

ResumeBot is a web-based application designed to interact with users by answering questions about candidates' resumes. The project leverages state-of-the-art natural language processing and machine learning techniques to provide accurate and relevant responses. The chatbot is built using the Django framework and integrates with OpenAI's language models through LangChain.

## Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Technologies Used](#technologies-used)
- [Contributing](#contributing)

## Project Overview

ResumeBot aims to provide an interactive platform where users can ask questions about candidates' resumes and receive precise and informative answers. It is particularly useful for recruiters and interviewers who need quick access to detailed information about candidates.

## Features

- User identification through name and email
- Interactive chat interface to ask questions about candidates' resumes
- Real-time response generation using OpenAI's language models
- Logging and recording of user interactions
- Personalized responses based on resume data

## Installation

To set up ResumeBot locally, follow these steps:


1. **Clone the repository:**
   ```sh
   git clone git@github.com:rrafaelpinto/mychatbot.git
   cd mychatbot
   ```

2. **Create and activate a virtual environment:**
   ```sh
   python -m venv chatbot
   source ../venvs/chatbot/bin/activate
   ```

3. **Install the required dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
   
4. **Set the OPENAI_API_KEY:**
    ```sh
    echo "export OPENAI_API_KEY='abcxyz'" >> ~/.zshrc
    ```

5. **Installing Node.js:**
   ```sh
   sudo apt update
   sudo apt install nodejs
   sudo apt install npm
   ```

6. **Apply migrations and load initial data:**
   ```sh
   python manage.py migrate
   python manage.py loaddata initial_data.json
   ```

7. **Run the development server:**
   ```sh
   python manage.py runserver
   ```

8. **Access the application:**
   Open your web browser and navigate to `http://localhost:8000`.

9. **Add/Show/Remove crontab:**
   ```sh
    python manage.py crontab add
    python manage.py crontab show
    python manage.py crontab remove
   ```

## Usage

1. **User Identification:**
   - When you first access the chatbot, you will be prompted to enter your name and email.
   - This information helps personalize your experience and log your interactions.

2. **Ask Questions:**
   - Once identified, you can start asking questions about the candidate's resume.
   - Type your question in the chat interface and hit 'Send'.
   - The chatbot will respond in real-time using data from the candidate's resume.

## Technologies Used

- **Python:** The main programming language used in the project.
- **Django:** A high-level Python web framework that enables rapid development and clean, pragmatic design.
- **LangChain:** A framework for developing applications using large language models.
- **OpenAI:** Provides the language models used for generating responses.
- **jQuery:** For handling asynchronous requests and updating the chat interface dynamically.
- **Bootstrap:** For responsive design and styling of the application.

## Contributing

We welcome contributions to improve ResumeBot. If you would like to contribute, please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature-name`).
3. Make your changes.
4. Commit your changes (`git commit -am 'Add some feature'`).
5. Push to the branch (`git push origin feature/your-feature-name`).
6. Open a Pull Request.