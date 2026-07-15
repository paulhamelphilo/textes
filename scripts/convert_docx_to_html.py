import os
import sys
import subprocess

# Reconfigure stdout for UTF-8 to support French accents in Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 1. Automatically check and install mammoth
def check_dependencies():
    try:
        import mammoth
    except ImportError:
        print("Bibliothèque 'mammoth' manquante. Installation en cours...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "mammoth"])
            print("Bibliothèque 'mammoth' installée avec succès !")
        except Exception as e:
            print(f"Erreur lors de l'installation de mammoth: {e}")
            print("Veuillez installer manuellement : pip install mammoth")
            sys.exit(1)

check_dependencies()
import mammoth

def main():
    cwd = os.getcwd()
    print(f"Recherche des fichiers dans : {cwd}")
    
    docx_files = [f for f in os.listdir(cwd) if f.endswith(".docx") and not f.startswith("~$")]
    
    if not docx_files:
        print("Aucun fichier .docx trouvé dans ce dossier.")
        return
        
    print(f"Trouvé {len(docx_files)} fichier(s) .docx.")
    
    # Create output directory
    output_dir = os.path.join(cwd, "converted_html")
    os.makedirs(output_dir, exist_ok=True)
    
    success_count = 0
    for filename in docx_files:
        filepath = os.path.join(cwd, filename)
        filename_no_ext = os.path.splitext(filename)[0]
        output_filepath = os.path.join(output_dir, f"{filename_no_ext}.html")
        
        print(f"Conversion de : {filename}...")
        try:
            with open(filepath, "rb") as docx_file:
                # convert with underline support mapped to <u>
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
                
            with open(output_filepath, "w", encoding="utf-8") as out_file:
                out_file.write(html_content)
            success_count += 1
        except Exception as e:
            print(f"Erreur lors de la conversion de {filename}: {e}")
                
    print(f"\nConversion terminée avec succès : {success_count}/{len(docx_files)} fichiers !")
    print(f"Les fichiers HTML convertis se trouvent dans : {output_dir}")
    print("Vous pouvez copier ces fichiers .html dans le dossier 'data/texts/' de votre application.")

if __name__ == "__main__":
    main()
