import fitz
import os
import re
import sys

# Configure directories
project_dir = r"C:\Users\paulh\OneDrive\DOCUMENTS DE TRAVAIL\AI WORK\Textes-approfondissement"
pdf_dir = os.path.join(project_dir, "pdf")
texts_dir = os.path.join(project_dir, "data", "texts")

def clean_text_formatting(text):
    # Remove spacing around apostrophes (e.g. "l ' homme" -> "l'homme")
    text = re.sub(r"([a-zA-Z\u00C0-\u017F])\s*['’]\s*([a-zA-Z\u00C0-\u017F])", r"\1’\2", text)
    # Remove spacing around hyphens in compound words (e.g. "peut - être" -> "peut-être")
    text = re.sub(r"([a-zA-Z\u00C0-\u017F])\s*-\s*([a-zA-Z\u00C0-\u017F])", r"\1-\2", text)
    # Specific OCR repairs
    text = re.sub(r"\bim\s+médiat", "immédiat", text, flags=re.IGNORECASE)
    text = re.sub(r"\bremp\s+lace", "remplace", text, flags=re.IGNORECASE)
    return text

def extract_rich_text(pdf_path):
    doc = fitz.open(pdf_path)
    
    # 1. First pass: find dominant font size
    sizes = {}
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        sz = round(s["size"], 1)
                        if s["text"].strip():
                            sizes[sz] = sizes.get(sz, 0) + len(s["text"])
    
    body_size = max(sizes, key=sizes.get) if sizes else 12.0
    
    paragraphs = []
    footnotes = []
    
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        # Filter for text blocks and sort top-to-bottom
        text_blocks = sorted([b for b in blocks if "lines" in b], key=lambda x: x["bbox"][1])
        
        for b in text_blocks:
            y0, y1 = b["bbox"][1], b["bbox"][3]
            
            # Determine if this block is a footnote
            # Criteria: y0 > 660 (A4 height is 842), and average font size is smaller than body_size
            block_sizes = [s["size"] for l in b["lines"] for s in l["spans"] if s["text"].strip()]
            avg_size = sum(block_sizes) / len(block_sizes) if block_sizes else body_size
            
            # Check text content of block
            block_text_raw = " ".join([s["text"] for l in b["lines"] for s in l["spans"]]).strip()
            
            # Ignore headers/footers like page numbers
            if re.match(r"^\d+\s*/\s*\d+$", block_text_raw) or re.match(r"^\d+$", block_text_raw):
                continue
                
            is_footnote = False
            if y0 > 660 and avg_size < body_size - 1.5:
                is_footnote = True
            
            # Process spans in block
            block_lines_processed = []
            for l in b["lines"]:
                line_spans_processed = []
                for s in l["spans"]:
                    txt = s["text"]
                    if not txt:
                        continue
                        
                    # Check styles
                    is_italic = "italic" in s["font"].lower() or "ital" in s["font"].lower() or "oblique" in s["font"].lower() or (s["flags"] & 2)
                    is_bold = "bold" in s["font"].lower() or "bd" in s["font"].lower() or (s["flags"] & 16)
                    is_super = (s["flags"] & 1) or (s["size"] < body_size - 2.5 and s["bbox"][1] < l["bbox"][1] + 2) # superscript
                    
                    # Normalize Wingdings arrows
                    if s["font"].lower().startswith("wingdings") or txt in ["à", "", "\uf0e0", "\uF0E0"]:
                        txt = "→"
                        
                    # Clean text
                    txt = clean_text_formatting(txt)
                    
                    # Apply HTML tags
                    if is_super and txt.strip().isdigit():
                        txt = f"<sup>{txt.strip()}</sup>"
                    else:
                        # Only apply styles if there is actual alphanumeric text
                        if re.search(r"\w", txt):
                            if is_italic and is_bold:
                                txt = f"<b><i>{txt}</i></b>"
                            elif is_italic:
                                txt = f"<i>{txt}</i>"
                            elif is_bold:
                                txt = f"<b>{txt}</b>"
                                
                    line_spans_processed.append(txt)
                
                line_txt = "".join(line_spans_processed)
                if line_txt.strip():
                    block_lines_processed.append(line_txt)
            
            # Join lines in block
            block_content = " ".join(block_lines_processed)
            block_content = re.sub(r"\s+", " ", block_content).strip()
            
            # Clean up nested or adjacent style tags
            block_content = re.sub(r"</i>\s*<i>", " ", block_content)
            block_content = re.sub(r"</b>\s*<b>", " ", block_content)
            block_content = re.sub(r"</i>\s*→", "→", block_content) # clean up trailing tags near arrow
            
            if block_content:
                if is_footnote:
                    footnotes.append(block_content)
                else:
                    paragraphs.append(block_content)
                    
    # Format final output & merge reference lines consecutive blocks
    final_blocks = []
    i = 0
    while i < len(paragraphs):
        p = paragraphs[i]
        
        # Check if this paragraph starts a reference (ignoring surrounding tags)
        clean_p = re.sub(r"<[^>]+>", "", p).strip()
        is_ref_start = clean_p.startswith("→")
        
        if is_ref_start:
            # Clean leading arrow tag styling
            p = re.sub(r"^(<b>|<i>|<b><i>)?→(</b>|</i>|</i></b>)?", "→", p)
            ref_lines = [p]
            i += 1
            
            # Look ahead to group continuation lines of the reference
            while i < len(paragraphs):
                next_p = paragraphs[i]
                
                # Strip HTML tags for checking next block properties
                clean_prev = re.sub(r"<[^>]+>", "", ref_lines[-1]).strip()
                clean_next = re.sub(r"<[^>]+>", "", next_p).strip()
                
                # Check continuation triggers
                ends_with_comma = clean_prev.endswith(",") or clean_prev.endswith(";") or clean_prev.endswith(":") or clean_prev.endswith("-")
                starts_with_lower = clean_next and clean_next[0].islower()
                starts_with_paren = clean_next and clean_next[0] in ["(", "["]
                is_translator = re.match(r"^(Trad\.|Traduction)", clean_next, re.IGNORECASE) is not None
                
                # A subheading block shouldn't merge
                is_next_subheading = (len(clean_next) < 75 and 
                                     not re.search(r"[.!?»]$", clean_next) and 
                                     re.match(r"^[A-ZÀ-Ÿ]", clean_next) and
                                     not re.match(r"^(Trad\.|Traduction|Tome|Vol\.|Ed\.|Éd\.|p\.|Page|Chapitre|col\.)", clean_next, re.IGNORECASE))
                
                is_next_block_start = (clean_next.startswith("«") or 
                                       clean_next.startswith("→") or 
                                       clean_next.startswith("*") or 
                                       clean_next.startswith("N.B."))
                
                # Decide if we should merge next_p
                should_merge = False
                if not is_next_block_start:
                    if ends_with_comma or starts_with_lower or starts_with_paren or is_translator:
                        should_merge = True
                    elif not is_next_subheading:
                        should_merge = True
                        
                if not should_merge:
                    break
                    
                ref_lines.append(next_p)
                i += 1
                
            # Join the reference lines with a single newline (tells JS parser it's the same block)
            final_blocks.append("\n".join(ref_lines))
        else:
            final_blocks.append(p)
            i += 1
        
    if footnotes:
        final_blocks.append("[[FOOTNOTES]]")
        for fn in footnotes:
            final_blocks.append(fn)
            
    return "\n\n".join(final_blocks)

def main():
    if not os.path.exists(pdf_dir):
        print(f"Error: {pdf_dir} does not exist")
        sys.exit(1)
        
    os.makedirs(texts_dir, exist_ok=True)
    
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    print(f"Found {len(pdf_files)} PDF files in project pdf directory.")
    
    count = 0
    for filename in pdf_files:
        filename_no_ext = os.path.splitext(filename)[0]
        pdf_path = os.path.join(pdf_dir, filename)
        txt_path = os.path.join(texts_dir, f"{filename_no_ext}.txt")
        
        try:
            rich_text = extract_rich_text(pdf_path)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(rich_text)
            count += 1
            if count % 50 == 0 or count == len(pdf_files):
                print(f"Processed {count}/{len(pdf_files)} files...")
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            
    print(f"Successfully re-extracted {count} files with formatting.")

if __name__ == "__main__":
    main()
