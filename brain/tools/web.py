import asyncio
import re
import urllib.parse
import httpx
import os
from . import tool

SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

STOP_WORDS = frozenset(
    "le la les de des du un une est et a au sur dans pour par avec ce se que qui "
    "quoi dont où es tu il elle on nous vous ils elles son sa ses mon ma mes "
    "ton ta ses notre nos votre vos leur leurs je tu il elle on nous vous ils "
    "elles me te se lui y en ne pas plus tres bien mal aussi mais donc or ni car "
    "si comme quand lorsque puisque parce que cependant toute tous toutes "
    "plusieurs certaines chaque aucun aucune quelques soit soit".split())

# Sources fiables (bonus de score)
TRUSTED_DOMAINS = {
    "wikipedia.org", "fr.wikipedia.org", "en.wikipedia.org",
    "github.com", "gitlab.com", "stackoverflow.com",
    "docs.python.org", "developer.mozilla.org", "mdn.fr",
    "arxiv.org", "scholar.google.com", "pubmed.ncbi.nlm.nih.gov",
    "inria.fr", "cnrs.fr", "insa-lyon.fr",
    "stackoverflow.com", "stackexchange.com",
    "youtube.com", "youtu.be",
    "docs.oracle.com", "learn.microsoft.com",
    "linuxfr.org", "github.io", "readthedocs.io",
    "openverse.org", "freesound.org",
}

# Sources spam / peu fiables (malus de score)
SPAM_DOMAINS = {
    "pinterest.com", "pin.it",
    "facebook.com", "fb.com", "m.facebook.com",
    "instagram.com", "tiktok.com",
    "twitter.com", "x.com",
    "reddit.com", "old.reddit.com",
    "quora.com",
    "medium.com",  # paywall souvent
    "substack.com",
    "buzzfeed.com", "list25.com", "boredpanda.com",
    "wix.com", "weebly.com", "wordpress.com",
    "amazon.com", "ebay.com", "aliexpress.com",
    "ad.doubleclick.net", "ads.google.com",
}

# Patterns de bruit à filtrer dans les snippets
NOISE_PATTERNS = re.compile(
    r'(?:cookie|accepter|refuser|mot de passe|password|inscription|'
    r's\'inscrire|abonnez-vous|menu|navigation|newsletter|recevoir|'
    r'partager|twitter|facebook|linkedin|instagram|tiktok|'
    r'charger plus|voir plus|lire la suite|subscribe|sign up|'
    r'privacy policy|terms of service|copyright|tous droits réservés|'
    r'annonce|publicité|sponsorisé|ad\b|advertisement)',
    re.IGNORECASE
)


def _clean_html(html: str) -> str:
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
    text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
    text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL)
    text = re.sub(r'<form[^>]*>.*?</form>', '', text, flags=re.DOTALL)
    text = re.sub(r'<aside[^>]*>.*?</aside>', '', text, flags=re.DOTALL)
    text = re.sub(r'<svg[^>]*>.*?</svg>', '', text, flags=re.DOTALL)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'\{\{[^}]*\}\}', ' ', text)
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
    text = re.sub(r'\[\[[^\]]*\]\]', ' ', text)
    texts = []
    for tag in ('h1', 'h2', 'h3', 'h4', 'p', 'li', 'td', 'th', 'blockquote', 'figcaption'):
        texts.extend(re.findall(f'<{tag}[^>]*>(.*?)</{tag}>', text, flags=re.DOTALL))
    if not texts:
        texts = [text]
    combined = ' '.join(texts)
    combined = re.sub(r'<[^>]+>', ' ', combined)
    combined = re.sub(r'&[a-z]+;', ' ', combined)
    combined = re.sub(r'&#\d+;', ' ', combined)
    combined = re.sub(r'\s+', ' ', combined).strip()
    return combined


def _extract_sentences(text: str) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    clean = []
    for s in sentences:
        s = s.strip()
        if len(s) < 25:
            continue
        if NOISE_PATTERNS.search(s):
            continue
        clean.append(s)
    return clean


def _query_keywords(query: str) -> set[str]:
    words = set(re.findall(r'\w+', query.lower()))
    return words - STOP_WORDS


def _domain_score(url: str) -> float:
    """Score de crédibilité d'un domaine (-1.0 à +1.0)."""
    domain_match = re.match(r'https?://([^/]+)', url)
    if not domain_match:
        return 0
    domain = domain_match.group(1).replace('www.', '')

    if domain in TRUSTED_DOMAINS:
        return 1.0
    if domain in SPAM_DOMAINS:
        return -1.0

    # Bonus pour les domaines gouvernementaux/edu/org
    if domain.endswith('.gov') or domain.endswith('.gouv.fr'):
        return 0.8
    if domain.endswith('.edu') or domain.endswith('.ac.fr'):
        return 0.7
    if domain.endswith('.org'):
        return 0.3
    if domain.endswith('.fr') or domain.endswith('.com'):
        return 0.1
    return 0


def _relevance_score(text: str, keywords: set[str]) -> float:
    if not keywords:
        return 0
    words = set(re.findall(r'\w+', text.lower()))
    overlap = len(words & keywords)
    return overlap / max(len(keywords), 1)


def _refine_query(query: str, qtype: str) -> str:
    """Enrichit la requête pour de meilleurs résultats."""
    q = query.strip()

    # Pour les vidéos, ajouter des mots-clés qualitatifs
    if qtype == "video":
        if "tutoriel" not in q.lower() and "tutorial" not in q.lower():
            pass  # ne pas forcer

    # Pour les fichiers, ajouter des extensions
    if qtype == "file":
        if not any(ext in q.lower() for ext in (".pdf", ".zip", ".exe", ".apk", ".doc", ".xlsx")):
            q += " filetype:pdf"

    # Pour les images, ajouter qualité
    if qtype == "image":
        if "hd" not in q.lower() and "haut" not in q.lower():
            pass  # garder la requête telle quelle

    return q


def _detect_question_type(query: str) -> str:
    q = query.lower().strip()
    if any(w in q for w in ("vidéo", "video", "youtube", "regarder", "voir la vidéo")):
        return "video"
    if any(w in q for w in ("image", "photo", "图片", "screensaver", "fond d'écran", "wallpaper")):
        return "image"
    if any(w in q for w in ("audio", "musique", "music", "chanson", "mp3", "écouter")):
        return "audio"
    if any(w in q for w in ("fichier", "file", "télécharger", "download", "pdf", "zip", ".exe")):
        return "file"
    if q.startswith(("qui", "quel", "quelle", "quels", "quelles", "qu'est-ce que", "qu'est-ce qu'")):
        return "factual"
    if q.startswith(("comment", "de quelle façon", "de quelle manière")):
        return "howto"
    if q.startswith(("pourquoi")):
        return "why"
    if any(w in q for w in ("combien", "quel âge", "quelle taille", "quel poids", "prix", "coût", "tarif")):
        return "measure"
    if q.startswith(("où")):
        return "where"
    if q.startswith(("quand")):
        return "when"
    if any(w in q for w in ("liste", "quels sont", "quelles sont", "types de", "catégories")):
        return "list"
    return "general"


async def _fetch_page(url: str, client: httpx.AsyncClient) -> tuple[str, str, float]:
    """Récupère une page et retourne (domain, text, domain_score)."""
    domain_match = re.match(r'https?://([^/]+)', url)
    domain = domain_match.group(1).replace('www.', '') if domain_match else url
    dscore = _domain_score(url)
    try:
        resp = await client.get(url, headers=SEARCH_HEADERS, timeout=12, follow_redirects=True)
        resp.raise_for_status()
        raw = _clean_html(resp.text)
        sentences = _extract_sentences(raw)
        if not sentences:
            return domain, "", dscore
        return domain, '. '.join(sentences[:15]), dscore
    except Exception:
        return domain, "", dscore


async def _brave_search(query: str, client: httpx.AsyncClient) -> list[str]:
    """Recherche via Brave Search API (si clé disponible)."""
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        return []
    try:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": 8},
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("web", {}).get("results", [])
        return [r["url"] for r in results if r.get("url")]
    except Exception:
        return []


async def _ddg_search(query: str, client: httpx.AsyncClient) -> list[str]:
    """Recherche via DuckDuckGo HTML scraping."""
    encoded = urllib.parse.quote_plus(query)
    try:
        resp = await client.get(
            f"https://html.duckduckgo.com/html/?q={encoded}",
            headers=SEARCH_HEADERS, timeout=15, follow_redirects=True
        )
        resp.raise_for_status()
        html = resp.text
    except Exception:
        return []

    urls = []
    seen = set()
    for m in re.finditer(r'uddg=([^"&]+)', html):
        u = urllib.parse.unquote(m.group(1))
        if not u.startswith("http"):
            continue
        domain_match = re.match(r'https?://([^/]+)', u)
        domain = domain_match.group(1).replace('www.', '') if domain_match else u
        if domain in seen:
            continue
        seen.add(domain)
        urls.append(u)
        if len(urls) >= 8:
            break

    if not urls:
        for m in re.finditer(r'<a[^>]*href="(https?://[^"]+)"', html):
            u = m.group(1)
            if any(s in u for s in ("duckduckgo.com", "yahoo.com", "bing.com", "google.")):
                continue
            if len(urls) >= 8:
                break
            urls.append(u)

    return urls


@tool("recherche_web", "Recherche web approfondie. Paramètre : requete (question ou sujet).")
async def recherche_web(requete: str) -> str:
    """Recherche web avec scoring avancé et filtrage des sources."""
    if not requete or not requete.strip():
        return "Il me faut une requête pour chercher."

    query = requete.strip()
    qtype = _detect_question_type(query)
    keywords = _query_keywords(query)

    # Enrichir la requête
    refined = _refine_query(query, qtype)

    async with httpx.AsyncClient(verify=False) as client:
        # Brave Search en priorité, sinon DuckDuckGo
        urls = await _brave_search(refined, client)
        if not urls:
            urls = await _ddg_search(refined, client)

        if not urls:
            # Deuxième tentative avec requête simplifiée
            simple = ' '.join(query.split()[:5])
            urls = await _ddg_search(simple, client)

        if not urls:
            return f"Je n'ai pas trouvé de résultats pour « {query} »."

        # Fetch et scorer les pages
        results = await asyncio.gather(
            *[_fetch_page(u, client) for u in urls[:6]],
            return_exceptions=True
        )

    # Traiter les résultats
    scored_results = []
    for r in results:
        if isinstance(r, Exception) or not r[1]:
            continue
        domain, text, dscore = r
        sents = [s.strip() for s in text.split('. ') if len(s.strip()) > 25]
        for s in sents:
            rscore = _relevance_score(s, keywords)
            # Score final = pertinence * 0.6 + crédibilité domaine * 0.4
            final_score = rscore * 0.6 + (dscore + 1) / 2 * 0.4
            scored_results.append((final_score, s, domain))

    scored_results.sort(key=lambda x: -x[0])

    # Dédupliquer
    seen = set()
    final = []
    for score, sent, domain in scored_results:
        key = re.sub(r'\W+', '', sent[:80].lower())
        if key in seen:
            continue
        seen.add(key)
        final.append((score, sent, domain))

    # Sélectionner les meilleurs
    top = [s for s in final if s[0] > 0.1]
    if not top:
        top = final[:6]
    else:
        top = top[:8]

    if not top:
        return f"Je n'ai pas trouvé de contenu pertinent pour « {query} »."

    # Formater selon le type de question
    if qtype == "factual":
        answer = [f"{top[0][1]}."]
        for _, sent, _ in top[1:4]:
            if sent not in answer[0]:
                answer.append(sent + ".")
        body = ' '.join(answer)
    elif qtype == "list":
        items = [f"  - {s.split('.')[0]}" for _, s, _ in top[:8]]
        body = "Voici ce que j'ai trouvé :\n" + '\n'.join(items)
    elif qtype == "measure":
        body = ' '.join(f"{s}." for _, s, _ in top[:5])
    else:
        body = ' '.join(s for _, s, _ in top[:6])

    # Nettoyer
    body = re.sub(r'\s*\.\s*\.', '.', body)
    body = re.sub(r'\s{2,}', ' ', body)

    if len(body) > 2000:
        body = body[:2000] + "..."

    if len(body) < 40:
        body = ' '.join(s[1] for s in final[:4])

    # Sources avec indicateur de fiabilité
    domains_used = list(dict.fromkeys(d for _, _, d in top))  # preserve order, dedup
    src_parts = []
    for d in domains_used[:4]:
        score = _domain_score(f"https://{d}")
        if score >= 0.7:
            src_parts.append(f"✓ {d}")
        elif score >= 0:
            src_parts.append(d)
        else:
            src_parts.append(f"⚠ {d}")
    src_line = " — Sources: " + ', '.join(src_parts)

    return body + src_line


@tool("recherche_image", "Cherche des images sur le web. Paramètre : requete.")
async def recherche_image(requete: str) -> str:
    """Cherche des images avec filtres qualité."""
    if not requete or not requete.strip():
        return "Que veux-tu que je cherche comme image ?"
    query = requete.strip()
    encoded = urllib.parse.quote_plus(query)

    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        # DuckDuckGo instant answer API
        try:
            resp = await client.get(
                f"https://api.duckduckgo.com/?q={encoded}&format=json",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            
            # Image principale
            image_url = data.get("Image", "")
            if image_url and image_url.startswith("http"):
                result = f"📸 Images pour « {query} » :\n[IMG]{image_url}[/IMG]"
                
                # Topics liés avec images
                topics = data.get("RelatedTopics", [])
                img_urls = []
                for topic in topics:
                    if isinstance(topic, dict):
                        img = topic.get("Image", "")
                        if img and img.startswith("http") and img not in img_urls:
                            img_urls.append(img)
                        # Sous-topics
                        for sub in topic.get("Topics", []):
                            if isinstance(sub, dict):
                                sub_img = sub.get("Image", "")
                                if sub_img and sub_img.startswith("http") and sub_img not in img_urls:
                                    img_urls.append(sub_img)
                
                if img_urls:
                    for u in img_urls[:5]:
                        result += f"\n[IMG]{u}[/IMG]"
                
                return result.strip()
        except Exception:
            pass

        # Fallback: Openverse (avec timeout plus long)
        try:
            resp = await client.get(
                f"https://api.openverse.org/v1/images/?q={encoded}&page_size=8",
                headers={"User-Agent": "AlexAssistant/1.0"},
                timeout=20
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                valid = []
                for r in results:
                    url = r.get("url")
                    width = r.get("width", 0)
                    height = r.get("height", 0)
                    if width and height and (width < 200 or height < 200):
                        continue
                    if url:
                        try:
                            hr = await client.head(url, timeout=5, follow_redirects=True)
                            if hr.status_code == 200 and "image" in hr.headers.get("content-type", ""):
                                valid.append(url)
                                if len(valid) >= 4:
                                    break
                        except Exception:
                            continue
                if valid:
                    result = f"📸 Images pour « {query} » :\n"
                    for u in valid:
                        result += f"[IMG]{u}[/IMG]\n"
                    return result.strip()
        except Exception:
            pass

        # Fallback: recherche web classique
        try:
            text_result = await recherche_web(f"{query} image")
            return text_result
        except Exception:
            pass

    return f"Je n'ai pas trouvé d'images pour « {query} »."


@tool("recherche_video", "Cherche des vidéos. Paramètre : requete.")
async def recherche_video(requete: str) -> str:
    """Cherche des vidéos avec filtres qualité."""
    if not requete or not requete.strip():
        return "Quelle vidéo veux-tu que je cherche ?"
    query = requete.strip()
    encoded = urllib.parse.quote_plus(query)

    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        # Recherche YouTube via DuckDuckGo
        try:
            resp = await client.get(
                f"https://html.duckduckgo.com/html/?q={encoded}+site:youtube.com",
                headers=SEARCH_HEADERS, follow_redirects=True
            )
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            return f"Erreur de recherche vidéo : {e}"

        results = []
        for m in re.finditer(r'uddg=([^"&]+)', html):
            u = urllib.parse.unquote(m.group(1))
            if not u.startswith("http"):
                continue
            if "youtube.com/watch" in u or "youtu.be/" in u:
                if u not in results:
                    results.append(u)
            if len(results) >= 5:
                break

        # Fallback: recherche directe
        if not results:
            for m in re.finditer(r'<a[^>]*href="(https?://(?:www\.)?youtube\.com/watch\?v=[^"]+)"', html, re.IGNORECASE):
                u = m.group(1)
                if u not in results:
                    results.append(u)
                if len(results) >= 5:
                    break

        # Aussi chercher sur Dailymotion
        if not results:
            try:
                resp2 = await client.get(
                    f"https://html.duckduckgo.com/html/?q={encoded}+site:dailymotion.com",
                    headers=SEARCH_HEADERS, follow_redirects=True
                )
                resp2.raise_for_status()
                html2 = resp2.text
                for m in re.finditer(r'uddg=([^"&]+)', html2):
                    u = urllib.parse.unquote(m.group(1))
                    if "dailymotion.com/video" in u:
                        if u not in results:
                            results.append(u)
                        if len(results) >= 5:
                            break
            except Exception:
                pass

        if not results:
            return f"Je n'ai pas trouvé de vidéos pour « {query} »."

        result = f"🎬 Vidéos pour « {query} » :\n"
        for u in results:
            result += u + "\n"
        return result.strip()


@tool("recherche_audio", "Cherche de la musique/audio. Paramètre : requete.")
async def recherche_audio(requete: str) -> str:
    """Cherche de l'audio avec filtres qualité."""
    if not requete or not requete.strip():
        return "Que veux-tu que je cherche comme audio ?"
    query = requete.strip()
    encoded = urllib.parse.quote_plus(query)

    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        # Openverse audio
        try:
            resp = await client.get(
                f"https://api.openverse.org/v1/audio/?q={encoded}&page_size=8",
                headers={"User-Agent": "AlexAssistant/1.0"},
                timeout=10
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                urls = []
                for r in results:
                    url = r.get("audio_url") or r.get("url", "")
                    if url:
                        urls.append(url)
                    if len(urls) >= 6:
                        break
                if urls:
                    result = f"🎵 Audio pour « {query} » :\n"
                    for u in urls:
                        result += u + "\n"
                    return result.strip()
        except Exception:
            pass

        # Fallback: FreeSound via DuckDuckGo
        try:
            resp2 = await client.get(
                f"https://html.duckduckgo.com/html/?q={encoded}+site:freesound.org",
                headers=SEARCH_HEADERS, follow_redirects=True
            )
            resp2.raise_for_status()
            html2 = resp2.text
            audio_urls = []
            for m in re.finditer(r'uddg=([^"&]+)', html2):
                u = urllib.parse.unquote(m.group(1))
                if "freesound.org" in u:
                    if u not in audio_urls:
                        audio_urls.append(u)
                    if len(audio_urls) >= 4:
                        break
            if audio_urls:
                result = f"🎵 Audio pour « {query} » :\n"
                for u in audio_urls:
                    result += u + "\n"
                return result.strip()
        except Exception:
            pass

    return f"Je n'ai pas trouvé d'audio pour « {query} »."


@tool("recherche_fichier", "Cherche des fichiers téléchargeables (PDF, ZIP, etc.). Paramètre : requete.")
async def recherche_fichier(requete: str) -> str:
    """Cherche des fichiers téléchargeables sur le web."""
    if not requete or not requete.strip():
        return "Quel fichier veux-tu que je cherche ?"
    query = requete.strip()

    # Détecter le type de fichier demandé
    ext = ""
    if any(w in query.lower() for w in ("pdf", "document")):
        ext = "pdf"
    elif any(w in query.lower() for w in ("zip", "archive")):
        ext = "zip"
    elif any(w in query.lower() for w in ("exe", "installateur", "installation")):
        ext = "exe"
    elif any(w in query.lower() for w in ("apk", "android")):
        ext = "apk"
    elif any(w in query.lower() for w in ("doc", "word")):
        ext = "docx"
    elif any(w in query.lower() for w in ("excel", "tableur", "xlsx")):
        ext = "xlsx"

    # Construire la requête de recherche
    search_query = query
    if ext:
        search_query += f" filetype:{ext}"

    urls = []
    async with httpx.AsyncClient(verify=False) as client:
        urls = await _ddg_search(search_query, client)
        if not urls and ext:
            # Réessayer sans l'extension
            urls = await _ddg_search(query, client)

    if not urls:
        return f"Je n'ai pas trouvé de fichiers pour « {query} »."

    # Filtrer pour les URLs qui ressemblent à des fichiers
    file_urls = []
    for u in urls:
        lower = u.lower()
        is_file = any(lower.endswith(f".{e}") for e in (
            "pdf", "zip", "rar", "exe", "msi", "apk", "deb", "rpm",
            "doc", "docx", "xls", "xlsx", "ppt", "pptx",
            "mp3", "mp4", "avi", "mkv", "wav", "flac",
            "jpg", "jpeg", "png", "gif", "webp",
            "iso", "img", "dmg",
        ))
        is_download = any(w in lower for w in ("download", "télécharger", "getfile", "files/"))
        if is_file or is_download:
            file_urls.append(u)

    if not file_urls:
        # Si pas de fichiers trouvés, retourner les résultats normaux
        result = f"📄 Résultats pour « {query} » :\n"
        for u in urls[:5]:
            result += f"{u}\n"
        return result.strip()

    result = f"📄 Fichiers pour « {query} » :\n"
    for u in file_urls[:5]:
        result += f"{u}\n"
    return result.strip()
