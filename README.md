# GEN//SMART - JSON Profile Generator v3.3 with LLM support

<img width="1319" height="806" alt="image" src="https://github.com/user-attachments/assets/ccc65ae0-1818-41ba-8301-c9beeb7c9fd8" />



> // PROXY-BASED IDENTITY SYNTHESIS //

Welcome to the Generator. This isn't just a Python/Flask app; it's a retro-cyberpunk terminal wrapped in a Docker container, designed to synthesize profiles with style. It features a CRT-like violet UI, blinky cursors, and LLM-powered logic under the hood.

![Terminal Vibes](https://img.shields.io/badge/Vibes-Cyberpunk-purple) ![Dockerized](https://img.shields.io/badge/Runs%20on-Docker-blue) ![Flask](https://img.shields.io/badge/Powered%20By-Flask-black)

## ✨ Features

- **Proxy-Based Generation:** Smart proxy allocation with duplicate allowances and max-reuse limits.
- **LLM Integration:** Modify interests and shrink intentions using the power of Large Language Models.
- **Retro UI:** A terminal-style interface with scanlines, Orbitron fonts, and zero boring Bootstrap.
- **Dockerized:** Isolated, predictable, and easy to deploy.

## 🚀 Quick Start (Docker)

Make sure you have your `proxy` and `profiles` directories set up (the app expects them to exist, even if empty).

1. **Build and run the container:**
   bash
   docker-compose up -d --build
   
2.   The app will internally wake up on port 8182.

## 🌐 Reverse Proxy Setup (Angie / Nginx) 
If you want to expose the generator to the web under a virtual subfolder (e.g., http://your-domain.com:8080/generator/), you'll need a reverse proxy. Here is a battle-tested config for Angie (or Nginx).

**Note**: The /static/ block is crucial. Since the Flask app runs at the root of its container, asking for CSS/JS from /generator/static/ will result in 404s. This config gracefully handles that.

## Configuration (suggested)

server {     listen 8080;
    server_name NAME;
    access_log /var/log/angie/tarja.access.log;
    error_log  /var/log/angie/tarja.error.log;

    # Main app route (if you have other stuff running)
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # The Generator route
    location /generator/ {
        proxy_pass http://127.0.0.1:8182/;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Generation might take time (LLM calls, etc.)
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        proxy_cache off;
        proxy_store off;
    }

    # IMPORTANT: Proxying Flask static files
    # Browsers will request absolute paths like /static/css/style.css
    location /static/ {
        proxy_pass http://127.0.0.1:8182/static/;
    } 	}

**CRITICAL NOTE for v3.3+** : To make the live progress bar and System Log stream properly, you must disable proxy buffering and use HTTP/1.1. Here is the updated, battle-tested config for Angie (or Nginx).

server {	listen 8080;
    server_name NAME;
    access_log /var/log/angie/hoho.access.log;
    error_log  /var/log/angie/hoho.error.log;

    # Main app route (if you have other stuff running)
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # The Generator route
    location /generator/ {
        proxy_pass http://127.0.0.1:8182/;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # IMPORTANT: Required for SSE (Server-Sent Events) streaming!
        proxy_buffering off;
        proxy_http_version 1.1;
        proxy_set_header Connection '';

        # Timeouts (Generation + LLM calls can take a while)
        proxy_connect_timeout 10s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        proxy_cache off;
        proxy_store off;
    }

    # IMPORTANT: Proxying Flask static files
    # Browsers will request absolute paths like /static/css/style.css
    location /static/ {
        proxy_pass http://127.0.0.1:8182/static/;
    }	}

## 🛠 How LLM Key Rotation Works

Place your API keys in mistral.txt or llm7.io.txt (one per line). Empty lines are ignored automatically.
If a key fails (e.g., 401 Unauthorized or rate limit), the app instantly falls back to the next key in the list.
On a successful request, the used key is moved to the back of the queue (Round-Robin), ensuring even distribution of API limits.
All errors are streamed directly into the UI System Log in vivid red, so you know exactly which key failed and why.

💜 **Acknowledgements**
Made with coffee and love to violet colours.
