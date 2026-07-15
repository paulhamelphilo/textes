import os
import re
import sys
import argparse
import shutil
import fitz  # PyMuPDF
from bs4 import BeautifulSoup, NavigableString

# Reconfigure stdout for UTF-8 to support French accents in Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def normalize(text):
    if not text:
        return ""
    text = text.lower().replace("’", "'").replace("œ", "oe").replace("æ", "ae")
    return re.sub(r"[^a-z0-9]", "", text)

def clean_text_formatting(text):
    text = re.sub(r"([a-zA-Z\u00C0-\u017F])\s*['’]\s*([a-zA-Z\u00C0-\u017F])", r"\1’\2", text)
    text = re.sub(r"([a-zA-Z\u00C0-\u017F])\s*-\s*([a-zA-Z\u00C0-\u017F])", r"\1-\2", text)
    return text

def extract_pdf_rich_blocks(pdf_path):
    """
    Extract blocks from PDF, returning text content, role,
    and lists of bold/italic substrings within each block.
    """
    doc = fitz.open(pdf_path)
    
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
        text_blocks = sorted([b for b in blocks if "lines" in b], key=lambda x: x["bbox"][1])
        
        for b in text_blocks:
            x0, y0, x1, y1 = b["bbox"]
            
            lines_data = []
            text_parts = []
            
            bold_spans = []
            italic_spans = []
            current_bold = []
            current_italic = []
            
            for l in b["lines"]:
                lines_data.append(l["bbox"][0])
                
                line_text_parts = []
                for s in l["spans"]:
                    t = s["text"]
                    if not t.strip():
                        continue
                    
                    font_name = s["font"].lower()
                    is_b = "bold" in font_name or "bd" in font_name or (s["flags"] & 16)
                    is_i = "italic" in font_name or "ital" in font_name or "oblique" in font_name or (s["flags"] & 2)
                    
                    t_clean = clean_text_formatting(t).strip()
                    if not t_clean or len(t_clean) < 2:
                        continue
                        
                    if is_b:
                        current_bold.append(t_clean)
                    else:
                        if current_bold:
                            bold_spans.append(" ".join(current_bold))
                            current_bold = []
                            
                    if is_i:
                        current_italic.append(t_clean)
                    else:
                        if current_italic:
                            italic_spans.append(" ".join(current_italic))
                            current_italic = []
                    
                    line_text_parts.append(t)
                
                line_txt = "".join(line_text_parts)
                if line_txt.strip():
                    text_parts.append(line_txt)
                    
            if current_bold:
                bold_spans.append(" ".join(current_bold))
            if current_italic:
                italic_spans.append(" ".join(current_italic))
            
            block_text = " ".join(text_parts)
            block_text = re.sub(r"\s+", " ", block_text).strip()
            
            if not block_text:
                continue
                
            if re.match(r"^\d+\s*/\s*\d+$", block_text) or re.match(r"^\d+$", block_text):
                continue
                
            # Classifications
            mid_x = (x0 + x1) / 2
            page_mid = page_width / 2
            block_width = x1 - x0
            
            is_centered = abs(mid_x - page_mid) < 25 and block_width < 0.8 * page_width and len(block_text) < 120 and not block_text.endswith(".")
            is_right = (x1 > page_width - 80) and (x0 > page_width * 0.3) and (block_width < 0.85 * page_width)
            has_arrow = re.search(r"^.{0,12}(?:[→🡪🡺\u2190-\u21FF\u2B00-\u2BFF\U0001F800-\U0001F8FF]|)", block_text) is not None
            if has_arrow:
                is_right = True
                
            block_sizes = [s["size"] for l in b["lines"] for s in l["spans"] if s["text"].strip()]
            avg_size = sum(block_sizes) / len(block_sizes) if block_sizes else body_size
            is_footnote = (y0 > page_height - 180) and (avg_size < body_size - 1.2)
            
            has_indent = False
            if len(lines_data) > 1:
                has_indent = lines_data[0] > lines_data[1] + 12
                
            is_subheading = False
            if not is_centered and not is_right and not is_footnote:
                has_bold_span = len(bold_spans) > 0
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
                
            # Filter clean list of bold/italic spans
            bold_spans = [clean_text_formatting(s) for s in bold_spans if len(s.strip()) > 3]
            italic_spans = [clean_text_formatting(s) for s in italic_spans if len(s.strip()) > 3]
            
            pdf_blocks.append({
                "text": block_text,
                "role": role,
                "has_indent": has_indent,
                "bold_spans": bold_spans,
                "italic_spans": italic_spans,
                "page": page_num,
                "bbox": (x0, y0, x1, y1)
            })
            
    return pdf_blocks

def extract_html_paragraphs(soup):
    """
    Extract HTML paragraphs and elements (excluding footnotes).
    Returns list of parsed elements.
    """
    elements = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"])
    html_blocks = []
    
    for el in elements:
        if el.find_parent(class_="footnotes") or el.find_parent("div", class_="footnotes") or el.get("id", "").startswith("footnote"):
            continue
        if el.find_parent(["table", "ul", "ol", "li"]):
            continue
            
        el_text = re.sub(r"\s+", " ", el.get_text()).strip()
        if not el_text:
            continue
            
        html_blocks.append({
            "text": el_text,
            "element": el
        })
    return html_blocks

def align_blocks(pdf_blocks, html_blocks):
    """
    Match PDF blocks to HTML blocks using text similarity.
    """
    aligned = []
    html_idx = 0
    
    for p_block in pdf_blocks:
        p_norm = normalize(p_block["text"])
        if not p_norm:
            continue
            
        best_match_idx = -1
        best_score = 0
        
        for search_idx in range(html_idx, min(html_idx + 6, len(html_blocks))):
            h_block = html_blocks[search_idx]
            h_norm = normalize(h_block["text"])
            
            if p_norm == h_norm:
                score = 1.0
            elif p_norm in h_norm or h_norm in p_norm:
                score = min(len(p_norm), len(h_norm)) / max(len(p_norm), len(h_norm))
            else:
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

def make_fuzzy_regex(target_text):
    # Escape all special characters safely
    escaped = re.escape(target_text)
    # Replace literal spaces and escaped spaces with \s* to support space variance
    escaped = escaped.replace(r"\ ", r"\s*").replace(" ", r"\s*")
    # Replace literal and escaped apostrophes with ['’]\s* to handle straight vs curly quotes
    escaped = escaped.replace(r"\'", r"['’]\s*").replace(r"\’", r"['’]\s*").replace("'", r"['’]\s*").replace("’", r"['’]\s*")
    return re.compile(escaped, re.IGNORECASE)

def wrap_text_in_tag(element, target_text, tag_name):
    """
    DOM-safe insertion of <strong> or <em> tags within elements.
    Recursively checks text nodes to prevent wrapping already formatted spans.
    Uses fuzzy regex to match text with slight space/punctuation variance.
    """
    if not target_text or len(target_text.strip()) < 3:
        return False
        
    modified = False
    children = list(element.contents)
    
    # Compile fuzzy regex for matching target text
    regex = make_fuzzy_regex(target_text)
    
    for child in children:
        if isinstance(child, str):
            text_val = str(child)
            
            # Fuzzy match
            match = regex.search(text_val)
            if match:
                match_str = match.group(0)
                # Check parents to avoid double wrapping
                parent = child.parent
                already_wrapped = False
                while parent and parent != element:
                    if parent.name in ["strong", "b"] and tag_name == "strong":
                        already_wrapped = True
                        break
                    if parent.name in ["em", "i"] and tag_name == "em":
                        already_wrapped = True
                        break
                    parent = parent.parent
                    
                if already_wrapped:
                    continue
                    
                parts = text_val.split(match_str, 1)
                before_text = parts[0]
                after_text = parts[1]
                
                new_tag = BeautifulSoup(f"<{tag_name}>{match_str}</{tag_name}>", "html.parser").find(tag_name)
                
                try:
                    idx = element.contents.index(child)
                    child.extract()
                    
                    if after_text:
                        element.insert(idx, after_text)
                    element.insert(idx, new_tag)
                    if before_text:
                        element.insert(idx, before_text)
                        
                    modified = True
                    break  # Stop processing this text node to prevent index conflicts
                except ValueError:
                    # element contents index mismatch
                    continue
                    
        elif hasattr(child, "contents"):
            if child.name in ["strong", "b"] and tag_name == "strong":
                continue
            if child.name in ["em", "i"] and tag_name == "em":
                continue
                
            if wrap_text_in_tag(child, target_text, tag_name):
                modified = True
                
    return modified

def enrich_file(pdf_path, html_path):
    """
    Enrich an HTML file using metadata extracted from its PDF version.
    """
    if not os.path.exists(pdf_path) or not os.path.exists(html_path):
        return False, "Fichier PDF ou HTML introuvable."
        
    try:
        pdf_blocks = extract_pdf_blocks_or_spans = extract_pdf_rich_blocks(pdf_path)
        
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        soup = BeautifulSoup(html_content, "html.parser")
        html_blocks = extract_html_paragraphs(soup)
        
        aligned = align_blocks(pdf_blocks, html_blocks)
        
        modified = False
        bold_added = 0
        italic_added = 0
        
        for pdf_b, html_b in aligned:
            if not html_b:
                continue
                
            html_element = html_b["element"]
            
            # Apply bold spans
            for bold_span in pdf_b["bold_spans"]:
                if wrap_text_in_tag(html_element, bold_span, "strong"):
                    modified = True
                    bold_added += 1
                    
            # Apply italic spans
            for italic_span in pdf_b["italic_spans"]:
                if wrap_text_in_tag(html_element, italic_span, "em"):
                    modified = True
                    italic_added += 1
                    
        if modified:
            # Save backup first
            backup_path = html_path + ".bak"
            if not os.path.exists(backup_path):
                shutil.copyfile(html_path, backup_path)
                
            # Write updated HTML
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(str(soup))
                
            return True, f"Enrichi avec succès : +{bold_added} gras, +{italic_added} italiques."
        else:
            return False, "Aucun changement requis (déjà conforme)."
            
    except Exception as e:
        import traceback
        return False, f"Erreur lors de l'enrichissement : {str(e)}\n{traceback.format_exc()}"

def main():
    parser = argparse.ArgumentParser(description="Enrichissement automatique du formatage HTML à partir des PDF")
    parser.add_argument("--sample", type=int, help="Nombre de fichiers à enrichir en échantillon")
    parser.add_argument("--file", type=str, help="Enrichir un fichier spécifique (sans extension)")
    args = parser.parse_args()
    
    project_dir = r"C:\Users\paulh\OneDrive\DOCUMENTS DE TRAVAIL\AI WORK\Textes-approfondissement"
    pdf_dir = os.path.join(project_dir, "pdf")
    html_dir = os.path.join(project_dir, "data", "texts")
    
    if not os.path.exists(pdf_dir) or not os.path.exists(html_dir):
        print("Erreur: Les répertoires 'pdf/' ou 'data/texts/' sont introuvables.")
        sys.exit(1)
        
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    pdf_files.sort()
    
    # Filter to ignore missing HTML files
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
            print(f"Fichier '{target_base}.pdf' non trouvé ou version HTML manquante.")
            sys.exit(1)
    elif args.sample:
        import random
        random.seed(42)
        pdf_files = random.sample(pdf_files, min(args.sample, len(pdf_files)))
        pdf_files.sort()
        
    print(f"Lancement de l'enrichissement typographique sur {len(pdf_files)} fichier(s)...")
    
    enriched_count = 0
    skipped_count = 0
    error_count = 0
    
    for idx, filename in enumerate(pdf_files):
        base_name = os.path.splitext(filename)[0]
        pdf_path = os.path.join(pdf_dir, filename)
        html_path = os.path.join(html_dir, f"{base_name}.html")
        
        success, message = enrich_file(pdf_path, html_path)
        
        if success:
            enriched_count += 1
            print(f"[{idx+1}/{len(pdf_files)}] {base_name} : ✅ {message}")
        else:
            if "Erreur" in message:
                error_count += 1
                print(f"[{idx+1}/{len(pdf_files)}] {base_name} : ❌ {message}")
            else:
                skipped_count += 1
                print(f"[{idx+1}/{len(pdf_files)}] {base_name} : ⚪ {message}")
                
    print(f"\nTerminé ! Enrichis : {enriched_count} | Ignorés/Déjà conformes : {skipped_count} | Erreurs : {error_count}")

if __name__ == "__main__":
    main()
