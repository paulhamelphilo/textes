import os
import re
import sys
import argparse
import fitz  # PyMuPDF
from bs4 import BeautifulSoup

# Reconfigure stdout for UTF-8 to support French accents in Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def normalize(text):
    if not text:
        return ""
    text = text.lower().replace("’", "'").replace("œ", "oe").replace("æ", "ae")
    # Remove all non-alphanumeric characters
    return re.sub(r"[^a-z0-9]", "", text)

def extract_pdf_blocks(pdf_path):
    """
    Extract text blocks from PDF using PyMuPDF (fitz) dict layout.
    Classifies blocks based on their geometric coordinate properties.
    """
    doc = fitz.open(pdf_path)
    
    # 1. Gather all font sizes to determine dominant body font size
    font_sizes = {}
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        if s["text"].strip():
                            size = round(s["size"], 1)
                            font_sizes[size] = font_sizes.get(size, 0) + len(s["text"])
    body_size = max(font_sizes, key=font_sizes.get) if font_sizes else 11.0
    
    pdf_blocks = []
    page_num = 0
    
    for page in doc:
        page_num += 1
        page_width = page.rect.width
        page_height = page.rect.height
        
        blocks = page.get_text("dict")["blocks"]
        # Sort blocks top-to-bottom
        text_blocks = sorted([b for b in blocks if "lines" in b], key=lambda x: x["bbox"][1])
        
        for b in text_blocks:
            x0, y0, x1, y1 = b["bbox"]
            
            lines_data = []
            text_parts = []
            has_bold_span = False
            has_italic_span = False
            
            for l in b["lines"]:
                # Keep track of left coordinates of lines to check for indentation
                lines_data.append(l["bbox"][0])
                
                line_text_parts = []
                for s in l["spans"]:
                    t = s["text"]
                    if not t.strip():
                        continue
                    
                    font_name = s["font"].lower()
                    is_b = "bold" in font_name or "bd" in font_name or (s["flags"] & 16)
                    is_i = "italic" in font_name or "ital" in font_name or "oblique" in font_name or (s["flags"] & 2)
                    
                    if is_b:
                        has_bold_span = True
                    if is_i:
                        has_italic_span = True
                    
                    line_text_parts.append(t)
                
                line_txt = "".join(line_text_parts)
                if line_txt.strip():
                    text_parts.append(line_txt)
            
            block_text = " ".join(text_parts)
            block_text = re.sub(r"\s+", " ", block_text).strip()
            
            if not block_text:
                continue
                
            # Filter out standalone page numbers (e.g. "1 / 5" or "5")
            if re.match(r"^\d+\s*/\s*\d+$", block_text) or re.match(r"^\d+$", block_text):
                continue
                
            # Geometry-based classifications
            mid_x = (x0 + x1) / 2
            page_mid = page_width / 2
            block_width = x1 - x0
            
            # 1. Centered (Title)
            # Distance from page center is small, block is not full-width, short, and no final period (blockquotes end with periods)
            is_centered = abs(mid_x - page_mid) < 25 and block_width < 0.8 * page_width and len(block_text) < 120 and not block_text.endswith(".")
            
            # 2. Right-Aligned (Reference/Source)
            # Ends near the right margin (usually right margin is 30-70pt), starts in right 60% of page
            is_right = (x1 > page_width - 80) and (x0 > page_width * 0.3) and (block_width < 0.85 * page_width)
            # Or contains an arrow near the beginning (accounts for OCR prefixes like "à")
            has_arrow = re.search(r"^.{0,12}(?:[→🡪🡺\u2190-\u21FF\u2B00-\u2BFF\U0001F800-\U0001F8FF]|)", block_text) is not None
            if has_arrow:
                is_right = True
            
            # 3. Footnote
            # Located near bottom, and font size is smaller than body size
            block_sizes = [s["size"] for l in b["lines"] for s in l["spans"] if s["text"].strip()]
            avg_size = sum(block_sizes) / len(block_sizes) if block_sizes else body_size
            is_footnote = (y0 > page_height - 180) and (avg_size < body_size - 1.2)
            
            # 4. Indented paragraph (Alinéa)
            has_indent = False
            if len(lines_data) > 1:
                # First line is indented compared to the second line
                has_indent = lines_data[0] > lines_data[1] + 12
            
            # 5. Subheading
            # Left-aligned, bold, short, no final period
            is_subheading = False
            if not is_centered and not is_right and not is_footnote:
                is_subheading = has_bold_span and len(block_text) < 120 and not block_text.endswith(".")
            
            role = "paragraph"
            if is_centered:
                role = "title"
            elif is_right:
                role = "reference"
            elif is_footnote:
                role = "footnote"
            elif is_subheading:
                role = "subheading"
                
            pdf_blocks.append({
                "text": block_text,
                "role": role,
                "has_indent": has_indent,
                "has_bold": has_bold_span,
                "has_italic": has_italic_span,
                "page": page_num,
                "bbox": (x0, y0, x1, y1)
            })
            
    return pdf_blocks, body_size

def simulate_process_loaded_html(soup):
    """
    Simulates the dynamic JS processLoadedHTML logic in app.js.
    Determines classes and roles for HTML blocks exactly as the browser would.
    """
    elements = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"])
    
    ref_keywords = ['trad', 'traduction', 'tome', 'vol', 'éd', 'ed', 'p.', 'page', 'chapitre', 'col.']
    common_publishers = ['gallimard', 'éditions', 'editions', 'jean-françois', 'librairie', 'presses', 'minuit', 'seuil', 'flammarion', 'vrin', 'albin', 'grasset', 'fayard', 'hachette', 'nathan', 'hatier', 'belin', 'bordas']
    
    first_title_found = False
    after_reference = False
    
    html_blocks = []
    
    for el in elements:
        # Nettoyage des styles en ligne parasites pour simuler le comportement du nouveau app.js
        if el.has_attr("style"):
            del el["style"]
        for child in el.find_all(style=True):
            del child["style"]

        # Ignore if inside footnotes section or if it's a footnote item
        if el.find_parent(class_="footnotes") or el.find_parent("div", class_="footnotes") or el.get("id", "").startswith("footnote"):
            continue
            
        # Ignore elements inside table, ul, ol (they get class 'text-body-simple' in app.js)
        if el.find_parent(["table", "ul", "ol", "li"]):
            html_blocks.append({
                "text": el.get_text().strip(),
                "role": "simple",
                "has_bold": el.find(["b", "strong"]) is not None,
                "has_italic": el.find(["i", "em"]) is not None,
                "classes": el.get("class", []) + ["text-body-simple"],
                "tag": el.name,
                "element": el
            })
            continue
            
        plain_text = el.get_text().strip()
        if not plain_text:
            continue
            
        # 1. Arrow reference detection
        is_arrow_ref = re.match(r"^\s*(?:[→🡪🡺\u2190-\u21FF\u2B00-\u2BFF\U0001F800-\U0001F8FF]|&rarr;|&#8594;)", plain_text, re.UNICODE) is not None
        
        # 2. Continuation reference detection
        is_ref_cont = False
        if after_reference:
            clean_plain = re.sub(r"^[«»\"“’\s\t\(\)\[\]\{\}\-\+~≈]+", "", plain_text).strip()
            if clean_plain:
                first_char = clean_plain[0]
                is_lower = first_char.islower()
                
                clean_plain_lower = clean_plain.lower()
                is_ref_keyword = any(clean_plain_lower.startswith(kw) for kw in ref_keywords)
                is_year_or_paren = re.match(r"^\d{4}", clean_plain) is not None or re.match(r"^[ivxlcdm]+(?:e|ème|°|er)?\s+(?:siècle|s\b)", clean_plain, re.IGNORECASE) is not None
                is_roman_ref = re.match(r"^[ivxlcdm]+(?:\b|\.)", clean_plain, re.IGNORECASE) is not None
                is_l_ref = re.match(r"^l\.(?:\s|\d|$)", clean_plain_lower) is not None or re.match(r"^l\s+\d", clean_plain_lower) is not None or re.match(r"^l\s+[ivxlcdm]+", clean_plain_lower) is not None
                is_publisher = any(clean_plain_lower.startswith(pub) for pub in common_publishers)
                
                # Check if starts with italic tag in HTML
                starts_with_italic = False
                contents = list(el.contents)
                if contents and hasattr(contents[0], "name") and contents[0].name in ["em", "i"]:
                    starts_with_italic = True
                    
                if is_lower or is_ref_keyword or is_year_or_paren or is_roman_ref or is_l_ref or is_publisher or starts_with_italic:
                    is_ref_cont = True
                    
        # 3. Strong Title check (wrapped entirely in strong/b)
        is_strong = False
        active_children = [c for c in el.contents if not isinstance(c, str) or c.strip()]
        if len(active_children) == 1 and hasattr(active_children[0], "name") and active_children[0].name in ["strong", "b"]:
            is_strong = True
            
        # 4. Title Like check
        def is_title_like(text):
            plain = text.strip()
            plain = re.sub(r"\s*[\[\(]\d+[a-f]?[\]\)]\s*$", "", plain, flags=re.IGNORECASE).strip()
            plain = re.sub(r"^[«»\"“’\s\t\(\)\[\]\{\}]+|[«»\"“’\s\t\(\)\[\]\{\}]+$", "", plain).strip()
            if not plain:
                return False
                
            starts_with_letter_digit = re.match(r"^[a-zA-Z0-9À-ÿŒœ]", plain) is not None
            if not starts_with_letter_digit:
                return False
                
            if len(plain) > 100:
                return False
                
            ends_with_punct = re.search(r"[.!?;:]$", plain) is not None
            if ends_with_punct:
                return False
                
            title_exclude = ['trad', 'traduction', 'éd', 'ed', 'p.', 'page', 'col.']
            plain_lower = plain.lower()
            if any(plain_lower.startswith(kw) for kw in title_exclude):
                return False
                
            return True
            
        is_heading = el.name in ["h1", "h2", "h3", "h4", "h5", "h6"]
        
        # Check if next sibling is a list (list intro)
        next_sibling = el.find_next_sibling()
        is_list_intro = next_sibling and next_sibling.name in ["ol", "ul"]
        
        is_title_or_sub = is_heading or is_strong or (is_title_like(plain_text) and not is_list_intro)
        
        role = "paragraph"
        resolved_classes = list(el.get("class", []))
        
        if is_arrow_ref or is_ref_cont:
            role = "reference"
            resolved_classes.append("text-body-reference")
            after_reference = True
        elif is_title_or_sub:
            is_all_uppercase = plain_text == plain_text.upper() and any(c.isupper() for c in plain_text)
            if not first_title_found or after_reference or is_all_uppercase:
                role = "title"
                resolved_classes.append("text-body-title")
                first_title_found = True
            else:
                role = "subheading"
                resolved_classes.append("text-body-subheading")
            after_reference = False
        else:
            role = "paragraph"
            resolved_classes.append("text-body-paragraph")
            after_reference = False
            
        html_blocks.append({
            "text": plain_text,
            "role": role,
            "has_bold": el.find(["b", "strong"]) is not None,
            "has_italic": el.find(["i", "em"]) is not None,
            "classes": resolved_classes,
            "tag": el.name,
            "element": el
        })
        
    return html_blocks

def extract_html_blocks(html_path):
    """
    Extract blocks from HTML with styles and classes.
    Identifies empty paragraphs and inline style anomalies.
    """
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    soup = BeautifulSoup(html_content, "html.parser")
    anomalies = []
    
    # 1. Detect empty paragraphs
    for p in soup.find_all("p"):
        p_text = p.get_text().strip()
        if not p_text and not p.find():
            anomalies.append({
                "type": "empty_element",
                "message": "Paragraphe vide `<p>` ou contenant uniquement des espaces.",
                "text": str(p)[:80]
            })
            
    # 2. Detect inline styles
    for el in soup.find_all(style=True):
        anomalies.append({
            "type": "inline_style",
            "message": f"Style en ligne parasite détecté sur `{el.name}` : `style=\"{el['style']}\"`",
            "text": str(el)[:80]
        })
        
    # 3. Extract footnotes
    html_footnotes = []
    footnote_div = soup.find(class_="footnotes") or soup.find("div", class_="footnotes")
    if footnote_div:
        items = footnote_div.find_all(["li", "div"], class_="footnote-item") or footnote_div.find_all("li")
        for item in items:
            html_footnotes.append({
                "text": re.sub(r"\s+", " ", item.get_text()).strip(),
                "element": item
            })
            
    # 4. Extract body blocks using rendering simulation
    html_blocks = simulate_process_loaded_html(soup)
        
    return html_blocks, html_footnotes, anomalies

def align_blocks(pdf_blocks, html_blocks):
    """
    Align PDF blocks with HTML blocks in sequential order
    using normalized text overlap.
    """
    aligned = []
    html_idx = 0
    
    for p_block in pdf_blocks:
        p_norm = normalize(p_block["text"])
        if not p_norm:
            continue
            
        best_match_idx = -1
        best_score = 0
        
        # Look ahead up to 5 blocks to match in sequential order
        for search_idx in range(html_idx, min(html_idx + 6, len(html_blocks))):
            h_block = html_blocks[search_idx]
            h_norm = normalize(h_block["text"])
            
            if p_norm == h_norm:
                score = 1.0
            elif p_norm in h_norm or h_norm in p_norm:
                score = min(len(p_norm), len(h_norm)) / max(len(p_norm), len(h_norm))
            else:
                # 3-gram Jaccard similarity
                p_shingles = set([p_norm[i:i+3] for i in range(len(p_norm)-2)])
                h_shingles = set([h_norm[i:i+3] for i in range(len(h_norm)-2)])
                if p_shingles and h_shingles:
                    score = len(p_shingles & h_shingles) / len(p_shingles | h_shingles)
                else:
                    score = 0
                    
            if score > best_score:
                best_score = score
                best_match_idx = search_idx
                
        if best_score > 0.4:
            aligned.append((p_block, html_blocks[best_match_idx]))
            html_idx = best_match_idx + 1
        else:
            aligned.append((p_block, None))
            
    return aligned

def check_mismatches(aligned_pairs, html_footnotes, pdf_blocks, html_blocks):
    """
    Identify visual, role, indentation, or structural formatting gaps.
    """
    mismatches = []
    
    # 1. Check mapped blocks
    for pdf_b, html_b in aligned_pairs:
        if not html_b:
            mismatches.append({
                "type": "missing_html_block",
                "message": "Bloc présent dans le PDF mais absent du HTML (texte manquant).",
                "text": pdf_b["text"][:100]
            })
            continue
            
        pdf_role = pdf_b["role"]
        html_role = html_b["role"]
        
        # Role mismatch
        if pdf_role != html_role:
            # Skip tables labeled simple
            if html_role == "simple" and pdf_role in ["paragraph", "footnote"]:
                continue
            mismatches.append({
                "type": "role_mismatch",
                "message": f"Écart d'alignement visuel : PDF attend '{pdf_role}' vs HTML affiche '{html_role}'.",
                "text": pdf_b["text"][:80],
                "details": f"PDF={pdf_role} | HTML={html_role}"
            })
            
        # Indentation mismatch
        if pdf_role == "paragraph" and html_role == "paragraph":
            pdf_indent = pdf_b["has_indent"]
            html_indent = "text-body-simple" not in html_b["classes"]
            if pdf_indent != html_indent:
                mismatches.append({
                    "type": "indent_mismatch",
                    "message": f"Écart d'alinéa : PDF={'retrait' if pdf_indent else 'sans retrait'} vs HTML={'retrait' if html_indent else 'sans retrait'}.",
                    "text": pdf_b["text"][:80]
                })
                
        # Rich styles mismatch
        if pdf_b["has_bold"] and not html_b["has_bold"] and len(pdf_b["text"]) > 10:
            mismatches.append({
                "type": "style_mismatch_bold",
                "message": "Gras manquant dans le HTML.",
                "text": pdf_b["text"][:80]
            })
        if pdf_b["has_italic"] and not html_b["has_italic"] and len(pdf_b["text"]) > 10:
            mismatches.append({
                "type": "style_mismatch_italic",
                "message": "Italique manquant dans le HTML.",
                "text": pdf_b["text"][:80]
            })
            
    # 2. Check for extra unmapped HTML blocks (e.g. headers/footers)
    matched_html_ids = {id(h_b["element"]) for p_b, h_b in aligned_pairs if h_b}
    for h_b in html_blocks:
        if id(h_b["element"]) not in matched_html_ids:
            h_text = h_b["text"]
            # Page number checks
            if re.match(r"^\d+\s*/\s*\d+$", h_text) or re.match(r"^page\s+\d+$", h_text, re.IGNORECASE):
                mismatches.append({
                    "type": "header_footer_leak",
                    "message": "Fuite d'en-tête ou de pied de page visible dans le HTML.",
                    "text": h_text
                })
            else:
                mismatches.append({
                    "type": "extra_html_block",
                    "message": "Bloc de texte présent en HTML mais absent du PDF.",
                    "text": h_text[:80]
                })
                
    # 3. Check footnotes
    pdf_footnotes = [b for b in pdf_blocks if b["role"] == "footnote"]
    if len(pdf_footnotes) != len(html_footnotes):
        mismatches.append({
            "type": "footnotes_count_mismatch",
            "message": f"Écart notes : PDF a {len(pdf_footnotes)} note(s) vs HTML a {len(html_footnotes)} note(s).",
            "text": f"PDF={len(pdf_footnotes)} | HTML={len(html_footnotes)}"
        })
        
    return mismatches

def diagnose_file(pdf_path, html_path):
    if not os.path.exists(pdf_path):
        return None, ["Fichier PDF introuvable."]
    if not os.path.exists(html_path):
        return None, ["Fichier HTML introuvable."]
        
    try:
        pdf_blocks, body_size = extract_pdf_blocks(pdf_path)
        html_blocks, html_footnotes, html_anomalies = extract_html_blocks(html_path)
        
        aligned = align_blocks(pdf_blocks, html_blocks)
        mismatches = check_mismatches(aligned, html_footnotes, pdf_blocks, html_blocks)
        
        all_anomalies = html_anomalies + mismatches
        return all_anomalies, []
    except Exception as e:
        return None, [f"Erreur de diagnostic: {str(e)}"]

def main():
    parser = argparse.ArgumentParser(description="Diagnostic géométrique visuel PDF vs HTML")
    parser.add_argument("--sample", type=int, help="Nombre de fichiers à diagnostiquer en échantillon")
    parser.add_argument("--file", type=str, help="Diagnostiquer un fichier spécifique (sans extension)")
    parser.add_argument("--output", type=str, default="layout_diagnosis_report.md", help="Nom du fichier de rapport Markdown de sortie")
    args = parser.parse_args()
    
    project_dir = r"C:\Users\paulh\OneDrive\DOCUMENTS DE TRAVAIL\AI WORK\Textes-approfondissement"
    pdf_dir = os.path.join(project_dir, "pdf")
    html_dir = os.path.join(project_dir, "data", "texts")
    
    if not os.path.exists(pdf_dir) or not os.path.exists(html_dir):
        print("Erreur: Les répertoires 'pdf/' ou 'data/texts/' sont introuvables.")
        sys.exit(1)
        
    # Get file list
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    pdf_files.sort()
    
    # Filter to ignore missing HTML files as requested by user
    active_pdf_files = []
    for f in pdf_files:
        base_name = os.path.splitext(f)[0]
        html_path = os.path.join(html_dir, f"{base_name}.html")
        if os.path.exists(html_path):
            active_pdf_files.append(f)
    pdf_files = active_pdf_files
    
    if args.file:
        target_base = args.file
        pdf_files = [f for f in pdf_files if os.path.splitext(f)[0] == target_base]
        if not pdf_files:
            print(f"Fichier '{target_base}.pdf' non trouvé dans {pdf_dir} ou version HTML manquante (ignorée)")
            sys.exit(1)
    elif args.sample:
        import random
        random.seed(42) # Deterministic sample
        pdf_files = random.sample(pdf_files, min(args.sample, len(pdf_files)))
        pdf_files.sort()
        
    print(f"Lancement du diagnostic sur {len(pdf_files)} fichier(s)...")
    
    results = {}
    errors = {}
    total_anomalies_count = 0
    files_with_anomalies = 0
    
    for idx, filename in enumerate(pdf_files):
        base_name = os.path.splitext(filename)[0]
        pdf_path = os.path.join(pdf_dir, filename)
        html_path = os.path.join(html_dir, f"{base_name}.html")
        
        print(f"[{idx+1}/{len(pdf_files)}] Diagnostic de {base_name}...")
        anomalies, file_errors = diagnose_file(pdf_path, html_path)
        
        if file_errors:
            errors[base_name] = file_errors
        elif anomalies:
            results[base_name] = anomalies
            total_anomalies_count += len(anomalies)
            files_with_anomalies += 1
            
    # Generate markdown report
    output_path = os.path.join(project_dir, args.output)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Rapport de Diagnostic Visuel Géométrique (PDF vs HTML)\n\n")
        f.write("Ce rapport liste les écarts structurels, visuels et typographiques entre les PDF originaux de référence et le formatage final HTML.\n\n")
        f.write("## Statistiques\n\n")
        f.write(f"- **Nombre total de fichiers analysés :** {len(pdf_files)}\n")
        f.write(f"- **Fichiers avec anomalies détectées :** {files_with_anomalies}\n")
        f.write(f"- **Nombre total d'anomalies :** {total_anomalies_count}\n")
        if errors:
            f.write(f"- **Fichiers avec erreurs d'analyse :** {len(errors)}\n")
        f.write("\n---\n\n")
        
        if errors:
            f.write("## Erreurs d'Exécution / Fichiers Manquants\n\n")
            for base, errs in errors.items():
                f.write(f"### {base}\n")
                for e in errs:
                    f.write(f"- ⚠️ {e}\n")
                f.write("\n")
            f.write("---\n\n")
            
        f.write("## Détail des Anomalies par Fichier\n\n")
        
        if not results:
            f.write("✅ Aucune anomalie détectée sur l'échantillon analysé !\n")
        else:
            # Group anomalies by type to show counts
            type_counts = {}
            for base, anomalies in results.items():
                for anomaly in anomalies:
                    t = anomaly["type"]
                    type_counts[t] = type_counts.get(t, 0) + 1
                    
            f.write("### Résumé par Type de Défaut\n\n")
            f.write("| Type d'Anomalie | Description | Nombre d'occurrences |\n")
            f.write("| --- | --- | --- |\n")
            descriptions = {
                "empty_element": "Paragraphe vide ou inutile",
                "inline_style": "Styles CSS en ligne (Mammoth override)",
                "role_mismatch": "Écart d'alignement visuel (ex: Titre classé en paragraphe)",
                "indent_mismatch": "Écart d'alinéa (retrait de début de paragraphe)",
                "style_mismatch_bold": "Gras manquant dans le HTML",
                "style_mismatch_italic": "Italique manquant dans le HTML",
                "header_footer_leak": "Numéros de page ou en-têtes leakés dans le HTML",
                "extra_html_block": "Texte HTML supplémentaire absent du PDF",
                "missing_html_block": "Texte PDF manquant dans le HTML (perte de contenu)",
                "footnotes_count_mismatch": "Écart sur le nombre de notes de bas de page"
            }
            for t, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                desc = descriptions.get(t, t)
                f.write(f"| `{t}` | {desc} | {count} |\n")
            f.write("\n---\n\n")
            
            # Print detailed file anomalies
            for base, anomalies in results.items():
                f.write(f"### {base}\n\n")
                f.write(f"Nombre d'anomalies : **{len(anomalies)}**\n\n")
                f.write("| Type | Message | Extrait / Détail |\n")
                f.write("| --- | --- | --- |\n")
                for a in anomalies:
                    txt_snippet = a.get("text", "").replace("\n", " ").replace("|", "\\|")
                    details = a.get("details", "")
                    content_col = f"*{txt_snippet}*"
                    if details:
                        content_col += f" ({details})"
                    f.write(f"| `{a['type']}` | {a['message']} | {content_col} |\n")
                f.write("\n")
                
    print(f"\nDiagnostic terminé ! Rapport écrit dans {output_path}")

if __name__ == "__main__":
    main()
