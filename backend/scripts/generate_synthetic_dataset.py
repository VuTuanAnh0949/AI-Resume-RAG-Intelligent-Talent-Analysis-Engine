import argparse
import json
from pathlib import Path
from fpdf import FPDF
from faker import Faker

# Setup Faker
fake = Faker('en_US')

# Configuration
PROJECT_ROOT = Path(__file__).resolve().parents[2] # 2 levels up: scripts -> backend -> project_root
SOURCE_DATASET_DIR = PROJECT_ROOT / "Resume_Dataset" / "data" / "INFORMATION-TECHNOLOGY"
TEXT_DIR = PROJECT_ROOT / "data" / "text"

# Ensure target directory exists
SOURCE_DATASET_DIR.mkdir(parents=True, exist_ok=True)

class ResumePDF(FPDF):
    def header(self):
        pass # No header
        
    def footer(self):
        pass # No footer

def create_synthetic_resume(original_id: str, raw_text: str):
    # 1. Generate Fake Personal Data
    fake_name = fake.name()
    # Ensure name has no weird titles to test pure name extraction
    fake_name = fake_name.replace("Mr. ", "").replace("Mrs. ", "").replace("Dr. ", "").replace("Miss ", "").replace("Ms. ", "")
    
    fake_email = f"{fake_name.split()[0].lower()}.{fake_name.split()[-1].lower()}@example.com"
    fake_phone = fake.phone_number()

    # 2. Prepare the new text content
    lines = raw_text.splitlines()
    body_text = "\n".join(lines[3:] if len(lines) > 3 else lines)
    
    # 3. Create PDF
    pdf = ResumePDF()
    pdf.add_page()
    
    pdf.set_font("Helvetica", size=11)
    
    # Write Header (Personal Info)
    pdf.set_font("Helvetica", style="B", size=16)
    pdf.cell(0, 10, fake_name, new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 5, f"Email: {fake_email} | Phone: {fake_phone}", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.cell(0, 10, "", new_x="LMARGIN", new_y="NEXT") # Spacer
    
    # Write Body
    pdf.set_font("Helvetica", size=11)
    
    # Replace common unicode bullet points with standard ASCII hyphen to preserve layout
    # because standard fpdf fonts don't support complex unicode.
    clean_body = body_text.replace('•', '-').replace('▪', '-').replace('·', '-')
    
    # Also clean out weird replacement characters that might have snuck in during extraction
    clean_body = clean_body.replace('ï¼', '- ')
    
    # Final encoding step to prevent fpdf crashes on any remaining weird chars
    clean_body = clean_body.encode('latin-1', 'replace').decode('latin-1')
    
    # Process line by line to preserve formatting and bullet points
    for line in clean_body.splitlines():
        line = line.strip()
        if not line:
            pdf.cell(0, 4, "", new_x="LMARGIN", new_y="NEXT") # Empty line
            continue
            
        # If it's a bullet point, draw it with an indent
        if line.startswith("-") or line.startswith("*") or line.startswith("?"):
            pdf.set_x(15) # Indent
            # Replace the starting char with a consistent bullet-like hyphen
            clean_line = "- " + line[1:].strip()
            pdf.multi_cell(0, 6, clean_line)
        elif line.isupper() and len(line) < 50:
            pdf.ln(2)
            pdf.set_font("Helvetica", style="B", size=12)
            pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=11)
        else:
            pdf.set_x(10) # Reset indent
            pdf.multi_cell(0, 6, line)
    
    # 4. Save PDF
    target_filename = f"AST_{original_id}.pdf"
    target_path = SOURCE_DATASET_DIR / target_filename
    pdf.output(str(target_path))
    
    print(f"Created: {target_filename} (Name: {fake_name})")
    
    return {
        "id": f"AST_{original_id}",
        "original_id": original_id,
        "injected_data": {
            "name": fake_name,
            "email": fake_email,
            "phone": fake_phone
        }
    }

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic resumes with injected personal data.")
    parser.add_argument(
        "--limit", 
        type=int, 
        default=20, 
        help="Number of synthetic resumes to generate (default: 20)"
    )
    args = parser.parse_args()

    print(f"Generating synthetic dataset in: {SOURCE_DATASET_DIR}")
    
    if not TEXT_DIR.exists():
        print(f"Error: Text directory {TEXT_DIR} not found. Please run ingestion first to extract text.")
        return

    text_files = list(TEXT_DIR.glob("*.txt"))
    
    if not text_files:
        print("No extracted text files found in data/text. Please ingest the original dataset first.")
        return
        
    limit = min(args.limit, len(text_files))
    print(f"Processing {limit} files out of {len(text_files)} available...")
    text_files = text_files[:limit]
    
    ground_truth = []
    
    for txt_path in text_files:
        original_id = txt_path.stem
        raw_text = txt_path.read_text(encoding="utf-8")
        
        try:
            meta = create_synthetic_resume(original_id, raw_text)
            ground_truth.append(meta)
        except Exception as e:
            print(f"Failed to create PDF for {original_id}: {e}")

    gt_path = SOURCE_DATASET_DIR / "ground_truth.json"
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)
        
    print(f"\nDone! Generated {len(ground_truth)} synthetic PDFs.")
    print(f"Ground truth saved to: {gt_path}")

if __name__ == "__main__":
    main()