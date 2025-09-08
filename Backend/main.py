# backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict
import uuid, json, re, os, pdfkit
from jinja2 import Template
import openai

# --- Set OpenAI API Key ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise EnvironmentError("Set OPENAI_API_KEY in environment variables")
openai.api_key = OPENAI_API_KEY

app = FastAPI(title="Full AI Research Agent")
PDF_DIR = "pdf"
os.makedirs(PDF_DIR, exist_ok=True)

# --- Models ---
class Subsection(BaseModel):
    h3: str
    paragraphs: List[str]
    image_url: str = None

class Section(BaseModel):
    header: str
    intro: str
    subsections: List[Subsection]
    image_url: str = None

class Source(BaseModel):
    url: str
    title: str

class CombinedReport(BaseModel):
    title: str
    subtitle: str
    sections: List[Section]
    sources: List[Source]

class ClarifyRequest(BaseModel):
    session_id: str = None
    user_input: str = None

class AnswerRequest(BaseModel):
    session_id: str
    answers: Dict[str,str]

# --- In-memory sessions ---
sessions = {}

# --- Helpers ---
def strip_markdown(text: str) -> str:
    return re.sub(r'[*#_>`~]', '', text).strip()

def generate_ai_image(prompt: str) -> str:
    response = openai.Image.create(
        prompt=prompt,
        n=1,
        size="1024x1024"
    )
    return response.data[0].url

def generate_clarifying_questions(topic: str) -> List[str]:
    prompt = f"""
    You are an expert research assistant.
    Help the user refine their research topic: "{topic}".
    Generate up to 8 clarifying questions that will help collect detailed context.
    Respond as a JSON array of questions only.
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role":"user","content":prompt}],
        temperature=0
    )
    text = response.choices[0].message.content
    return json.loads(text)

def synthesize_refined_topic(answers: Dict[str,str]) -> str:
    answers_text = "\n".join([f"{q}: {a}" for q,a in answers.items()])
    prompt = f"""
    You are an expert research assistant.
    Based on the following Q&A, generate a concise refined research topic:
    {answers_text}
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role":"user","content":prompt}],
        temperature=0
    )
    return response.choices[0].message.content.strip()

def generate_structured_report(refined_topic: str) -> CombinedReport:
    prompt = f"""
    Using the topic "{refined_topic}", generate a detailed research report.
    Respond in the following JSON structure:

    {{
      "title":"Title of report",
      "subtitle":"Compelling one line hook",
      "sections":[{{ "header":"H2 header","intro":"Intro paragraph","subsections":[{{"h3":"H3 header","paragraphs":["para1","para2"]}}]}}],
      "sources":[{{"url":"https://example.com","title":"Source title"}}]
    }}
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role":"user","content":prompt}],
        temperature=0
    )
    report_json = json.loads(response.choices[0].message.content)
    return CombinedReport(**report_json)

# --- API Endpoints ---
@app.post("/start_session")
def start_session(req: ClarifyRequest):
    session_id = str(uuid.uuid4())
    questions = generate_clarifying_questions(req.user_input)
    sessions[session_id] = {"questions": questions, "answers": {}}
    return {"session_id": session_id, "questions": questions}

@app.post("/submit_answers")
def submit_answers(req: AnswerRequest):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    sessions[req.session_id]["answers"] = req.answers
    refined_topic = synthesize_refined_topic(req.answers)
    return {"refined_topic": refined_topic}

@app.post("/generate_report")
def generate_report(refined_topic: str):
    report = generate_structured_report(refined_topic)

    # Generate AI images for sections/subsections
    for sec in report.sections:
        sec.image_url = generate_ai_image(sec.intro)
        for sub in sec.subsections:
            sub.image_url = generate_ai_image(" ".join(sub.paragraphs))

    # Strip markdown
    report.title = strip_markdown(report.title)
    report.subtitle = strip_markdown(report.subtitle)

    # Render HTML
    html_template = """
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{{ report.title }}</title></head><body>
    <h1>{{ report.title }}</h1><p>{{ report.subtitle }}</p>
    {% for section in report.sections %}
      <h2>{{ section.header }}</h2><p>{{ section.intro }}</p>
      {% if section.image_url %}<img src="{{ section.image_url }}">{{% endif %}
      {% for sub in section.subsections %}
        <h3>{{ sub.h3 }}</h3>
        {% if sub.image_url %}<img src="{{ sub.image_url }}">{{% endif %}
        {% for p in sub.paragraphs %}<p>{{ p }}</p>{% endfor %}
      {% endfor %}
    {% endfor %}
    <h2>Sources</h2>
    <ul>{% for s in report.sources %}<li><a href="{{ s.url }}">{{ s.title }}</a></li>{% endfor %}</ul>
    </body></html>
    """
    template = Template(html_template)
    html_content = template.render(report=report)

    # Generate PDF
    pdf_file = os.path.join(PDF_DIR, f"{uuid.uuid4().hex}.pdf")
    pdfkit.from_string(html_content, pdf_file)

    return {"html_content": html_content, "pdf_path": pdf_file, "report_json": report.dict()}

@app.get("/pdf_download")
def pdf_download(file_path: str):
    return FileResponse(file_path, media_type="application/pdf", filename="research_report.pdf")

