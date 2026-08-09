import sys
from pathlib import Path

base_dir = Path(__file__).resolve().parent
sys_path_filtered = [p for p in sys.path if p != '' and Path(p).resolve() != base_dir]
sys.path = sys_path_filtered
import docx

def humanize_text(text):
    if not text or len(text.strip()) < 10:
        return text
        
    replacements = [
        ("Furthermore,", "Also,"),
        ("Furthermore ", "In addition, "),
        ("Additionally,", "Besides,"),
        ("Additionally ", "In addition, "),
        ("Moreover,", "Along with this,"),
        ("Moreover ", "Also, "),
        ("Therefore,", "Thus,"),
        ("Hence,", "So,"),
        ("Consequently,", "As a result,"),
        ("It is worth noting that", "Note that"),
        ("It should be noted that", "Importantly,"),
        ("pose a severe threat to", "severely damage"),
        ("economically vital", "important income"),
        ("a significant barrier to adoption", "a major hurdle for adoption"),
        ("In conclusion,", "To sum up,"),
        ("In summary,", "Overall,"),
        ("Recent progress in artificial intelligence", "Recent advancements in AI"),
        ("Traditionally, farmers depend on", "For a long time, farmers relied on"),
        ("Historically, farmers have relied on", "In the past, farmers relied on"),
        ("A clear need exists for", "There is a pressing need for"),
        ("The primary focus of this study is", "This study focuses on"),
        ("This study holds practical and academic significance for several reasons:", "This project is significant for several key reasons:"),
        ("Improves agricultural productivity and food security:", "Boosts farm yields and food security:"),
        ("Builds farmer trust through explainable AI:", "Enhances trust with visual explainability:"),
        ("Addresses technical limitations of existing solutions:", "Solves technical flaws of prior methods:"),
        ("Reduces engineering overhead through cross-platform development:", "Lowers software development overhead:"),
        ("Enables offline functionality for resource constrained settings:", "Operates completely offline without internet:"),
        ("plays a pivotal role", "is important"),
        ("testament to", "proof of"),
        ("delves into", "examines"),
        ("paradigm shift", "major shift"),
        ("cutting-edge", "advanced"),
        ("robust", "reliable"),
        ("comprehensive", "thorough"),
    ]
    
    res = text
    for old, new in replacements:
        res = res.replace(old, new)
    return res

def run():
    doc_path = base_dir / "crop_disease_detection.docx"
    doc = docx.Document(str(doc_path))

    count = 0
    for p in doc.paragraphs:
        orig = p.text
        new_txt = humanize_text(orig)
        if orig != new_txt:
            p.text = new_txt
            count += 1

    doc.save(str(doc_path))
    print(f"Humanized {count} paragraphs across the document successfully!")

if __name__ == '__main__':
    run()
