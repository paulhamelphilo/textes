/**
 * MENTOR-IA / Textes-approfondissement Client Application
 * Handles loading TSV database, filtering (Auteur, Notion, text search),
 * dynamic text loading, routing, and styling preferences.
 */

// Application state
const state = {
    texts: [],          // Full list of parsed texts from TSV
    filteredTexts: [],  // Currently filtered list
    selectedAuthor: null,
    selectedNotion: null,
    activeTextId: null,
    preselectedTextId: null, // Track currently preselected card
    fontSize: 18,       // Default reader font size (px)
};

// Utility helper functions
/**
 * Applique la typographie française UNIQUEMENT sur les nœuds texte d'une
 * chaîne HTML, sans toucher aux balises ni aux attributs.
 */
function formatFrenchTypography(str) {
    if (!str) return '';
    
    // Remplacer en ne ciblant QUE les portions texte (entre balises)
    return str.replace(/(<[^>]*>)|([^<]+)/g, (match, tag, text) => {
        if (tag) return tag; // Conserver les balises intactes
        if (!text) return text;
        
        // 1. Apostrophes droites → apostrophes typographiques
        let result = text.replace(/(?<=[a-zA-Z\u00C0-\u017F\d])'/g, '\u2019');
        
        // 2. Guillemets droits "..." → guillemets français «\u00A0...\u00A0»
        result = result.replace(/"([^"]+)"/g, '\u00AB\u00A0$1\u00A0\u00BB');
        
        // 3. Guillemets français déjà présents : espace insécable après « et avant »
        result = result.replace(/\u00AB\s*/g, '\u00AB\u00A0');
        result = result.replace(/\s*\u00BB/g, '\u00A0\u00BB');
        
        // 4. Deux-points : espace insécable avant (pas dans les URLs ni les heures)
        result = result.replace(/(?<!\d)\s*:\s*(?!\d|\/)/g, '\u00A0: ');
        
        // 5. Point-virgule : espace insécable avant
        result = result.replace(/([a-zA-Z\u00C0-\u017F\d])\s*;+\s*/g, '$1\u00A0; ');
        
        // 6. Point d'exclamation : espace insécable avant
        result = result.replace(/([a-zA-Z\u00C0-\u017F\d])\s*(!+)/g, '$1\u00A0$2');
        
        // 7. Point d'interrogation : espace insécable avant
        result = result.replace(/([a-zA-Z\u00C0-\u017F\d])\s*(\?+)/g, '$1\u00A0$2');
        
        return result;
    });
}

function formatTitleSentenceCase(str) {
    if (!str) return '';
    
    // Check if the string is all uppercase (excluding punctuation, numbers, spaces)
    const lettersOnly = str.replace(/[^a-zA-Z\u00C0-\u017F]/g, '');
    if (lettersOnly.length === 0 || lettersOnly !== lettersOnly.toUpperCase()) {
        return str; // Not all uppercase
    }
    
    // Lowercase everything
    let result = str.toLowerCase();
    
    // Capitalize the first letter (skipping leading symbols/quotes)
    result = result.replace(/^([^a-zA-Z\u00C0-\u017F]*)([a-zA-Z\u00C0-\u017F])/, (m, p1, p2) => p1 + p2.toUpperCase());
    
    // Capitalize known proper nouns in the database to be clean
    const properNouns = [
        'alain', 'aristote', 'badiou', 'barthes', 'baudrillard', 'benjamin', 'bentham', 
        'bergson', 'berkeley', 'bible', 'bourdieu', 'boëda', 'chalmers', 'charbonnier', 
        'châtelet', 'chollet', 'cicéron', 'clastres', 'clément', 'cohen', 'comte-sponville', 
        'corpus', 'crawford', 'daudet', 'daumal', 'de montaigne', 'descartes', 'de beauvoir', 
        'de funès', 'diderot', 'ducros', 'duras', 'durkheim', 'ecclésiaste', 'einstein', 
        'ellul', 'encinas', 'goyard-fabre', 'tap-pierre', 'encyclopédie', 'engels', 'épicure', 
        'faye', 'ferry', 'filliozat', 'foucault', 'fraisse', 'frankfurt', 'freud', 'pages', 
        'froideveaux-metterie', 'galluzzo', 'garcia', 'gide', 'girard', 'godin', 'gracian', 
        'grimaldi', 'gros', 'hamilton', 'hefez', 'hegel', 'hempel', 'hersch', 'hobbes', 
        'houellebecq', 'hugo', 'hume', 'huxley', 'hölderlin', 'illouz', 'benger', 'alaluf', 
        'west', 'james', 'jankélévitch', 'jaspers', 'kant', 'klein', 'koyré', 'kundera', 
        'la rochefoucauld', 'lacan', 'lafargue', 'lagasgnerie', 'lao-tseu', 'laplace', 'leibniz', 
        'locke', 'lucrèce', 'léotard', 'lévi-strauss', 'machiavel', 'malherbe', 'marx', 'mauss', 
        'mead', 'mill', 'mirbeau', 'montaigne', 'montesquieu', 'morice', 'mouy', 'nagel', 
        'newton', 'nietzsche', 'nozick', 'nussbaum', 'ovide', 'pascal', 'pessoa', 'platon', 
        'pline', 'popper', 'proust', 'prévost', 'putnam', 'rosenberg', 'rousseau', 'russell', 
        'sartre', 'schopenhauer', 'sen', 'serres', 'sextus', 'smith', 'spinoza', 'testart', 
        'thoreau', 'tocqueville', 'tournier', 'valéry', 'voltaire', 'weil', 'yourcenar', 
        'zamiatine', 'zeniter', 'zeuxis'
    ];
    
    properNouns.forEach(noun => {
        const regex = new RegExp(`\\b${noun}\\b`, 'gi');
        result = result.replace(regex, match => {
            return match.split('-').map(part => part.charAt(0).toUpperCase() + part.slice(1)).join('-');
        });
    });
    
    // Also capitalize roman numerals
    result = result.replace(/\b(i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx)\b/gi, m => m.toUpperCase());
    
    return result;
}

function formatTitleListSeparators(str, id) {
    if (!str) return '';
    
    // Split by / or ;
    if (str.includes('/') || str.includes(';')) {
        const delimiter = str.includes('/') ? '/' : ';';
        return str.split(delimiter)
            .map(p => p.trim())
            .filter(p => p.length > 0)
            .map(p => p.charAt(0).toUpperCase() + p.slice(1))
            .join(' \u2013 '); // \u2013 is '–'
    }
    
    // Split by comma for known concept list IDs
    const knownListIds = [170, 261, 322, 582];
    if (str.includes(',') && knownListIds.includes(Number(id))) {
        return str.split(',')
            .map(p => p.trim())
            .filter(p => p.length > 0)
            .map(p => p.charAt(0).toUpperCase() + p.slice(1))
            .join(' \u2013 ');
    }
    
    return str;
}

function removeAccents(str) {
    if (!str) return '';
    return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function isMobileDevice() {
    return window.matchMedia("(max-width: 1024px)").matches || 
           /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
           ('ontouchstart' in window) || 
           (navigator.maxTouchPoints > 0);
}

function setPreselectedText(id) {
    state.preselectedTextId = id;
    
    // Remove selected class from all cards
    document.querySelectorAll('.text-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    if (id !== null) {
        const cardEl = document.querySelector(`.text-card[data-id="${id}"]`);
        if (cardEl) {
            cardEl.classList.add('selected');
            // Scroll into view if not fully visible
            cardEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    }
}

/**
 * Extrait le texte brut d'une chaîne HTML (supprime les balises)
 * pour la classification des blocs, sans altérer le contenu HTML source.
 */
function stripHTML(html) {
    if (!html) return '';
    return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

/**
 * Point d'entrée principal : sépare corps et notes de bas de page,
 * puis rend chacun en HTML.
 */
function parseTextToHTML(rawText, author) {
    if (!rawText) return '';
    
    // Séparer le corps et les notes de bas de page
    const parts = rawText.split('[[FOOTNOTES]]');
    const bodyRawText = parts[0];
    const footnotesRawText = parts[1] || '';
    
    const bodyHTML = parseBodyToHTML(bodyRawText, author);
    
    let footnotesHTML = '';
    if (footnotesRawText.trim()) {
        const lines = footnotesRawText.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
        if (lines.length > 0) {
            footnotesHTML = `<div class="footnotes">` + lines.map(line => {
                return `<div class="footnote-item">${formatFrenchTypography(line)}</div>`;
            }).join('') + `</div>`;
        }
    }
    
    return bodyHTML + footnotesHTML;
}

/**
 * Traite le HTML brut chargé depuis un fichier extrait de DOCX.
 * Applique la typographie française et identifie titre & références.
 */
/**
 * Helper to check if a paragraph is wrapped entirely in strong/b tags
 */
function isStrongTitle(el) {
    const activeChildren = Array.from(el.childNodes).filter(node => {
        return node.nodeType !== Node.TEXT_NODE || node.textContent.trim().length > 0;
    });
    if (activeChildren.length === 1) {
        const child = activeChildren[0];
        return child.nodeName === 'STRONG' || child.nodeName === 'B';
    }
    return false;
}

/**
 * Heuristique pour déterminer si un paragraphe ressemble à un titre
 */
function isTitleLike(plainText, isLast) {
    if (isLast) return false;
    
    // Nettoyer les espaces de fin
    let plain = plainText.trim();
    if (!plain) return false;
    
    // Supprimer les numéros de page ou notes à la fin en crochets/parenthèses (ex: [494c], (494c))
    plain = plain.replace(/\s*[\[\(]\d+[a-f]?[\]\)]\s*$/gi, '').trim();
    
    // Nettoyer les guillemets, crochets, parenthèses et espaces résiduels des deux côtés
    plain = plain.replace(/^[«»"“’\s\t\(\)\[\]\{\}]+|[«»"“’\s\t\(\)\[\]\{\}]+$/g, '').trim();
    if (!plain) return false;
    
    // Doit commencer par une lettre ou un chiffre
    const startsWithLetterOrDigit = /^[a-zA-Z0-9À-ÿŒœ]/u.test(plain);
    if (!startsWithLetterOrDigit) return false;
    
    // Un titre est court (inférieur à 100 caractères)
    if (plain.length > 100) return false;
    
    // S'il se termine par un point, point d'exclamation, point d'interrogation, deux-points ou point-virgule, c'est une phrase de corps ou de dialogue, pas un titre
    const endsWithPunctuation = /[.!?;:]$/.test(plain);
    if (endsWithPunctuation) return false;
    
    // Mots-clés excluant le fait d'être un titre (on n'exclut plus 'chapitre', 'tome', 'vol')
    const titleExcludeKeywords = ['trad', 'traduction', 'éd', 'ed', 'p.', 'page', 'col.'];
    const plainLower = plain.toLowerCase();
    if (titleExcludeKeywords.some(kw => plainLower.startsWith(kw))) {
        return false;
    }
    
    return true;
}

/**
 * Traite le HTML brut chargé depuis un fichier extrait de DOCX.
 * Applique la typographie française et identifie titre & références.
 */
function processLoadedHTML(rawHtml, author) {
    if (!rawHtml) return '';
    
    // 1. Appliquer la typographie française sur les portions texte (HTML-aware)
    const htmlWithTypo = formatFrenchTypography(rawHtml);
    
    // 2. Parser le HTML pour manipuler le DOM
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlWithTypo, 'text/html');
    
    // Wrap ol elements containing footnote items in a div.footnotes
    const olElements = doc.body.querySelectorAll('ol');
    olElements.forEach(ol => {
        if (ol.querySelector('li[id^="footnote"]')) {
            if (!ol.parentElement.classList.contains('footnotes')) {
                const wrapper = doc.createElement('div');
                wrapper.className = 'footnotes';
                ol.parentNode.insertBefore(wrapper, ol);
                wrapper.appendChild(ol);
            }
        }
    });

    // SVG pour l'icône flèche
    const arrowSVG = `<svg class="ref-arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"
        style="display:inline-block;vertical-align:middle;margin-right:6px;width:1.1em;height:1.1em;color:var(--accent);">
        <line x1="4" y1="12" x2="20" y2="12"></line>
        <polyline points="13 5 20 12 13 19"></polyline></svg>`;
        
    let afterReference = false;
    let firstTitleFound = false;
    let inBody = false;
    const refKeywords = ['trad', 'traduction', 'tome', 'vol', 'éd', 'ed', 'p.', 'page', 'chapitre', 'col.'];
    
    const elements = doc.body.querySelectorAll('p, h1, h2, h3, h4, h5, h6');
    const totalCount = elements.length;
    
    elements.forEach((el, idx) => {
        // Nettoyage des styles en ligne parasites pour éviter d'écraser la charte graphique de l'application
        el.removeAttribute('style');
        el.querySelectorAll('[style]').forEach(child => child.removeAttribute('style'));

        // Ignorer les éléments des notes de bas de page
        if (el.closest('.footnotes') || el.closest('li[id^="footnote"]')) return;

        // Ignorer les éléments dans les tables ou listes pour préserver leur structure
        if (el.closest('table') || el.closest('ul') || el.closest('ol') || el.closest('li')) {
            el.className = '';
            el.classList.add('text-body-simple');
            return;
        }

        const plainText = el.textContent.trim();
        if (!plainText) return;
        
        const isLast = (idx === totalCount - 1);
        const isHeading = ['H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(el.tagName);
        const isStrong = isStrongTitle(el);
        
        // Détection de dialogue (speakers et directions)
        let isSpeaker = false;
        let isDirection = false;
        
        if ((plainText.startsWith('[') && plainText.endsWith(']')) || (plainText.startsWith('(') && plainText.endsWith(')'))) {
            isDirection = true;
        } else {
            const cleaned = plainText.replace(/^[«»"“’\s\t\(\)\[\]\{\}]+|[«»"“’\s\t\(\)\[\]\{\}]+$/g, '').trim();
            if (cleaned.length > 0 && cleaned.length < 35) {
                const isAllUpper = cleaned === cleaned.toUpperCase() && /[A-ZÀ-Ÿ]/.test(cleaned);
                const isLetterOnly = /^[\p{L}\s’'\-]+$/u.test(cleaned);
                if (isAllUpper && isLetterOnly) {
                    isSpeaker = true;
                }
            }
        }
        
        // Détection si l'on entre dans le corps du texte
        if (!inBody) {
            const startsWithQuote = /^\s*«/u.test(plainText);
            const isLongText = plainText.length > 150;
            if (startsWithQuote || isLongText || isSpeaker || isDirection) {
                inBody = true;
            }
        }
        
        // Détection de flèche (référence)
        const isArrowRef = /^\s*(?:[→🡪🡺\u2190-\u21FF\u2B00-\u2BFF\u{1F800}-\u{1F8FF}]|&rarr;|&#8594;)/u.test(plainText);
        
        // Détection de continuation de référence
        let isRefCont = false;
        if (afterReference) {
            const cleanPlain = plainText.replace(/^[«»"“’\s\t\(\)\[\]\{\}\-\+~≈]+/, '');
            const firstChar = cleanPlain.charAt(0);
            const isLower = firstChar && firstChar === firstChar.toLowerCase() && firstChar !== firstChar.toUpperCase();
            
            const cleanPlainLower = cleanPlain.toLowerCase();
            const isRefKeyword = refKeywords.some(kw => cleanPlainLower.startsWith(kw));
            const isYearOrParen = /^\d{4}/.test(cleanPlain) || /^[i|v|x|l|c|d|m]+(?:e|ème|°|er)?\s+(?:siècle|s\b)/i.test(cleanPlain);
            const isRomanRef = /^[ivxlcdm]+(?:\b|\.)/i.test(cleanPlain);
            const isLRef = /^l\.(?:\s|\d|$)/i.test(cleanPlainLower) || /^l\s+\d/i.test(cleanPlainLower) || /^l\s+[ivxlcdm]+/i.test(cleanPlainLower);
            
            const commonPublishers = ['gallimard', 'éditions', 'editions', 'jean-françois', 'librairie', 'presses', 'minuit', 'seuil', 'flammarion', 'vrin', 'albin', 'grasset', 'fayard', 'hachette', 'nathan', 'hatier', 'belin', 'bordas'];
            const isPublisher = commonPublishers.some(pub => cleanPlainLower.startsWith(pub));
            const startsWithItalic = el.innerHTML.trim().startsWith('<em>');
            
            if (isLower || isRefKeyword || isYearOrParen || isRomanRef || isLRef || isPublisher || startsWithItalic) {
                isRefCont = true;
            }
        }
        
        // Attribution des classes
        if (isSpeaker) {
            el.className = '';
            el.classList.add('text-body-dialogue-speaker');
            afterReference = false;
        } else if (isDirection) {
            el.className = '';
            el.classList.add('text-body-dialogue-direction');
            afterReference = false;
        } else if (isArrowRef || isRefCont) {
            el.className = '';
            el.classList.add('text-body-reference');
            
            if (isArrowRef) {
                const removeLeadingArrow = (node) => {
                    if (node.nodeType === Node.TEXT_NODE) {
                        const original = node.textContent;
                        const cleaned = original.replace(/^\s*(?:&rarr;|&#8594;|[→🡪🡺\u2190-\u21FF\u2B00-\u2BFF\u{1F800}-\u{1F8FF}])\s*/u, '');
                        if (cleaned !== original) {
                            node.textContent = cleaned;
                            return true;
                        }
                    }
                    if (node.childNodes) {
                        for (let child of node.childNodes) {
                            if (removeLeadingArrow(child)) return true;
                        }
                    }
                    return false;
                };
                removeLeadingArrow(el);
                el.innerHTML = arrowSVG + el.innerHTML;
            }
            afterReference = true;
        } else if (!inBody) {
            // Tout élément avant le début du corps est un titre
            el.className = '';
            el.classList.add('text-body-title');
            firstTitleFound = true;
            afterReference = false;
        } else {
            // Éléments du corps du texte (paragraphes ou sous-titres)
            const nextEl = el.nextElementSibling;
            const isListIntro = nextEl && (nextEl.tagName === 'OL' || nextEl.tagName === 'UL');
            let isTitleOrSub = isHeading || isStrong || (isTitleLike(plainText, isLast) && !isListIntro);
            
            el.className = '';
            if (isTitleOrSub) {
                el.classList.add('text-body-subheading');
            } else {
                el.classList.add('text-body-paragraph');
            }
            afterReference = false;
        }
    });
    
    return doc.body.innerHTML;
}

/**
 * Rendu principal du corps du texte.
 * 
 * Les fichiers .txt produits par PyMuPDF contiennent DÉJÀ du HTML
 * (<b>, <i>, <sup>, etc.). Cette fonction :
 * 1. Utilise stripHTML() pour classifier chaque bloc (titre / sous-titre /
 *    référence / paragraphe) sans casser le HTML.
 * 2. Conserve le HTML original pour le rendu — pas d'échappement.
 * 3. Applique formatFrenchTypography() HTML-aware sur le contenu rendu.
 */
function parseBodyToHTML(rawText, author) {
    if (!rawText) return '';

    // --- 1. Normalisation des flèches et guillemets avant découpage ---
    let text = rawText
        .replace(/[\uf0e0\uF0E0]/g, '→')
        .replace(/-->|->/g, '→');

    // Séparer les guillemets fermants/ouvrants adjacents
    text = text.replace(/»\s*«/g, '»\n\n«');
    // Forcer un saut avant toute flèche de référence
    text = text.replace(/[ \t]*(→)/g, '\n\n$1');

    // --- 2. Découpage en blocs (séparés par lignes vides) ---
    // On travaille au niveau du bloc (double saut de ligne), pas à la ligne,
    // car les balises HTML peuvent s'étendre sur plusieurs lignes.
    // Normaliser d'abord tous les CRLF en LF pour simplifier le découpage
    text = text.replace(/\r\n/g, '\n');
    const rawBlocks = text.split(/\n{2,}/);
    
    const blocks = [];
    let titleFound = false;

    for (const rawBlock of rawBlocks) {
        // Nettoyer les espaces en début/fin de bloc
        const block = rawBlock.trim();
        if (!block) continue;

        // Texte nu (sans balises) pour les décisions de classification
        const plain = stripHTML(block);
        if (!plain) continue;

        const plainLower = removeAccents(plain.toLowerCase());
        const authorLower = author ? removeAccents(author.toLowerCase()) : '';

        // --- Détection : Référence ---
        // Un bloc est une référence s'il commence par → (dans le texte nu)
        // ou s'il contient le nom de l'auteur + une année entre parenthèses
        const plainTrimmed = plain.trimStart();
        const hasArrow     = plainTrimmed.startsWith('→');
        const hasAuthor    = authorLower && plainLower.includes(authorLower);
        const hasYear      = /\(\d{4}\)/.test(plain) || /\([IVXLCDM]+e\s+siècle\)/i.test(plain);
        const hasTrad      = /\bTrad\.?\b|\bTraduction\b/i.test(plain);

        const isRef = hasArrow ||
                      (titleFound && hasAuthor && hasYear) ||
                      (titleFound && hasTrad && (hasAuthor || hasYear));

        if (isRef) {
            blocks.push({ type: 'reference', html: block });
            continue;
        }

        // --- Détection : Titre (premier bloc non-référence) ---
        if (!titleFound) {
            blocks.push({ type: 'title', html: block });
            titleFound = true;
            continue;
        }

        // --- Détection : Sous-titre ---
        // Critères : texte court (<80 car.), commence par une majuscule,
        // ne se termine pas par ponctuation de fin de phrase,
        // n'est pas un mot-clé de référence
        const isRefKeyword = /^(Trad\.?|Traduction|Tome|Vol\.|Éd\.|Ed\.|p\.|Page|Chapitre|col\.)/i.test(plain);
        const endsWithSentencePunct = /[.!?»]$/.test(plain);
        const startsWithUppercase   = /^[A-ZÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ]/.test(plain);
        const isShort               = plain.length < 80;

        const isSubheading = isShort && !endsWithSentencePunct && startsWithUppercase && !isRefKeyword;

        if (isSubheading) {
            blocks.push({ type: 'subheading', html: block });
            continue;
        }

        // --- Sinon : Paragraphe ---
        blocks.push({ type: 'paragraph', html: block });
    }

    // --- 3. Rendu HTML des blocs ---
    const arrowSVG = `<svg class="ref-arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"
        style="display:inline-block;vertical-align:middle;margin-right:6px;width:1.1em;height:1.1em;color:var(--accent);">
        <line x1="4" y1="12" x2="20" y2="12"></line>
        <polyline points="13 5 20 12 13 19"></polyline></svg>`;

    return blocks.map(block => {
        // Le HTML source est déjà correct — on applique seulement la typographie
        const content = formatFrenchTypography(block.html);

        if (block.type === 'title') {
            return `<div class="text-body-title">${content}</div>`;

        } else if (block.type === 'subheading') {
            return `<h4 class="text-body-subheading">${content}</h4>`;

        } else if (block.type === 'reference') {
            // Supprimer la flèche de début (texte ou balise entourant une flèche)
            let refContent = content
                .replace(/^(<[^>]+>)*\s*→\s*(<\/[^>]+>)*/, '')
                .trim();

            // Séparer les lignes de référence (le script Python les joint avec \n)
            const refLines = refContent.split(/\n/).map(l => l.trim()).filter(Boolean);
            
            const formattedLines = refLines.map((line, idx) => {
                // Ligne de traducteur → style non-gras
                if (/^(Trad\.?|Traduction)/i.test(stripHTML(line))) {
                    return `<span class="ref-translator">${line}</span>`;
                }
                // Première ligne : si elle contient une virgule, italiciser l'œuvre
                if (idx === 0) {
                    // Chercher le pattern Auteur, Œuvre dans le texte nu
                    const plainLine = stripHTML(line);
                    const m = plainLine.match(/^([^,]+),\s*([^,(]+)(.*)$/);
                    if (m && !line.includes('<i>')) {
                        // L'italique n'est pas encore là : on l'ajoute
                        // On reconstruit en cherchant la position de la virgule dans le HTML
                        const commaIdx = findFirstCommaInHTML(line);
                        if (commaIdx > -1) {
                            const authorPart = line.slice(0, commaIdx + 1);
                            const rest       = line.slice(commaIdx + 1).trim();
                            // Deuxième virgule ou parenthèse = fin du titre
                            const secondComma = findFirstCommaOrParenInHTML(rest);
                            if (secondComma > -1) {
                                const work    = rest.slice(0, secondComma);
                                const lastBit = rest.slice(secondComma);
                                return `${authorPart} <i>${work.trim()}</i>${lastBit}`;
                            }
                        }
                    }
                }
                return line;
            });

            return `<div class="text-body-reference">${arrowSVG}${formattedLines.join('<br>')}</div>`;

        } else {
            return `<p class="text-body-paragraph">${content}</p>`;
        }
    }).join('');
}

/**
 * Trouve l'index de la première virgule dans une chaîne HTML
 * en ignorant les virgules à l'intérieur des balises.
 */
function findFirstCommaInHTML(html) {
    let inTag = false;
    for (let i = 0; i < html.length; i++) {
        if (html[i] === '<') { inTag = true; continue; }
        if (html[i] === '>') { inTag = false; continue; }
        if (!inTag && html[i] === ',') return i;
    }
    return -1;
}

/**
 * Trouve l'index de la première virgule OU parenthèse ouvrante dans une
 * chaîne HTML, en ignorant celles à l'intérieur des balises.
 */
function findFirstCommaOrParenInHTML(html) {
    let inTag = false;
    for (let i = 0; i < html.length; i++) {
        if (html[i] === '<') { inTag = true; continue; }
        if (html[i] === '>') { inTag = false; continue; }
        if (!inTag && (html[i] === ',' || html[i] === '(')) return i;
    }
    return -1;
}

function normalizeForSearch(str) {
    if (!str) return '';
    return removeAccents(str.toLowerCase().replace(/’/g, "'"));
}

// DOM elements
const DOM = {
    searchForm: document.getElementById('search-form'),
    searchInput: document.getElementById('search-input'),
    searchClear: document.getElementById('search-clear'),
    resultsCount: document.getElementById('results-count'),
    resultsBar: document.getElementById('results-bar'),
    cardsGrid: document.getElementById('cards-grid'),
    readerView: document.getElementById('reader-view'),
    readerBackBtn: document.getElementById('header-back-btn'),
    readerTextId: document.getElementById('reader-text-id'),
    readerAuthor: document.getElementById('reader-author'),
    readerNotionsBadges: document.getElementById('reader-notions-badges'),
    readerTitle: document.getElementById('reader-title'),
    readerThesis: document.getElementById('reader-thesis'),
    readerSummary: document.getElementById('reader-summary'),
    readerBody: document.getElementById('reader-body'),
    pdfDownloadLink: document.getElementById('pdf-download-link'),
    darkModeToggle: document.getElementById('dark-mode-toggle'),
    analysisCard: document.getElementById('text-analysis-card'),
    navPrev: document.getElementById('nav-prev'),
    navNext: document.getElementById('nav-next'),
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    loadPreferences();
    fetchDatabase();
    setupEventListeners();
});

// ==========================================
// Preferences Management (Style & Dark Mode)
// ==========================================

function loadPreferences() {
    // Force Mentor IA style theme
    document.body.classList.add('theme-mentor');
    
    // Dark mode (user preference only)
    const savedDarkMode = localStorage.getItem('pref-dark-mode');
    if (savedDarkMode !== null) {
        if (savedDarkMode === 'true') {
            document.body.classList.add('dark-mode');
        } else {
            document.body.classList.remove('dark-mode');
        }
    } else {
        // No saved preference: default to light mode
        document.body.classList.remove('dark-mode');
    }
}

// ==========================================
// Data Fetching & Parsing
// ==========================================

async function fetchDatabase() {
    try {
        const response = await fetch('data/database.tsv?t=' + Date.now());
        if (!response.ok) {
            throw new Error(`Erreur de chargement TSV: ${response.status}`);
        }
        const tsvText = await response.text();
        parseTSV(tsvText);
        
        // After loading, render cards
        applyFilters();
        
        // Check hash on load
        handleHashRoute();

        // Focus search input by default on PC when grid is visible
        if (!isMobileDevice() && state.activeTextId === null) {
            DOM.searchInput.focus();
        }
    } catch (error) {
        console.error("Erreur d'initialisation:", error);
        DOM.cardsGrid.innerHTML = `
            <div class="loading-spinner" style="color: #e74c3c;">
                <p>⚠️ Erreur lors du chargement des données. Veuillez lancer le script d'extraction Python en premier.</p>
                <code style="background: rgba(0,0,0,0.05); padding: 8px 12px; border-radius: 4px; font-size: 13px;">${error.message}</code>
            </div>
        `;
    }
}

function cleanTSVField(field) {
    if (!field) return '';
    let str = field.trim();
    if (str.startsWith('"') && str.endsWith('"')) {
        str = str.slice(1, -1);
    }
    return str.replace(/""/g, '"').trim();
}

function parseTSV(tsvText) {
    const lines = tsvText.split(/\r?\n/);
    if (lines.length <= 1) return;
    
    // Line 0 is header: Identifiant \t Nom du fichier \t Analyse du texte \t Notions
    state.texts = [];
    
    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        
        const cols = line.split('\t');
        if (cols.length < 3) continue;
        
        const number = parseInt(cols[0].trim()) || 999;
        const filename = cleanTSVField(cols[1]);
        const analysisText = cleanTSVField(cols[2]);
        const notionsText = cleanTSVField(cols[3]);
        
        // Parse filename metadata
        const parts = filename.split('_');
        
        let authorRaw = parts[0] ? parts[0].trim() : 'INCONNU';
        let rawThemes = parts.slice(1).join('_');
        
        // If the author name starts with 'DE' (e.g. DE_BEAUVOIR, DE_FUNES), merge it
        if (authorRaw.toUpperCase() === 'DE' && parts[1]) {
            authorRaw = 'DE_' + parts[1].trim();
            rawThemes = parts.slice(2).join('_');
        }
        
        // Special case for EN.UNIV.
        if (authorRaw.toUpperCase() === 'EN.UNIV.' && parts[1]) {
            authorRaw = parts[1].trim();
            rawThemes = parts.slice(2).join('_');
        }
        
        // Map raw author name to clean display name
        const AUTHOR_MAPPING = {
            "ALIZAHRA": "Zahra ALI",
            "CHOLLET": "Mona CHOLLET",
            "CLEMENTE": "Élisabeth CLÉMENT",
            "COHEN": "Albert COHEN",
            "CRAWFORD": "CRAWFORD",
            "DAUDET": "Alphonse DAUDET",
            "DAUMAL": "René DAUMAL",
            "DEBEAUVOIR": "DE BEAUVOIR",
            "DEMONTAIGNE": "Tania DE MONTAIGNE",
            "DEFUNES": "Julia DE FUNÈS",
            "DURAS": "Marguerite DURAS",
            "FAYEGAEL": "Gaël FAYE",
            "FILLIOZAT": "Isabelle FILLIOZAT",
            "FRAISSE": "Paul FRAISSE",
            "FREUDSARTRE": "FREUD – SARTRE",
            "FREUDCLAIREPAGES": "Claire PAGÈS",
            "FROIDEVEAUXMETTERIE": "FROIDEVEAUX–METTERIE",
            "GALLUZZOANTHONY": "GALLUZZO",
            "GARCIA": "GARCIA",
            "GIDE": "André GIDE",
            "GODINCHRISTIAN": "Christian GODIN",
            "HOUELLEBECQ": "Michel HOUELLEBECQ",
            "HUGO": "HUGO",
            "HUXLEY": "HUXLEY",
            "JAMESW": "JAMES",
            "JANKELEVITCHV": "JANKÉLÉVITCH",
            "KLEINNAOMI": "Naomi KLEIN",
            "KUNDERA": "Milan KUNDERA",
            "LAROCHEFOUCAULD": "LA ROCHEFOUCAULD",
            "LAFARGUE": "LAFARGUE",
            "LAGASGNERIE": "LAGASNERIE",
            "LAOTSEU": "LAO TSEU",
            "LEOTARD": "Marc-Antoine LÉOTARD",
            "MEADMARGARETH": "Margaret MEAD",
            "MIRBEAU": "Octave MIRBEAU",
            "MORICEJULIETTE": "Juliette MORICE",
            "MOUYPAUL": "Paul MOUY",
            "PIGNOCCHI": "Alessandro PIGNOCCHI",
            "PLINELANCIEN": "PLINE l’Ancien",
            "PREVOST": "Abbé PRÉVOST",
            "RELIGION": "MARX – KANT",
            "SEP": "Stanford Encyc. of Phil.",
            "SEXTUS": "SEXTUS Empiricus",
            "TESTART": "Jacques TESTART",
            "TOURNIER": "Michel TOURNIER",
            "YOURCENAR": "Marguerite YOURCENAR",
            "ZAMIATINE": "Evgueni ZAMIATINE",
            "ZENITER": "Alice ZENITER",
            "EPICURE": "ÉPICURE",
            "TAPPIERRE": "Pierre TAP"
        };
        
        // ID-specific overrides
        const ID_AUTHOR_OVERRIDES = {
            383: "BIBLE – LOCKE – DDHC 1789",
            508: "HÉSIODE – PLATON"
        };
        
        let authorClean;
        if (ID_AUTHOR_OVERRIDES[number]) {
            authorClean = ID_AUTHOR_OVERRIDES[number];
        } else {
            // Normalize the raw author for lookup
            const normKey = authorRaw.toUpperCase()
                .normalize("NFD")
                .replace(/[\u0300-\u036f]/g, "")
                .replace(/[^A-Z0-9]/g, "");
                
            authorClean = AUTHOR_MAPPING[normKey] || authorRaw;
        }
        
        // Replace straight apostrophes with curly ones
        authorClean = authorClean.replace(/'/g, '’');
        
        const author = formatFrenchTypography(authorClean);
        
        // Check version suffixes like _C, _Court, _Complet, _Intro
        let suffix = null;
        if (rawThemes.match(/_C$/i) || rawThemes.match(/_Court$/i)) {
            suffix = 'Version Courte';
            rawThemes = rawThemes.replace(/_C$/i, '').replace(/_Court$/i, '');
        } else if (rawThemes.match(/_Complet$/i)) {
            suffix = 'Version Complète';
            rawThemes = rawThemes.replace(/_Complet$/i, '');
        } else if (rawThemes.match(/_Introduction$/i) || rawThemes.match(/_Intro$/i)) {
            suffix = 'Introduction';
            rawThemes = rawThemes.replace(/_Introduction$/i, '').replace(/_Intro$/i, '');
        }
        
        const themes = formatFrenchTypography(rawThemes.split('&').map(t => t.trim()).join(' / '));
        
        // 2. Parse Analysis column
        // Format: Titre: [T]. Thèse: [Th]. Résumé: [R].
        const titreMatch = analysisText.match(/Titre:\s*(.*?)\s*\.\s*(?:Thèse:|$)/);
        const theseMatch = analysisText.match(/Thèse:\s*(.*?)\s*\.\s*(?:Résumé:|$)/);
        const resumeMatch = analysisText.match(/Résumé:\s*(.*?)\s*\.?\s*$/);
        
        const rawTitle = titreMatch ? titreMatch[1].trim() : themes;
        const cleanTitle = rawTitle
            .replace(/\s*\((?:version\s+)?courte?\)\s*/gi, '')
            .replace(/\s*\((?:version\s+)?complète?\)\s*/gi, '')
            .replace(/\s*\(introduction\)\s*/gi, '')
            .trim();
        const title = formatTitleListSeparators(formatTitleSentenceCase(formatFrenchTypography(cleanTitle)), number);
        const thesis = formatFrenchTypography(theseMatch ? theseMatch[1].trim() : 'Thèse non spécifiée.');
        const summary = formatFrenchTypography(resumeMatch ? resumeMatch[1].trim() : 'Résumé non spécifié.');
        
        // 3. Parse Notions list
        const notions = notionsText.split(',')
            .map(n => formatFrenchTypography(n.trim()))
            .filter(n => n.length > 0);
            
        state.texts.push({
            id: number,
            filename: filename,
            author: author,
            themes: themes,
            suffix: suffix,
            title: title,
            thesis: thesis,
            summary: summary,
            notions: notions,
            rawAnalysis: analysisText
        });
    }
    
    // Sort texts by id numerically
    state.texts.sort((a, b) => a.id - b.id);
}

// ==========================================
// Filtering Logic & Rendering
// ==========================================

function parseSearchQuery(queryStr) {
    const terms = [];
    let temp = queryStr.trim();
    
    // Extract exact phrases in quotes (e.g. "phrase")
    const quoteRegex = /"([^"]+)"|'([^']+)'/g;
    let match;
    while ((match = quoteRegex.exec(temp)) !== null) {
        const phrase = match[1] || match[2];
        if (phrase.trim()) {
            terms.push({ type: 'exact', text: normalizeForSearch(phrase) });
        }
    }
    
    // Remove the exact phrases from the query string to parse the rest
    const remaining = temp.replace(quoteRegex, ' ');
    
    // Split remaining text by spaces and filter out common stop words
    const words = remaining.split(/\s+/);
    const stopWords = ['et', 'ou', 'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'd', 'l', 'a', 'à', 'en', 'par', 'pour', 'dans', 'sur'];
    
    for (let word of words) {
        const cleaned = normalizeForSearch(word).replace(/^['’\-]+|['’\-]+$/g, '');
        if (cleaned && !stopWords.includes(cleaned) && cleaned.length > 1) {
            terms.push({ type: 'word', text: cleaned });
        }
    }
    
    return terms;
}

function applyFilters() {
    const rawQuery = DOM.searchInput.value.trim();
    
    // Reset card preselection when search filter changes
    setPreselectedText(null);
    
    // If the reader is active and a query is entered, close it to start a new search
    if (state.activeTextId !== null && rawQuery !== '') {
        closeReader();
    }
    
    if (!rawQuery) {
        state.filteredTexts = [...state.texts];
        DOM.resultsCount.textContent = `${state.filteredTexts.length} texte${state.filteredTexts.length > 1 ? 's' : ''} trouvé${state.filteredTexts.length > 1 ? 's' : ''}`;
        renderCards();
        DOM.searchClear.classList.remove('visible');
        return;
    }

    DOM.searchClear.classList.add('visible');

    // Check if query is a number
    if (/^\d+$/.test(rawQuery)) {
        state.filteredTexts = state.texts.filter(t => t.id.toString().includes(rawQuery));
        DOM.resultsCount.textContent = `${state.filteredTexts.length} texte${state.filteredTexts.length > 1 ? 's' : ''} trouvé${state.filteredTexts.length > 1 ? 's' : ''}`;
        renderCards();
        
        // If only one text matches, open it directly
        if (state.filteredTexts.length === 1 && state.activeTextId !== state.filteredTexts[0].id) {
            openText(state.filteredTexts[0].id);
        }
        return;
    }

    // Parse query into terms
    const terms = parseSearchQuery(rawQuery);
    if (terms.length === 0) {
        terms.push({ type: 'word', text: normalizeForSearch(rawQuery) });
    }

    // Filter texts: all terms must match (AND search)
    state.filteredTexts = state.texts.filter(t => {
        return terms.every(term => {
            const queryText = term.text;
            
            // Search in notions list
            const matchNotions = t.notions.some(n => normalizeForSearch(n).includes(queryText));
            
            // Search in other textual fields
            const matchAuthor = normalizeForSearch(t.author).includes(queryText);
            const matchThemes = normalizeForSearch(t.themes).includes(queryText);
            const matchTitle = normalizeForSearch(t.title).includes(queryText);
            const matchThesis = normalizeForSearch(t.thesis).includes(queryText);
            const matchSummary = normalizeForSearch(t.summary).includes(queryText);
            
            return matchNotions || matchAuthor || matchThemes || matchTitle || matchThesis || matchSummary;
        });
    });

    // Score and sort results based on official notions matched in the query
    const OFFICIAL_NOTIONS = [
        "L'art", "Le bonheur", "La conscience", "Le devoir", "L'État", 
        "L'inconscient", "La justice", "Le langage", "La liberté", "La nature", 
        "La raison", "La religion", "La science", "La technique", "Le temps", 
        "Le travail", "La vérité"
    ];

    const matchedNotions = OFFICIAL_NOTIONS.filter(notion => {
        const normNotion = normalizeForSearch(notion).replace(/^(l'|d'|la\s+|le\s+|l’)/, '').trim();
        return terms.some(term => {
            return term.type === 'word' && (normNotion.includes(term.text) || term.text.includes(normNotion));
        });
    });

    if (matchedNotions.length > 0) {
        state.filteredTexts.sort((a, b) => {
            // Count how many of the query's matched notions are assigned to this text in the DB
            const scoreA = a.notions.filter(n => {
                const normN = normalizeForSearch(n);
                return matchedNotions.some(mn => normalizeForSearch(mn) === normN);
            }).length;
            const scoreB = b.notions.filter(n => {
                const normN = normalizeForSearch(n);
                return matchedNotions.some(mn => normalizeForSearch(mn) === normN);
            }).length;
            
            if (scoreB !== scoreA) {
                return scoreB - scoreA; // Highest score first
            }
            return a.id - b.id; // Fallback to ID sorting
        });
    }

    // Update count display
    const count = state.filteredTexts.length;
    DOM.resultsCount.textContent = `${count} texte${count > 1 ? 's' : ''} trouvé${count > 1 ? 's' : ''}`;
    
    // Render cards
    renderCards();

    // If only one text matches, open it directly
    if (count === 1 && state.activeTextId !== state.filteredTexts[0].id) {
        openText(state.filteredTexts[0].id);
    }
}

function renderCards() {
    if (state.filteredTexts.length === 0) {
        DOM.cardsGrid.innerHTML = `
            <div class="loading-spinner">
                <p>Aucun texte ne correspond à votre recherche ou filtre.</p>
            </div>
        `;
        return;
    }
    
    DOM.cardsGrid.innerHTML = state.filteredTexts.map(t => {
        const isPreselected = t.id === state.preselectedTextId;
        return `
            <div class="text-card${isPreselected ? ' selected' : ''}" data-id="${t.id}" onclick="openText(${t.id})">
                <div class="card-meta">
                    <span class="card-id-badge">${t.id}</span>
                    <span class="card-author">${t.author}</span>
                </div>
                <h3 class="card-title">
                    ${t.title}
                    ${t.suffix ? `<span class="notion-tag" style="margin-left: 6px; font-weight: 500;">${t.suffix}</span>` : ''}
                </h3>
                <p class="card-thesis-preview">${t.thesis}</p>
                <p class="card-summary-preview">${t.summary}</p>
                <div class="card-notions">
                    ${t.notions.map(n => `<span class="notion-tag">${n}</span>`).join('')}
                </div>
            </div>
        `;
    }).join('');
}

// ==========================================
// Reader & Routing Operations
// ==========================================

function openText(id) {
    // If already active and reader is displayed, do nothing
    if (state.activeTextId === id && document.body.classList.contains('reader-active')) {
        return;
    }
    
    const textData = state.texts.find(t => t.id === id);
    if (!textData) return;
    
    // Set active state
    state.activeTextId = id;
    state.preselectedTextId = id;
    
    // Update hash route quietly to allow sharing links
    window.location.hash = `#${id}`;
    
    // Populate reader metadata
    DOM.readerTextId.textContent = textData.id;
    DOM.readerAuthor.textContent = textData.author;
    DOM.readerTitle.textContent = textData.title;
    DOM.readerThesis.textContent = textData.thesis;
    DOM.readerSummary.textContent = textData.summary;
    
    // Notions badges + Version suffix badge if present
    let badgesHTML = textData.notions.map(n => `<span class="notion-tag">${n}</span>`).join('');
    if (textData.suffix) {
        badgesHTML += `<span class="notion-tag" style="background: var(--accent); color: white; font-weight: 600; margin-left: 6px;">${textData.suffix}</span>`;
    }
    DOM.readerNotionsBadges.innerHTML = badgesHTML;
    
    // Set PDF download link
    DOM.pdfDownloadLink.href = `pdf/${textData.filename}.pdf`;
    
    // Loading state for body text
    DOM.readerBody.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner"></div>
            <p>Chargement du texte intégral...</p>
        </div>
    `;
    DOM.readerBody.style.fontSize = `${state.fontSize}px`;
    
    // Display reader, hide card list
    document.body.classList.add('reader-active');
    DOM.cardsGrid.style.display = 'none';
    DOM.resultsBar.style.display = 'none';
    DOM.readerView.style.display = 'block';
    
    // Update navigation buttons
    updateNavigationButtons();
    
    // Scroll to the very top of the page
    window.scrollTo(0, 0);
    
    // Fetch HTML text content
    fetch(`data/texts/${textData.filename}.html`)
        .then(res => {
            if (!res.ok) throw new Error("Fichier HTML introuvable");
            return res.text();
        })
        .then(html => {
            DOM.readerBody.innerHTML = processLoadedHTML(html, textData.author);
            setupFootnoteListeners();
        })
        .catch(err => {
            console.error(err);
            DOM.readerBody.innerHTML = `
                <div class="pdf-only-notice">
                    <a href="pdf/${textData.filename}.pdf" target="_blank" class="notice-link" title="Ouvrir le PDF">
                        <span class="notice-icon">📂</span>
                    </a>
                    <p><a href="pdf/${textData.filename}.pdf" target="_blank" class="notice-text-link">Ce texte est à consulter directement sur le document PDF d'origine.</a></p>
                </div>
            `;
        });
}

function setupFootnoteListeners() {
    const refLinks = DOM.readerBody.querySelectorAll('a[id^="footnote-ref-"]');
    refLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href').replace('#', '');
            const targetEl = DOM.readerBody.querySelector(`[id="${targetId}"]`);
            if (targetEl) {
                targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                targetEl.classList.add('highlight-note');
                setTimeout(() => {
                    targetEl.classList.remove('highlight-note');
                }, 2000);
            }
        });
    });

    const backLinks = DOM.readerBody.querySelectorAll('.footnotes a[href^="#footnote-ref-"]');
    backLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href').replace('#', '');
            const targetEl = DOM.readerBody.querySelector(`[id="${targetId}"]`);
            if (targetEl) {
                targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                targetEl.classList.add('highlight-ref');
                setTimeout(() => {
                    targetEl.classList.remove('highlight-ref');
                }, 2000);
            }
        });
    });
}

function updateNavigationButtons() {
    if (!DOM.navPrev || !DOM.navNext) return;
    
    const currentIndex = state.filteredTexts.findIndex(t => t.id === state.activeTextId);
    if (currentIndex === -1) {
        DOM.navPrev.disabled = true;
        DOM.navNext.disabled = true;
        return;
    }
    
    DOM.navPrev.disabled = (currentIndex === 0);
    DOM.navNext.disabled = (currentIndex === state.filteredTexts.length - 1);
}

function navigatePrev() {
    const currentIndex = state.filteredTexts.findIndex(t => t.id === state.activeTextId);
    if (currentIndex > 0) {
        openText(state.filteredTexts[currentIndex - 1].id);
    }
}

function navigateNext() {
    const currentIndex = state.filteredTexts.findIndex(t => t.id === state.activeTextId);
    if (currentIndex !== -1 && currentIndex < state.filteredTexts.length - 1) {
        openText(state.filteredTexts[currentIndex + 1].id);
    }
}

function closeReader() {
    const closedId = state.activeTextId;
    state.activeTextId = null;
    window.location.hash = '';
    
    // Toggle view visibility
    document.body.classList.remove('reader-active');
    DOM.readerView.style.display = 'none';
    DOM.cardsGrid.style.display = 'grid';
    DOM.resultsBar.style.display = 'flex';
    
    // Auto-preselect closed text card on PC
    if (closedId !== null && !isMobileDevice()) {
        setPreselectedText(closedId);
    }
}

function handleHashRoute() {
    const hash = window.location.hash.substring(1);
    if (!hash) {
        if (state.activeTextId) {
            closeReader();
        }
        return;
    }
    
    // Try matching numeric text ID
    const matchId = parseInt(hash.replace("text-", ""));
    if (!isNaN(matchId)) {
        openText(matchId);
    }
}

// ==========================================
// Event Listeners Configuration
// ==========================================

function setupEventListeners() {
    // Search form submission (direct access by number or unique search term)
    DOM.searchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const query = DOM.searchInput.value.trim();
        const isMobile = isMobileDevice();
        
        // Remove focus from input to hide keyboard on mobile / exit search on PC
        DOM.searchInput.blur();
        
        if (isMobile) {
            if (/^\d+$/.test(query)) {
                const num = parseInt(query, 10);
                const hasText = state.texts.some(t => t.id === num);
                if (hasText) {
                    openText(num);
                    DOM.searchInput.value = '';
                    applyFilters(); // Reset search input state
                } else {
                    alert(`Le texte N° ${num} n'existe pas dans la base.`);
                }
            } else {
                // If not a number, but there is exactly 1 match
                if (state.filteredTexts.length === 1) {
                    openText(state.filteredTexts[0].id);
                    DOM.searchInput.value = '';
                    applyFilters(); // Reset search input state
                }
            }
        } else {
            // On PC: preselect the first text card without opening it yet
            if (state.filteredTexts.length > 0) {
                setPreselectedText(state.filteredTexts[0].id);
            }
        }
    });
    
    // Text search inputs
    DOM.searchInput.addEventListener('input', applyFilters);
    
    // Clear search
    DOM.searchClear.addEventListener('click', () => {
        DOM.searchInput.value = '';
        if (state.activeTextId !== null) {
            closeReader();
        }
        applyFilters();
    });
    

    
    // Reader Back Button
    DOM.readerBackBtn.addEventListener('click', closeReader);
    
    // Text navigation
    DOM.navPrev.addEventListener('click', navigatePrev);
    DOM.navNext.addEventListener('click', navigateNext);

    // Keyboard navigation on PC (ArrowLeft/ArrowRight/Escape/Enter/ArrowUp/ArrowDown)
    document.addEventListener('keydown', (e) => {
        const isMobile = isMobileDevice();
        if (isMobile) return;
        
        // --- Scenario A: Reader is active ---
        if (state.activeTextId !== null) {
            if (e.key === 'Escape' || e.key === 'Esc') {
                closeReader();
                return;
            }
            
            // Ignore if user is currently typing in an input element
            if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) {
                return;
            }
            
            if (e.key === 'ArrowLeft') {
                navigatePrev();
            } else if (e.key === 'ArrowRight') {
                navigateNext();
            }
            return;
        }
        
        // --- Scenario B: Reader is NOT active (Viewing grid) ---
        if (e.key === 'Escape' || e.key === 'Esc') {
            e.preventDefault();
            DOM.searchInput.value = '';
            applyFilters();
            DOM.searchInput.focus();
            return;
        }

        // Ignore if user is currently typing in an input element
        if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) {
            return;
        }
        
        if (state.preselectedTextId !== null) {
            const currentIndex = state.filteredTexts.findIndex(t => t.id === state.preselectedTextId);
            
            if (e.key === 'Enter') {
                e.preventDefault();
                openText(state.preselectedTextId);
            } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                e.preventDefault();
                if (currentIndex !== -1 && currentIndex < state.filteredTexts.length - 1) {
                    setPreselectedText(state.filteredTexts[currentIndex + 1].id);
                }
            } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                e.preventDefault();
                if (currentIndex !== -1 && currentIndex > 0) {
                    setPreselectedText(state.filteredTexts[currentIndex - 1].id);
                }
            }
        } else {
            // If no card is preselected but the user presses an arrow key on the document,
            // preselect the first card.
            if (state.filteredTexts.length > 0 && (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === 'ArrowLeft' || e.key === 'ArrowUp')) {
                e.preventDefault();
                setPreselectedText(state.filteredTexts[0].id);
            }
        }
    });

    // Swipe gauche/droite (1 doigt) → texte suivant/précédent
    let touchStartX = 0;
    let touchStartY = 0;

    document.addEventListener('touchstart', (e) => {
        if (state.activeTextId === null) return;
        if (e.touches.length > 1) return; // ignorer le multi-touch
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
        if (state.activeTextId === null) return;
        if (e.changedTouches.length > 1) return;
        const deltaX = e.changedTouches[0].clientX - touchStartX;
        const deltaY = e.changedTouches[0].clientY - touchStartY;
        const threshold = 60;
        if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > threshold) {
            if (deltaX > 0) {
                navigatePrev();
            } else {
                navigateNext();
            }
        }
    }, { passive: true });
    
    // Font sizing
    document.getElementById('font-dec').addEventListener('click', () => {
        if (state.fontSize > 14) {
            state.fontSize -= 2;
            DOM.readerBody.style.fontSize = `${state.fontSize}px`;
        }
    });
    document.getElementById('font-inc').addEventListener('click', () => {
        if (state.fontSize < 28) {
            state.fontSize += 2;
            DOM.readerBody.style.fontSize = `${state.fontSize}px`;
        }
    });
    

    
    // Dark mode toggle
    DOM.darkModeToggle.addEventListener('click', () => {
        const isDark = document.body.classList.toggle('dark-mode');
        localStorage.setItem('pref-dark-mode', isDark);
    });
    
    // Hash route listening
    window.addEventListener('hashchange', handleHashRoute);
}
