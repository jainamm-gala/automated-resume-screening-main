from flask import Flask, request, jsonify, render_template
import os
import re
import json
from transformers import pipeline
from werkzeug.utils import secure_filename
import PyPDF2
from docx import Document
import matplotlib.pyplot as plt
from io import BytesIO
import base64

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Load job roles and keywords dynamically from JSON file
JOB_ROLES_FILE = "job_roles.json"
with open(JOB_ROLES_FILE, "r") as file:
    JOB_ROLES = json.load(file)

# Pre-trained BERT-based classifier
classifier = pipeline('zero-shot-classification', model='facebook/bart-large-mnli')

def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, "rb") as f:
        pdf_reader = PyPDF2.PdfReader(f)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def extract_text_from_docx(file_path):
    document = Document(file_path)
    text = " ".join([paragraph.text for paragraph in document.paragraphs])
    return text

def match_keywords(resume_text, job_keywords):
    matched_keywords = [kw for kw in job_keywords if re.search(rf"\b{kw}\b", resume_text.lower())]
    return matched_keywords

def create_bar_chart(keyword_results):
    roles = list(keyword_results.keys())
    scores = [keyword_results[role]['score'] for role in roles]

    plt.figure(figsize=(10, 6))
    plt.barh(roles, scores, color='skyblue')
    plt.xlabel('Matching Score (%)')
    plt.ylabel('Job Roles')
    plt.title('Keyword Matching Scores by Job Role')
    plt.tight_layout()

    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close()
    return plot_url

@app.route("/")
def index():
    return render_template("index.html", job_roles=list(JOB_ROLES.keys()))

@app.route("/upload", methods=["POST"])
def upload_file():
    if "resume" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["resume"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(file.filename))
    file.save(file_path)

    # Extract text from the uploaded file
    if file.filename.endswith(".pdf"):
        resume_text = extract_text_from_pdf(file_path)
    elif file.filename.endswith(".docx"):
        resume_text = extract_text_from_docx(file_path)
    else:
        return jsonify({"error": "Unsupported file format. Please upload a PDF or DOCX file."}), 400

    # Perform keyword matching
    keyword_results = {}
    for role, keywords in JOB_ROLES.items():
        matched_keywords = match_keywords(resume_text, keywords)
        keyword_results[role] = {
            "matched_keywords": matched_keywords,
            "total_keywords": len(keywords),
            "score": round(len(matched_keywords) / len(keywords) * 100, 2)
        }

    # Generate bar chart for visualization
    plot_url = create_bar_chart(keyword_results)

    # Perform BERT-based classification
    bert_results = classifier(resume_text, list(JOB_ROLES.keys()), multi_class=True)

    return render_template(
        "results.html",
        resume_text=resume_text,
        keyword_results=keyword_results,
        bert_results=bert_results,
        plot_url=plot_url,
        zip=zip  # Pass the zip function to the template context
    )

if __name__ == "__main__":
    app.run(debug=True)
