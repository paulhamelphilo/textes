import os
import sys
import re
import shutil
import time
import subprocess

# Reconfigure stdout for UTF-8 to support French accents in Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure dependencies are checked and installed
def check_dependencies():
    dependencies = {
        'mammoth': 'mammoth',
        'win32com.client': 'pywin32',
        'google.generativeai': 'google-generativeai'
    }
    
    missing = []
    for module_name, package_name in dependencies.items():
        try:
            if module_name == 'win32com.client':
                import win32com.client
            else:
                __import__(module_name)
        except ImportError:
            missing.append(package_name)
            
    if missing:
        print(f"Bibliothèques manquantes détectées : {', '.join(missing)}")
        print("Installation automatique en cours...")
        for pkg in missing:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
                print(f"Bibliothèque '{pkg}' installée avec succès !")
            except Exception as e:
                print(f"Erreur lors de l'installation de {pkg}: {e}")
                print(f"Veuillez l'installer manuellement : pip install {pkg}")
                sys.exit(1)

# Check and install packages
check_dependencies()

import mammoth
import google.generativeai as genai

# Setup directories
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
TEXTS_DIR = os.path.join(DATA_DIR, "texts")
PDF_DIR = os.path.join(PROJECT_DIR, "pdf")
DATABASE_TSV = os.path.join(DATA_DIR, "database.tsv")

def get_next_available_id():
    """Scan database to find the next available ID starting at 50"""
    ids = []
    if os.path.exists(DATABASE_TSV):
        try:
            with open(DATABASE_TSV, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            for line in lines[1:]:
                if line.strip():
                    cols = line.split("\t")
                    try:
                        ids.append(int(cols[0]))
                    except ValueError:
                        pass
        except Exception as e:
            print(f"Erreur lecture database pour l'ID : {e}")
            
    # Filter IDs in range [50, 99]
    new_texts_ids = [i for i in ids if 50 <= i < 100]
    if new_texts_ids:
        return max(new_texts_ids) + 1
    else:
        return 50

# Official Philosophy Curriculum Notions Whitelist
OFFICIAL_NOTIONS = [
    "L'art", "Le bonheur", "La conscience", "Le devoir", "L'État", 
    "L'inconscient", "La justice", "Le langage", "La liberté", "La nature", 
    "La raison", "La religion", "La science", "La technique", "Le temps", 
    "Le travail", "La vérité"
]

# API config
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    env_path = os.path.join(PROJECT_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        API_KEY = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass

def normalize_notion(notion_str):
    """Normalize apostrophes, accents, and spacing to match official notions list"""
    norm = notion_str.strip().lower().replace("’", "'").replace("œ", "oe")
    norm = re.sub(r"[^a-z0-9]", "", norm)
    
    for official in OFFICIAL_NOTIONS:
        off_norm = official.lower().replace("’", "'").replace("œ", "oe")
        off_norm = re.sub(r"[^a-z0-9]", "", off_norm)
        if norm == off_norm:
            return official
    return None

def convert_to_pdf_word(docx_path, pdf_path):
    print("\n--- ÉTAPE 1 : CONVERSION DOCX -> PDF (via Microsoft Word) ---")
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(docx_path)
            # FileFormat=17 is PDF
            doc.SaveAs(pdf_path, FileFormat=17)
            doc.Close()
            print(f"-> PDF créé avec succès : {pdf_path}")
            return True
        except Exception as e:
            print(f"Erreur COM lors de la conversion PDF : {e}")
            return False
        finally:
            word.Quit()
    except Exception as e:
        print("Erreur : Impossible d'utiliser Microsoft Word pour la conversion PDF.")
        print("Avez-vous Microsoft Word installé sur votre ordinateur Windows ?")
        print(f"-> Veuillez convertir manuellement votre fichier en PDF et le placer ici : {pdf_path}")
        return False

def convert_to_html_mammoth(docx_path, html_path):
    print("\n--- ÉTAPE 2 : CONVERSION DOCX -> HTML (via Mammoth) ---")
    try:
        with open(docx_path, "rb") as docx_file:
            # Convert with underline support mapped to <u>
            result = mammoth.convert_to_html(docx_file, style_map="u => u")
            html_content = result.value
            
        # Nettoyage typographique général
        # 1. Supprimer les slashs et double-slashs parasites (suivis d'une majuscule ou d'un guillemet)
        html_content = re.sub(r'\s*//+\s*([A-ZÀ-Ÿ«])', r' \1', html_content)
        html_content = re.sub(r'\s*/+\s*([A-ZÀ-Ÿ«])', r' \1', html_content)
        
        # 2. Normaliser les espaces insécables et multiples
        html_content = re.sub(r'[ \t\u00a0\u202f]+', ' ', html_content)
        
        # 3. Supprimer les paragraphes vides générés
        html_content = re.sub(r'<p>\s*</p>', '', html_content)
        
        # 4. Nettoyer les espaces aux extrémités
        html_content = html_content.strip()
            
        with open(html_path, "w", encoding="utf-8") as out_file:
            out_file.write(html_content)
        print(f"-> HTML créé avec succès : {html_path}")
        return True
    except Exception as e:
        print(f"Erreur lors de la conversion HTML : {e}")
        return False

def extract_text_mammoth(docx_path):
    try:
        with open(docx_path, "rb") as docx_file:
            result = mammoth.extract_raw_text(docx_file)
            return result.value
    except Exception as e:
        print(f"Erreur d'extraction de texte brut : {e}")
        return ""

def call_gemini_analysis(filename_no_ext, text_content):
    print("\nAppel de l'API Gemini pour générer l'analyse du texte...")
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
Analyse le texte philosophique suivant. Tu dois extraire ou générer les éléments suivants au format attendu.

FORMAT DE SORTIE ATTENDU :
Titre: [Titre exact de l'en-tête du texte, recopié tel quel]
Thèse: [La thèse soutenue par l'auteur dans ce texte, rédigée en UNE phrase de 10 mots maximum]
Résumé: [Résumé synthétique des arguments principaux du texte, rédigé en 50 mots maximum]
Notions: [Liste des notions du programme de philosophie directement liées au texte (5 notions maximum), séparées par des virgules, choisies EXCLUSIVEMENT parmi la liste suivante : L’art, Le bonheur, La conscience, Le devoir, L’État, L’inconscient, La justice, Le langage, La liberté, La nature, La raison, La religion, La science, La technique, Le temps, Le travail, La vérité]

CONSIGNES CRUCIALES :
- Ne mentionne AUCUNE source (pas de nom d'auteur, pas de nom d'œuvre, pas de siècle, pas de traduction dans le Titre, la Thèse ou le Résumé).
- Respecte STRICTEMENT les limites de mots (max 10 mots pour la Thèse, max 50 mots pour le Résumé).
- Choisis uniquement les notions pertinentes de la liste fournie (maximum 5 notions).

TEXTE A ANALYSER :
{text_content[:6000]}
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
        
        notions_list = []
        for part in notions_raw.split(","):
            part_clean = part.strip().strip(".")
            matched = normalize_notion(part_clean)
            if matched:
                notions_list.append(matched)
                
        unique_notions = list(set(notions_list))
        return {
            "title": titre_val,
            "thesis": these_val,
            "summary": resume_val,
            "notions": unique_notions[:5]
        }
    except Exception as e:
        print(f"Erreur API Gemini : {e}")
        return None

def prompt_notions(current_notions_list):
    while True:
        print("\n=== NOTIONS DU PROGRAMME DISPONIBLES ===")
        # Print side-by-side to save space
        for i in range(0, len(OFFICIAL_NOTIONS), 2):
            n1 = OFFICIAL_NOTIONS[i]
            sel1 = "[X]" if n1 in current_notions_list else "[ ]"
            line = f"  {i+1:2d}. {sel1} {n1:<18s}"
            if i + 1 < len(OFFICIAL_NOTIONS):
                n2 = OFFICIAL_NOTIONS[i+1]
                sel2 = "[X]" if n2 in current_notions_list else "[ ]"
                line += f"  {i+2:2d}. {sel2} {n2}"
            print(line)
            
        print("\nSélection actuelle :", ", ".join(current_notions_list) if current_notions_list else "(aucune)")
        print("\n-> Entrez les numéros des notions (ex: 1, 4, 15) pour les ajouter/retirer,")
        print("-> Ou tapez directement les noms des notions séparées par des virgules.")
        print("-> Appuyez sur Entrée pour valider la sélection actuelle.")
        
        user_input = input("Votre choix : ").strip()
        if not user_input:
            return current_notions_list
            
        # Check if numbers
        if re.match(r"^[\d\s,]+$", user_input):
            parts = [p.strip() for p in user_input.split(",") if p.strip()]
            new_selection = list(current_notions_list)
            for part in parts:
                try:
                    num = int(part)
                    if 1 <= num <= len(OFFICIAL_NOTIONS):
                        notion = OFFICIAL_NOTIONS[num - 1]
                        if notion in new_selection:
                            new_selection.remove(notion)
                            print(f"[-] Retiré : {notion}")
                        else:
                            new_selection.append(notion)
                            print(f"[+] Ajouté : {notion}")
                    else:
                        print(f"⚠️ Numéro invalide : {num}")
                except ValueError:
                    pass
            current_notions_list = new_selection
        else:
            # Parse names
            parts = [p.strip() for p in user_input.split(",") if p.strip()]
            new_selection = []
            for part in parts:
                matched = normalize_notion(part)
                if matched:
                    new_selection.append(matched)
                else:
                    print(f"⚠️ Notion '{part}' non reconnue et ignorée.")
            if new_selection:
                current_notions_list = list(set(new_selection))

def get_validated_thesis(default_val=""):
    while True:
        thesis = input(f"\nThèse (max 10 mots) [{default_val}] :\n> ").strip()
        if not thesis:
            thesis = default_val
            
        word_count = len(thesis.split())
        if word_count > 10:
            print(f"⚠️ Attention : la thèse contient {word_count} mots (limite max: 10 mots).")
            confirm = input("Voulez-vous forcer cette thèse ? (o/N) : ").strip().lower()
            if confirm == 'o':
                return thesis
        elif not thesis:
            print("⚠️ La thèse ne peut pas être vide.")
        else:
            return thesis

def get_validated_summary(default_val=""):
    while True:
        summary = input(f"\nRésumé (max 50 mots) [{default_val}] :\n> ").strip()
        if not summary:
            summary = default_val
            
        word_count = len(summary.split())
        if word_count > 50:
            print(f"⚠️ Attention : le résumé contient {word_count} mots (limite max: 50 mots).")
            confirm = input("Voulez-vous forcer ce résumé ? (o/N) : ").strip().lower()
            if confirm == 'o':
                return summary
        elif not summary:
            print("⚠️ Le résumé ne peut pas être vide.")
        else:
            return summary

def update_database(text_id, filename_no_ext, title, thesis, summary, notions_list):
    print("\n--- ÉTAPE 4 : MISE À JOUR DE LA BASE DE DONNÉES ---")
    try:
        rows = []
        header = "Identifiant\tNom du fichier\tAnalyse du texte\tNotions du programme de philosophie"
        
        if os.path.exists(DATABASE_TSV):
            with open(DATABASE_TSV, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
                if lines:
                    header = lines[0]
                    for line in lines[1:]:
                        if line.strip():
                            rows.append(line.split("\t"))
        
        # Clean col 3 values
        analysis_col = f"Titre: {title}. Thèse: {thesis}. Résumé: {summary}."
        analysis_col = re.sub(r'\.+', '.', analysis_col)
        analysis_col = re.sub(r'\s+', ' ', analysis_col)
        
        # Limit notions to 5 maximum
        notions_list = notions_list[:5]
        
        # Fallback check: if notions_list contains "La technique" but "technique" does not appear in the filename, title, or summary,
        # and we have other notions, remove "La technique"
        if "La technique" in notions_list and len(notions_list) > 1:
            tech_norm = normalize_text_for_match("La technique")
            in_filename = tech_norm in normalize_text_for_match(filename_no_ext)
            in_title = tech_norm in normalize_text_for_match(title)
            in_summary = tech_norm in normalize_text_for_match(summary)
            if not (in_filename or in_title or in_summary):
                notions_list.remove("La technique")
                
        # If still empty, infer from filename
        if not notions_list:
            for official in OFFICIAL_NOTIONS:
                o_norm = normalize_text_for_match(official)
                if o_norm in normalize_text_for_match(filename_no_ext):
                    notions_list.append(official)
                    
        notions_str = ", ".join(notions_list[:5])
        
        new_row = [str(text_id), filename_no_ext, analysis_col, notions_str]
        existing_idx = -1
        for idx, row in enumerate(rows):
            if len(row) > 1 and row[1] == filename_no_ext:
                existing_idx = idx
                break
                
        if existing_idx != -1:
            print(f"Une entrée pour '{filename_no_ext}' existe déjà (Identifiant: {rows[existing_idx][0]}).")
            confirm = input(f"Voulez-vous écraser cette entrée existante et lui attribuer l'identifiant {text_id} ? (O/n) : ").strip().lower()
            if confirm == 'n':
                print("Mise à jour de la base de données annulée.")
                return False
            rows[existing_idx] = new_row
            print("-> L'entrée existante a été mise à jour.")
        else:
            rows.append(new_row)
            print("-> Nouvelle entrée ajoutée.")
            
        # Numerical sorting key
        def get_file_id(r):
            try:
                return int(r[0])
            except ValueError:
                return 9999
            
        rows.sort(key=get_file_id)
        
        # Write to TSV
        with open(DATABASE_TSV, "w", encoding="utf-8") as f:
            f.write(header + "\n")
            for row in rows:
                f.write("\t".join(row) + "\n")
                
        print(f"-> Base de données enregistrée avec succès : {DATABASE_TSV}")
        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde TSV : {e}")
        return False

def select_docx_files():
    # Scan current folder and parent folder for .docx
    candidates = []
    
    # Check current directory
    for f in os.listdir("."):
        if f.endswith(".docx") and not f.startswith("~$"):
            candidates.append(os.path.abspath(f))
            
    # Check scripts directory
    if os.path.exists(SCRIPTS_DIR):
        for f in os.listdir(SCRIPTS_DIR):
            if f.endswith(".docx") and not f.startswith("~$"):
                candidates.append(os.path.join(SCRIPTS_DIR, f))
                
    # Check parent directory (project root)
    if PROJECT_DIR != os.getcwd():
        for f in os.listdir(PROJECT_DIR):
            if f.endswith(".docx") and not f.startswith("~$"):
                abs_path = os.path.join(PROJECT_DIR, f)
                if abs_path not in candidates:
                    candidates.append(abs_path)
                    
    # Remove duplicates
    candidates = list(set(candidates))
    
    if not candidates:
        print("Aucun fichier Word (.docx) détecté automatiquement.")
        path = input("Veuillez entrer le chemin absolu ou relatif de votre fichier .docx :\n> ").strip()
        if not path or not os.path.exists(path):
            print("Fichier invalide ou inexistant. Fin du programme.")
            sys.exit(1)
        return [path]
        
    print("\nFichiers Word (.docx) détectés :")
    for idx, path in enumerate(candidates, 1):
        print(f"  {idx:2d}. {os.path.basename(path)}")
        
    print("\nSaisissez :")
    print("-> Un numéro unique (ex: 1)")
    print("-> Une liste de numéros séparés par des virgules (ex: 1, 3)")
    print("-> '*' ou 'tous' pour traiter TOUS les fichiers")
    print("-> Ou appuyez sur Entrée pour spécifier manuellement le chemin d'un autre fichier")
    
    user_input = input("\nVotre choix : ").strip()
    
    if not user_input:
        path = input("Veuillez entrer le chemin de votre fichier .docx :\n> ").strip()
        if not path or not os.path.exists(path):
            print("Fichier invalide ou inexistant. Fin du programme.")
            sys.exit(1)
        return [path]
        
    if user_input == '*' or user_input.lower() in ['tous', 'all']:
        return candidates
        
    # Check for list of numbers
    if re.match(r"^[\d\s,]+$", user_input):
        selected_files = []
        parts = [p.strip() for p in user_input.split(",") if p.strip()]
        for part in parts:
            try:
                num = int(part)
                if 1 <= num <= len(candidates):
                    selected_files.append(candidates[num - 1])
                else:
                    print(f"⚠️ Numéro de fichier ignoré (hors plage) : {num}")
            except ValueError:
                pass
        if selected_files:
            return selected_files
            
    # If not matched, try treating it as a path
    if os.path.exists(user_input):
        return [os.path.abspath(user_input)]
        
    print("Sélection invalide. Fin du programme.")
    sys.exit(1)

def main():
    print("=================================================================")
    print("    MEMENTO-IA : AJOUT DE NOUVEAUX TEXTES PHILOSOPHIQUES         ")
    print("=================================================================")
    
    # 1. Ensure output folders exist
    os.makedirs(TEXTS_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)
    
    # 2. Select files
    docx_paths = select_docx_files()
    
    print(f"\nNombre de fichiers à traiter : {len(docx_paths)}")
    
    success_count = 0
    for idx, docx_path in enumerate(docx_paths, 1):
        filename = os.path.basename(docx_path)
        filename_no_ext = os.path.splitext(filename)[0]
        
        print("\n=================================================================")
        print(f"  Fichier {idx}/{len(docx_paths)} : {filename}")
        print("=================================================================")
        
        # Determine clean filename
        # Since files will not be numbered, the clean filename is just filename_no_ext.
        # But just in case some files still have numbers, let's clean them.
        m = re.match(r"^(\d+)\.(.*)$", filename_no_ext)
        if m:
            clean_filename = m.group(2)
        else:
            clean_filename = filename_no_ext
            
        # Determine numerical ID automatically by looking at the database
        text_id = get_next_available_id()
        print(f"-> Identifiant attribué automatiquement : {text_id}")
        
        pdf_path = os.path.join(PDF_DIR, f"{clean_filename}.pdf")
        html_path = os.path.join(TEXTS_DIR, f"{clean_filename}.html")
        
        # 3. Conversions
        pdf_success = convert_to_pdf_word(docx_path, pdf_path)
        html_success = convert_to_html_mammoth(docx_path, html_path)
        
        if not html_success:
            print("❌ Erreur : La conversion HTML a échoué. Passage au fichier suivant.")
            continue
            
        # Enrich HTML with PDF formatting if PDF was successfully created
        if pdf_success:
            print("\n--- ÉTAPE 2.5 : ENRICHISSEMENT TYPOGRAPHIQUE DEPUIS LE PDF ---")
            try:
                enrich_script = os.path.join(SCRIPTS_DIR, "enrich_html_from_pdf.py")
                cmd = [sys.executable, enrich_script, "--file", clean_filename]
                subprocess.run(cmd, check=True)
                print("-> HTML enrichi avec succès depuis le PDF !")
            except Exception as e:
                print(f"⚠️ Avertissement : Échec de l'enrichissement typographique : {e}")
            
        # 4. Extraction & Seeding/Analysis
        raw_text = extract_text_mammoth(docx_path)
        
        analysis = None
        if API_KEY:
            analysis = call_gemini_analysis(clean_filename, raw_text)
            
        if analysis is None:
            print("\n⚠️ Analyse automatique par l'IA non disponible ou échouée.")
            print("Saisie manuelle des données requise.")
            analysis = {
                "title": clean_filename.split("_", 1)[-1].replace("&", " et ") if "_" in clean_filename else clean_filename,
                "thesis": "",
                "summary": "",
                "notions": []
            }
            
        # 5. User confirmation & edits
        print("\n--- ÉTAPE 3 : CONFIRMATION ET RÉVISION DE L'ANALYSE ---")
        print(f"Titre généré : {analysis['title']}")
        title_confirm = input("Appuyez sur Entrée pour valider, ou saisissez un nouveau titre :\n> ").strip()
        final_title = title_confirm if title_confirm else analysis['title']
        
        final_thesis = get_validated_thesis(analysis['thesis'])
        final_summary = get_validated_summary(analysis['summary'])
        final_notions = prompt_notions(analysis['notions'])
        
        # 6. Database Update
        db_success = update_database(text_id, clean_filename, final_title, final_thesis, final_summary, final_notions)
        if db_success:
            success_count += 1
            
    print("\n=================================================================")
    print("    SYNTHÈSE DE L'OPÉRATION BATCH                                ")
    print("=================================================================")
    print(f"Fichiers traités avec succès : {success_count}/{len(docx_paths)}")
    print("=================================================================")
    print("Les textes sont maintenant disponibles pour vos élèves dans l'outil !")
    print("N'oubliez pas de recharger la page web de votre navigateur.")

if __name__ == "__main__":
    main()
