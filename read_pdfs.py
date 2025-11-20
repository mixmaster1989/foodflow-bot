import pypdf
import os

files = [
    r"c:\Users\master\tgbotikar-2\FoodFlow_Final_Summary.pdf",
    r"c:\Users\master\tgbotikar-2\FoodFlow_Complete_Concept.pdf"
]

output_file = r"c:\Users\master\tgbotikar-2\pdf_content_utf8.txt"

with open(output_file, "w", encoding="utf-8") as f:
    for file_path in files:
        f.write(f"--- READING {os.path.basename(file_path)} ---\n")
        try:
            reader = pypdf.PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            f.write(text)
        except Exception as e:
            f.write(f"Error reading {file_path}: {e}\n")
        f.write("\n" + "="*50 + "\n")

print("Done writing to pdf_content_utf8.txt")
