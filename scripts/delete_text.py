import os
import sys

# Setup directories
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
TEXTS_DIR = os.path.join(DATA_DIR, "texts")
PDF_DIR = os.path.join(PROJECT_DIR, "pdf")
DATABASE_TSV = os.path.join(DATA_DIR, "database.tsv")

def main():
    print("=================================================================")
    print("    MEMENTO-IA : SUPPRESSION D'UN TEXTE PHILOSOPHIQUE            ")
    print("=================================================================")
    
    if not os.path.exists(DATABASE_TSV):
        print(f"Erreur : La base de données {DATABASE_TSV} n'existe pas.")
        sys.exit(1)
        
    # Read database
    rows = []
    header = ""
    try:
        with open(DATABASE_TSV, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            if lines:
                header = lines[0]
                for line in lines[1:]:
                    if line.strip():
                        rows.append(line.split("\t"))
    except Exception as e:
        print(f"Erreur lors de la lecture de la base de données : {e}")
        sys.exit(1)
        
    print(f"Nombre de textes actuellement enregistrés : {len(rows)}")
    
    user_input = input("\nEntrez l'identifiant (ID) ou le nom du fichier du texte à supprimer :\n> ").strip()
    if not user_input:
        print("Saisie vide. Fin du programme.")
        sys.exit(0)
        
    # Find matching row
    matched_row = None
    matched_idx = -1
    
    for idx, row in enumerate(rows):
        if len(row) > 1:
            # Match by ID or by filename
            if row[0] == user_input or row[1] == user_input or row[1].lower() == user_input.lower():
                matched_row = row
                matched_idx = idx
                break
                
    if matched_row is None:
        print(f"[-] Aucun texte trouve correspondant a : '{user_input}'.")
        sys.exit(1)
        
    text_id = matched_row[0]
    filename = matched_row[1]
    analysis = matched_row[2] if len(matched_row) > 2 else ""
    
    print("\n--- TEXTE TROUVE ---")
    print(f"Identifiant : {text_id}")
    print(f"Fichier     : {filename}")
    if analysis:
        # Show first 120 chars of analysis
        print(f"Analyse     : {analysis[:120]}...")
        
    confirm = input(f"\n[!] Attention : Voulez-vous vraiment supprimer ce texte et ses fichiers HTML/PDF associes ? (o/N) : ").strip().lower()
    if confirm != 'o':
        print("Suppression annulee.")
        sys.exit(0)
        
    # Remove from rows list
    del rows[matched_idx]
    
    # Save database
    try:
        with open(DATABASE_TSV, "w", encoding="utf-8") as f:
            f.write(header + "\n")
            for row in rows:
                f.write("\t".join(row) + "\n")
        print("-> Base de donnees database.tsv mise a jour.")
    except PermissionError:
        print("\n[Erreur] Acces refuse a database.tsv.")
        print("Le fichier est probablement ouvert dans Microsoft Excel.")
        print("Veuillez fermer Excel et relancer le programme.")
        sys.exit(1)
    except Exception as e:
        print(f"Erreur ecriture base de donnees : {e}")
        sys.exit(1)
        
    # Remove files
    html_file = os.path.join(TEXTS_DIR, f"{filename}.html")
    pdf_file = os.path.join(PDF_DIR, f"{filename}.pdf")
    
    files_deleted = 0
    for path in [html_file, pdf_file]:
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"-> Fichier supprime : {os.path.basename(path)}")
                files_deleted += 1
            except Exception as e:
                print(f"Impossible de supprimer {os.path.basename(path)} : {e}")
                
    print("\n=================================================================")
    print("    SYNTHESE DE LA SUPPRESSION                                   ")
    print("=================================================================")
    print(f"Texte ID {text_id} ('{filename}') supprime de la base.")
    print(f"Nombre de fichiers supprimes : {files_deleted}")
    print("=================================================================")
    print("N'oubliez pas de recharger la page web de votre navigateur.")

if __name__ == "__main__":
    main()
