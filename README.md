# ResumeBot

ResumeBot is a web-based application designed to interact with users by answering questions about candidates' resumes. The project leverages state-of-the-art natural language processing and machine learning techniques to provide accurate and relevant responses. The chatbot is built using the Django framework and integrates with OpenAI's language models through LangChain.

## Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Technologies Used](#technologies-used)
- [Contributing](#contributing)
- [Gunicorn Configuration](#gunicorn-configuration)
- [Nginx Configuration](#nginx-configuration)
- [Quick Access Guide](#quick-access-guide)
- [File Permissions](#file-permissions)
- [Error Tracking](#error-tracking)
- [Protecting Files with Nginx](#protecting-files-with-nginx)

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
   # Localhost
   source ../venvs/chatbot/bin/activate
   # Digital Ocean
   source .venv/bin/activate 
   ```

3. **Install the required dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

4. **Set the OPENAI_API_KEY:**
    ```sh
    echo "export OPENAI_API_KEY='abcxyz'" >> ~/.bashrc
    ```

5. **Apply migrations and load initial data:**
   ```sh
   python manage.py migrate
   python manage.py loaddata initial_data.json
   ```

6. **Run the development server:**
   ```sh
   python manage.py runserver
   ```

7. **Access the application:**
   Open your web browser and navigate to `http://localhost:8001`.

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

## Gunicorn Configuration

1. **Locate the Gunicorn Executable:**
   The path to the executable is `/home/rafael/mychatbot/.venv/bin/gunicorn`.

2. **Create/Edit the Systemd Configuration File for Gunicorn:**
   The file is usually located at `/etc/systemd/system/mychatbot-gunicorn.service`.
   - **To edit:**
     `sudo nano /etc/systemd/system/mychatbot-gunicorn.service`
   
   - **Example content:**
     ```
     [Unit]
     Description=gunicorn daemon for mychatbot
     After=network.target

     [Service]
     User=rafael
     Group=rafael
     WorkingDirectory=/home/rafael/mychatbot
     ExecStart=/home/rafael/mychatbot/.venv/bin/gunicorn --workers=3 mychatbot.wsgi:application --bind 127.0.0.1:8001
     Environment="OPENAI_API_KEY=abc123"

     [Install]
     WantedBy=multi-user.target
     ```

3. **Reload and Restart Gunicorn via Systemd:**
   ```sh
   sudo systemctl daemon-reload
   sudo systemctl restart mychatbot-gunicorn
   ```

## Nginx Configuration

1. **Locate or Create the Configuration File for the Site:**
   The file path is usually `/etc/nginx/sites-available/mychatbot`.
   
   - **To edit:**
     `sudo nano /etc/nginx/sites-available/mychatbot`

2. **Create a Symbolic Link to Activate the Site:**
   ```sh
   sudo ln -s /etc/nginx/sites-available/mychatbot /etc/nginx/sites-enabled
   ```

3. **Check Configuration and Restart Nginx:**
   ```sh
   sudo nginx -t
   sudo systemctl restart nginx
   ```

## Quick Access Guide

1. **Restart Gunicorn and Nginx:**
   ```sh
   sudo systemctl daemon-reload & systemctl restart mychatbot-gunicorn && systemctl restart nginx
   ```

2. **Status of Gunicorn and Nginx:**
   ```sh
   sudo journalctl -u gunicorn
   sudo journalctl -u nginx
   ```

3. **View Logs:**
   ```sh
   sudo journalctl -u mychatbot-gunicorn -n 50 --no-hostname
   ```

4. **List Service Configuration:**
   ```sh
   sudo cat /etc/systemd/system/mychatbot-gunicorn.service
   sudo nano /etc/systemd/system/mychatbot-gunicorn.service
   ```

## File Permissions

1. **Change Ownership and Permissions for Static Directories and Files:**
   ```sh
   sudo chown -R rafael:www-data /home/rafael/mychatbot/mychatbot/deploy/static/
   sudo chmod -R 750 /home/rafael/mychatbot/mychatbot/deploy/static/
   ```

## Error Tracking

1. **Check Gunicorn Status/Log via Systemd:**
   ```sh
   sudo systemctl status mychatbot-gunicorn
   ```
   or
   ```sh
   journalctl -u mychatbot-gunicorn -n 50 --no-hostname
   ```

2. **Check Nginx Logs:**
   ```sh
   sudo tail -f /var/log/nginx/error.log
   ```

3. **Test Local Connection with Curl:**
   ```sh
   curl http://127.0.0.1:8001
   ```
   If a connection refused error occurs, restart Gunicorn.

## Protecting Files with Nginx

Configure Nginx to block direct access to a specific directory, in this case, `media/upload`.

1. **Locate the Nginx Configuration File:**
   ```sh
   sudo nano /etc/nginx/sites-available/mychatbot
   ```

2. **Add the Following Location Block Within the Server Block:**
   ```sh
   location /media/upload/ {
       deny all;
       return 403;
   }
   ```
   This configuration blocks all access to the directory and returns an HTTP 403 Forbidden error for any access attempts.

3. **Reload Nginx:**
   ```sh
   sudo systemctl reload nginx
   ```
   Now, any attempt to directly access files within `media/upload` will be blocked by Nginx. However, your Django application can still access and serve these files, bypassing this restriction.