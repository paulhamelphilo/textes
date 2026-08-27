"""
Script d'automatisation pour ventiler les textes en attente (ID 50-99)
dans le corpus principal (ID >= 100) par ordre alphabetique de nom d'auteur,
puis renumeroter l'ensemble des textes en continu a partir de 100.
"""

import os
import sys
import shutil
import unicodedata

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
DATABASE_TSV = os.path.join(DATA_DIR, "database.tsv")

def normalize_key(text):
    """Normalize author/filename for alphabetical sorting."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    no_accent = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    cleaned = no_accent.upper().strip()
    if cleaned.startswith('BELL HOOKS'):
        cleaned = 'HOOKS ' + cleaned
    elif cleaned.startswith('DE '):
        cleaned = cleaned[3:] + ' DE'
    return cleaned

def get_author_sort_key(filename):
    """Extract and normalize the author part of a filename for sorting."""
    parts = filename.split('_')
    author_raw = parts[0].strip() if parts else ""
    return normalize_key(author_raw), normalize_key(filename)

def main():
    print("=================================================================")
    print("    VENTILATION DES NOUVEAUX TEXTES DANS LE CORPUS PRINCIPAL     ")
    print("=================================================================")

    if not os.path.exists(DATABASE_TSV):
        print(f"Erreur : La base de donnees {DATABASE_TSV} n'existe pas.")
        sys.exit(1)

    # Read database
    with open(DATABASE_TSV, "r", encoding="utf-8") as f:
        lines = [l.rstrip('\r\n').split('\t') for l in f if l.strip()]

    if not lines:
        print("La base de donnees est vide.")
        sys.exit(1)

    header = lines[0]
    data_rows = lines[1:]

    pending_rows = []
    main_rows = []

    for r in data_rows:
        try:
            tid = int(r[0])
            if 50 <= tid < 100:
                pending_rows.append(r)
            else:
                main_rows.append(r)
        except ValueError:
            main_rows.append(r)

    print(f"Textes en attente (ID 50-99) : {len(pending_rows)}")
    print(f"Textes du corpus principal   : {len(main_rows)}")

    if not pending_rows:
        print("\nAucun texte en attente (ID 50-99) a ventiler.")
        sys.exit(0)

    print("\nListe des textes a ventiler :")
    for r in pending_rows:
        print(f" - [{r[0]}] {r[1]}")

    # Combine all rows and sort by author/filename sort key
    all_rows = main_rows + pending_rows
    all_rows.sort(key=lambda r: get_author_sort_key(r[1]))

    # Renumber from 100
    for idx, r in enumerate(all_rows):
        r[0] = str(100 + idx)

    # Create backup before saving
    backup_path = os.path.join(DATA_DIR, "database.tsv.bak")
    shutil.copyfile(DATABASE_TSV, backup_path)
    print(f"\n[OK] Sauvegarde creee : {backup_path}")

    # Write updated database
    with open(DATABASE_TSV, "w", encoding="utf-8", newline='\n') as f:
        f.write('\t'.join(header) + '\n')
        for r in all_rows:
            f.write('\t'.join(r) + '\n')

    print(f"[OK] {len(pending_rows)} textes ventiles avec succes !")
    print(f"[OK] Base de donnees renumerotee : {len(all_rows)} textes (de 100 a {100 + len(all_rows) - 1}).")

if __name__ == "__main__":
    main()
