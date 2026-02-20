import sys
import subprocess
import codecs

try:
    import PyPDF2
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyPDF2", "--quiet"])
    import PyPDF2

try:
    import docx
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx", "--quiet"])
    import docx

def read_pdf(file_path):
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        text = ''
        for page in reader.pages:
            text += page.extract_text() + '\n'
        return text

def read_docx(file_path):
    doc = docx.Document(file_path)
    return '\n'.join([para.text for para in doc.paragraphs])

with codecs.open(r"C:\Users\rblos\datascience\Deuces\notebooks\sandbox\docs_output.txt", "w", "utf-8") as out:
    out.write("=== TEAM PROJECT INSTRUCTIONS ===\n")
    out.write(read_pdf(r"C:\Users\rblos\datascience\Deuces\GUIDENCE\Team Project Instructions.pdf"))
    out.write("\n=== BASE CASE 1 ===\n")
    out.write(read_docx(r"C:\Users\rblos\datascience\Deuces\GUIDENCE\Base Case 1.docx"))
