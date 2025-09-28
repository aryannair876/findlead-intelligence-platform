# 🚀 FindLead Intelligence Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A production-ready, AI-native intelligence API with provider failover (Groq → OpenRouter → optional local Ollama) for lead generation, email analysis, and website intelligence.

## 🌟 Features

### 🧠 AI Analysis
- **Sentiment Analysis**: AI-driven sentiment and buying-intent analysis for emails and content
- **Email Intelligence**: Security validation, deliverability checks, and AI synthesis
- **Website Monitoring**: Comprehensive intelligence including security, performance, SEO, and accessibility analysis

### 🔄 Robust Infrastructure
- **Groq-Powered AI**: Fast and efficient LLM processing with Llama 3.1
- **Rate Limit Handling**: Smart retry logic and rate limiting
- **JSON Coercion**: Automatic response formatting and error handling
- **Caching System**: Built-in caching for improved performance

### 🚀 Production Ready
- **Single Entrypoint**: Minimal `app.py` ready for deployment
- **Environment Configuration**: Flexible provider setup via environment variables
- **Health Monitoring**: Built-in health checks and status endpoints

## 🏗️ Architecture

- **Flask API**: `app.py` exposes endpoints and renders minimal templates
- **AI Services**: `services/analysis_service.py` (Sentiment, Email, Website)
- **LLM Router**: `services/llm_router.py` (Groq integration with rate limiting)
- **Utilities**: Caching and rate limiting in `utils/`
- **Tools**: Specialized analysis tools in `tools/`

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **Git** (for cloning)
- **Groq API Key** (get yours free at [console.groq.com](https://console.groq.com))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/findlead-intelligence-platform.git
   cd findlead-intelligence-platform
   ```

2. **Create a virtual environment**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux  
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   # Copy the example environment file
   cp .env.example .env
   
   # Edit .env and add your Groq API key:
   # GROQ_API_KEY=your_groq_api_key_here
   ```

5. **Run the application**
   ```bash
   # Windows PowerShell
   $env:PORT=5002; python app.py
   
   # macOS/Linux/Windows CMD
   export PORT=5002 && python app.py  # or set PORT=5002 && python app.py
   ```

6. **Verify installation**
   - Visit: http://localhost:5002
   - Health check: http://localhost:5002/api/health

## 📊 API Endpoints

- POST /api/analyze-sentiment
- POST /api/validate-email
- POST /api/monitor-website
- POST /api/askspot-analysis (alias of monitor-website)
- GET  /api/health

## 📁 Structure

- app.py — single production entrypoint
- services/ — AI services and router
- utils/ — caching and rate limiter
- templates/ — minimal UI pages
- config/, tools/, data/ — existing assets retained

## 🔐 Notes

- **Fast AI Processing**: Powered by Groq's high-performance inference infrastructure
- **Smart Rate Limiting**: Automatic retry logic handles rate limits gracefully  
- **JSON Coercion**: Responses are automatically formatted and validated
- **Caching**: Built-in caching system improves response times and reduces API costs

## 📄 License

MIT
