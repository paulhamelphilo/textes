import os
import re
import shutil
import time
import sys
import pypdf
import google.generativeai as genai

# Reconfigure stdout for UTF-8 to support French accents in Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

# Directories
SOURCE_PDF_DIR = r"C:\Users\paulh\Desktop\_Extraits élèves"
PROJECT_DIR = r"C:\Users\paulh\OneDrive\DOCUMENTS DE TRAVAIL\AI WORK\Textes-approfondissement"
DATA_DIR = os.path.join(PROJECT_DIR, "data")
TEXTS_DIR = os.path.join(DATA_DIR, "texts")
PDF_DIR = os.path.join(PROJECT_DIR, "pdf")
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
RAW_OCR_FILE = os.path.join(SCRIPTS_DIR, "raw_ocr.txt")
DATABASE_TSV = os.path.join(DATA_DIR, "database.tsv")

# Official Philosophy Curriculum Notions
OFFICIAL_NOTIONS = [
    "L'art", "Le bonheur", "La conscience", "Le devoir", "L'État", 
    "L'inconscient", "La justice", "Le langage", "La liberté", "La nature", 
    "La raison", "La religion", "La science", "La technique", "Le temps", 
    "Le travail", "La vérité"
]

# Configure Gemini
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("Warning: GEMINI_API_KEY environment variable is not set. API calls will fail.")
else:
    genai.configure(api_key=API_KEY)

def normalize_text_for_match(text):
    """Normalize text for matching (lowercase, no space, no punctuation, replace curly apostrophe)"""
    if not text:
        return ""
    text = text.lower().replace("’", "'").replace("œ", "oe")
    text = re.sub(r"[^a-z0-9]", "", text)
    return text

def parse_raw_ocr():
    """Parse raw_ocr.txt and return a dictionary indexed by normalized (Author, Themes)"""
    if not os.path.exists(RAW_OCR_FILE):
        print(f"Warning: {RAW_OCR_FILE} not found. Starting with empty database seed.")
        return {}

    with open(RAW_OCR_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into blocks by lines starting with digits followed by dot (e.g. 100. or 101. etc.)
    # We use regex to find lines starting with \d+\.
    lines = content.splitlines()
    blocks = []
    current_block = []
    
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+\.", stripped):
            if current_block:
                blocks.append(current_block)
            current_block = [line]
        else:
            if current_block or stripped: # only add if we started a block or if it's not empty
                current_block.append(line)
    if current_block:
        blocks.append(current_block)

    database_seed = {}
    
    for block in blocks:
        block_text = "\n".join(block)
        
        # 1. Parse header (lines before "Titre:")
        header_lines = []
        titre_idx = -1
        for idx, line in enumerate(block):
            if "Titre:" in line:
                titre_idx = idx
                break
            header_lines.append(line)
        
        if titre_idx == -1:
            # Skip invalid blocks
            continue
            
        header = " ".join(header_lines).strip()
        # Clean header to get filename key
        # Ex: "100.AFEISSA_Éthique environnementale"
        # Match number, author, themes
        header_match = re.match(r"^(\d+)\.([^_]+)_(.*)$", header.replace(" ", "").replace("\n", ""))
        if not header_match:
            # Fallback split
            header_clean = header.replace("\n", " ").strip()
            parts = header_clean.split("_", 1)
            if len(parts) == 2:
                author_part = parts[0]
                themes_part = parts[1]
                author = author_part.split(".", 1)[-1].strip()
                themes = themes_part.strip()
            else:
                continue
        else:
            author = header_match.group(2).strip()
            themes = header_match.group(3).strip()
            
        if author.upper() == "DE" and "_" in themes:
            author_extra, themes = themes.split("_", 1)
            author = f"DE {author_extra}"
            
        # Create match key
        author_norm = normalize_text_for_match(author)
        themes_norm = normalize_text_for_match(themes)
        
        # Remove suffixes like _c, _court, _complet from match key
        themes_norm = re.sub(r"(c|court|complet|introduction|intro)$", "", themes_norm)
        match_key = (author_norm, themes_norm)
        
        # 2. Extract Analysis (Titre, Thèse, Résumé) and Notions
        analysis_text = "\n".join(block[titre_idx:])
        
        # Find Titre, Thèse, Résumé tags
        titre_m = re.search(r"Titre:(.*?)(Thèse:|$)", analysis_text, re.DOTALL)
        these_m = re.search(r"Thèse:(.*?)(Résumé:|$)", analysis_text, re.DOTALL)
        
        titre_val = titre_m.group(1).strip() if titre_m else ""
        these_val = these_m.group(1).strip() if these_m else ""
        
        # Résumé starts from "Résumé:" up to the notions list
        resume_m = re.search(r"Résumé:(.*)$", analysis_text, re.DOTALL)
        resume_full = resume_m.group(1).strip() if resume_m else ""
        
        # Notions are at the end. We will find them by scanning the last few lines or checking
        # if the last lines consist primarily of comma-separated notions.
        # Let's clean the notions from the end of the resume
        notions_list = []
        resume_clean_lines = []
        
        # Split resume lines from the bottom to extract notions
        resume_lines = resume_full.splitlines()
        is_notions_part = True
        
        for line in reversed(resume_lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # Check if this line looks like a list of notions
            # (e.g. contains words from OFFICIAL_NOTIONS, separated by commas)
            cleaned_line = line_stripped.replace(",", " ").replace("L'art", "").replace("L’art", "")
            words = [normalize_text_for_match(w) for w in line_stripped.split(",")]
            
            # Verify if at least one word matches an official notion
            has_notion = False
            for w in words:
                if any(normalize_text_for_match(n) in w for n in OFFICIAL_NOTIONS):
                    has_notion = True
                    break
            
            if is_notions_part and (has_notion or line_stripped == "La justice" or line_stripped == "La vérité"):
                # Extract notions from this line
                for part in line_stripped.split(","):
                    part_clean = part.strip().strip(".")
                    if part_clean:
                        # Normalize to official spelling
                        matched_notion = None
                        part_norm = normalize_text_for_match(part_clean)
                        for official in OFFICIAL_NOTIONS:
                            if normalize_text_for_match(official) == part_norm:
                                matched_notion = official
                                break
                        if matched_notion:
                            if matched_notion not in notions_list:
                                notions_list.insert(0, matched_notion)
                        else:
                            # Keep it if it looks like a custom notion
                            if part_clean not in notions_list:
                                notions_list.insert(0, part_clean)
            else:
                is_notions_part = False
                resume_clean_lines.insert(0, line)
                
        resume_val = " ".join(resume_clean_lines).strip()
        # Clean any trailing punctuation or notion remains
        resume_val = re.sub(r"\s*La\s+(nature|religion|technique|science|justice|conscience|liberté|vérité|raison|le\s+travail)\s*$", "", resume_val, flags=re.IGNORECASE)
        resume_val = resume_val.strip().strip(",")
        
        # Save parsed data
        database_seed[match_key] = {
            "title": titre_val,
            "thesis": these_val,
            "summary": resume_val,
            "notions": notions_list
        }
        
    print(f"Successfully loaded {len(database_seed)} analysis cards from raw_ocr.txt.")
    return database_seed

def extract_pdf_text(filepath):
    """Extract raw text from PDF file and clean it up (removing page headers like 1 / 6)"""
    try:
        reader = pypdf.PdfReader(filepath)
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            # Clean page headers (e.g. "1 / 6" or "Page 1") from the beginning of pages
            lines = text.splitlines()
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                # Ignore lines that are just "1 / 6" or similar page indicators
                if re.match(r"^\d+\s*/\s*\d+$", stripped) or re.match(r"^page\s+\d+$", stripped, re.IGNORECASE):
                    continue
                cleaned_lines.append(line)
            pages_text.append("\n".join(cleaned_lines))
        return "\n\n".join(pages_text).strip()
    except Exception as e:
        print(f"Error extracting text from {filepath}: {e}")
        return ""

def call_gemini_analysis(filename_no_ext, text_content):
    """Use Gemini 2.5 Flash to analyze text according to the Gem constraints"""
    # Try using gemini-2.5-flash (modern and available)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
Analyse le texte philosophique suivant. Tu dois extraire ou générer les éléments suivants au format attendu.

FORMAT DE SORTIE ATTENDU :
Titre: [Titre exact de l'en-tête du texte, recopié tel quel]
Thèse: [La thèse soutenue par l'auteur dans ce texte, rédigée en UNE phrase de 10 mots maximum]
Résumé: [Résumé synthétique des arguments principaux du texte, rédigé en 50 mots maximum]
Notions: [Liste des notions du programme de philosophie directement liées au texte, séparées par des virgules, choisies EXCLUSIVEMENT parmi la liste suivante : L’art, Le bonheur, La conscience, Le devoir, L’État, L’inconscient, La justice, Le langage, La liberté, La nature, La raison, La religion, La science, La technique, Le temps, Le travail, La vérité]

CONSIGNES CRUCIALES :
- Ne mentionne AUCUNE source (pas de nom d'auteur, pas de nom d'œuvre, pas de siècle, pas de traduction dans le Titre, la Thèse ou le Résumé).
- Respecte STRICTEMENT les limites de mots (max 10 mots pour la Thèse, max 50 mots pour le Résumé).
- Choisis uniquement les notions pertinentes de la liste fournie.

TEXTE A ANALYSER :
{text_content[:4000]}  # Limit text to 4000 chars to fit context and keep it focused
"""
    try:
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Parse Gemini response
        titre_m = re.search(r"Titre:(.*?)(Thèse:|$)", response_text, re.DOTALL)
        these_m = re.search(r"Thèse:(.*?)(Résumé:|$)", response_text, re.DOTALL)
        resume_m = re.search(r"Résumé:(.*?)(Notions:|$)", response_text, re.DOTALL)
        notions_m = re.search(r"Notions:(.*)$", response_text, re.DOTALL)
        
        titre_val = titre_m.group(1).strip() if titre_m else ""
        these_val = these_m.group(1).strip() if these_m else ""
        resume_val = resume_m.group(1).strip() if resume_m else ""
        notions_raw = notions_m.group(1).strip() if notions_m else ""
        
        # Clean notions list to match official ones
        notions_list = []
        for part in notions_raw.split(","):
            part_clean = part.strip().strip(".")
            part_norm = normalize_text_for_match(part_clean)
            for official in OFFICIAL_NOTIONS:
                if normalize_text_for_match(official) == part_norm:
                    notions_list.append(official)
                    break
        
        # If no notions matched, try to infer from filename
        if not notions_list:
            header_match = re.match(r"^(\d+)\.([^_]+)_(.*)$", filename_no_ext.replace(" ", ""))
            if not header_match:
                parts = filename_no_ext.split("_", 1)
                if len(parts) == 2:
                    author = parts[0].split(".", 1)[-1].strip()
                    themes_part = parts[1].strip()
                else:
                    author = ""
                    themes_part = filename_no_ext
            else:
                author = header_match.group(2).strip()
                themes_part = header_match.group(3).strip()
                
            if author.upper() == "DE" and "_" in themes_part:
                _, themes_part = themes_part.split("_", 1)
                
            for t in themes_part.split("&"):
                t_norm = normalize_text_for_match(t)
                for official in OFFICIAL_NOTIONS:
                    if t_norm in normalize_text_for_match(official) or normalize_text_for_match(official) in t_norm:
                        notions_list.append(official)
                            
        return {
            "title": titre_val,
            "thesis": these_val,
            "summary": resume_val,
            "notions": list(set(notions_list))
        }
    except Exception as e:
        print(f"Error calling Gemini for {filename_no_ext}: {e}")
        return None

def main():
    print("--- STARTING哲学TEXT EXTRACTION AND ANALYSIS SEEDING ---")
    
    # 1. Ensure folders exist
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(TEXTS_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)
    
    # 2. Parse raw OCR seed
    database_seed = parse_raw_ocr()
    
    # 3. Scan PDF source folder
    if not os.path.exists(SOURCE_PDF_DIR):
        print(f"Error: Source directory {SOURCE_PDF_DIR} does not exist.")
        return
        
    pdf_files = [f for f in os.listdir(SOURCE_PDF_DIR) if f.endswith(".pdf")]
    print(f"Found {len(pdf_files)} PDF files in source directory.")
    
    # Sort files numerically
    def get_file_num(filename):
        m = re.match(r"^(\d+)\.", filename)
        return int(m.group(1)) if m else 999
    pdf_files.sort(key=get_file_num)

    tsv_rows = []
    matches_count = 0
    generated_count = 0
    error_count = 0
    
    for idx, filename in enumerate(pdf_files):
        filename_no_ext = os.path.splitext(filename)[0]
        filepath = os.path.join(SOURCE_PDF_DIR, filename)
        
        # Parse filename to match against seed
        # Ex: "111.ARENDT_Homme&Machine&Asservissement.pdf"
        header_match = re.match(r"^(\d+)\.([^_]+)_(.*)$", filename_no_ext.replace(" ", ""))
        if not header_match:
            parts = filename_no_ext.split("_", 1)
            if len(parts) == 2:
                author_part = parts[0]
                themes_part = parts[1]
                author = author_part.split(".", 1)[-1].strip()
                themes = themes_part.strip()
            else:
                author = ""
                themes = filename_no_ext
        else:
            author = header_match.group(2).strip()
            themes = header_match.group(3).strip()
            
        if author.upper() == "DE" and "_" in themes:
            author_extra, themes = themes.split("_", 1)
            author = f"DE {author_extra}"
            
        author_norm = normalize_text_for_match(author)
        themes_norm = normalize_text_for_match(themes)
        
        # Remove suffixes like _c, _court, _complet for seed lookup
        themes_norm_lookup = re.sub(r"(c|court|complet|introduction|intro)$", "", themes_norm)
        match_key = (author_norm, themes_norm_lookup)
        
        # A. Copy PDF to project pdf/ folder
        dest_pdf_path = os.path.join(PDF_DIR, filename)
        shutil.copyfile(filepath, dest_pdf_path)
        
        # B. Extract and save clean raw text
        text_content = extract_pdf_text(filepath)
        dest_txt_path = os.path.join(TEXTS_DIR, f"{filename_no_ext}.txt")
        with open(dest_txt_path, "w", encoding="utf-8") as txt_f:
            txt_f.write(text_content)
            
        analysis = None
        
        # C. Match against seed
        if match_key in database_seed:
            analysis = database_seed[match_key]
            matches_count += 1
            print(f"[{idx+1}/{len(pdf_files)}] MATCHED: {filename_no_ext} (seeded from last year)")
        else:
            # D. Call Gemini API for new texts
            print(f"[{idx+1}/{len(pdf_files)}] NEW TEXT: {filename_no_ext} (Analyzing with Gemini 2.0 Flash...)")
            # Wait 4 seconds to respect the 15 RPM rate limit of Google AI Studio Free Tier
            time.sleep(4.0)
            analysis = call_gemini_analysis(filename_no_ext, text_content)
            if analysis:
                generated_count += 1
                # Save generated analysis into database_seed so we don't call it again next time
                database_seed[match_key] = analysis
            else:
                error_count += 1
                # Fallback placeholder if API fails
                analysis = {
                    "title": themes.replace("&", " et "),
                    "thesis": "Thèse à rédiger pour ce texte.",
                    "summary": "Résumé de lecture à rédiger pour ce texte.",
                    "notions": []
                }
                
        # Format notions as comma-separated string
        notions_str = ", ".join(analysis["notions"]) if analysis["notions"] else "La technique" # default fallback
        
        # Format Analysis column exactly: Titre: [title]. Thèse: [thesis]. Résumé: [summary].
        analysis_col = f"Titre: {analysis['title']}. Thèse: {analysis['thesis']}. Résumé: {analysis['summary']}."
        # Remove any double dots or messy spacing
        analysis_col = re.sub(r'\.+', '.', analysis_col)
        analysis_col = re.sub(r'\s+', ' ', analysis_col)
        
        # Add to TSV rows: Col 1: Filename, Col 2: Analysis, Col 3: Notions
        tsv_rows.append(f"{filename_no_ext}\t{analysis_col}\t{notions_str}")

    # Write TSV database
    with open(DATABASE_TSV, "w", encoding="utf-8") as tsv_f:
        # Write header
        tsv_f.write("Nom du fichier\tAnalyse du texte\tNotions du programme de philosophie\n")
        for row in tsv_rows:
            tsv_f.write(f"{row}\n")
            
    print("\n--- EXTRACTION AND DATABASE GENERATION COMPLETE ---")
    print(f"Total PDFs processed: {len(pdf_files)}")
    print(f"Matched from last year's PDF: {matches_count}")
    print(f"Generated with Gemini 2.0 Flash: {generated_count}")
    print(f"Failed / Fallback placeholder: {error_count}")
    print(f"Database saved to: {DATABASE_TSV}")

if __name__ == "__main__":
    main()
