"""Outil de creation de sites web pour Alex."""
import os
import subprocess
from pathlib import Path
from . import tool


@tool("creer_site_web",
      "Cree un site web complet (HTML, CSS, JS). Parametres : nom (nom du projet), type (portfolio, blog, landing, app).")
def creer_site_web(nom: str = "mon-site", type: str = "portfolio") -> str:
    """Cree un site web complet."""
    if not nom or not nom.strip():
        return "Il me faut un nom pour le projet."
    
    nom = nom.strip().replace(" ", "-").lower()
    site_dir = Path.home() / nom
    
    try:
        site_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return f"Erreur creation dossier : {e}"
    
    templates = {
        "portfolio": _portfolio_template(),
        "blog": _blog_template(),
        "landing": _landing_template(),
        "app": _app_template(),
    }
    
    template = templates.get(type.lower(), templates["portfolio"])
    
    # Creer les fichiers
    for filename, content in template.items():
        filepath = site_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
    
    return f"Site web '{nom}' cree dans {site_dir}/ avec le theme {type}."


@tool("lancer_serveur_dev",
      "Lance un serveur de developpement local. Parametre : dossier (chemin du site).")
def lancer_serveur_dev(dossier: str = ".") -> str:
    """Lance un serveur de developpement local."""
    site_dir = Path(dossier).expanduser().resolve()
    if not site_dir.exists():
        return f"Dossier introuvable : {dossier}"
    
    # Verifier si c'est un projet Node.js
    if (site_dir / "package.json").exists():
        try:
            result = subprocess.run(
                ["npm", "run", "dev"],
                cwd=str(site_dir),
                capture_output=True,
                text=True,
                timeout=5
            )
            return f"Serveur de dev lance dans {dossier} (npm run dev)"
        except subprocess.TimeoutExpired:
            return f"Serveur de dev lance dans {dossier} (en arriere-plan)"
        except Exception as e:
            return f"Erreur lancement serveur : {e}"
    
    # Sinon, utiliser python http.server
    try:
        subprocess.Popen(
            ["python3", "-m", "http.server", "8000"],
            cwd=str(site_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return f"Serveur Python lance sur http://localhost:8000 dans {dossier}"
    except Exception as e:
        return f"Erreur lancement serveur : {e}"


@tool("installer_dependances_web",
      "Installe les dependances d'un projet web. Parametre : dossier (chemin du projet).")
def installer_dependances_web(dossier: str = ".") -> str:
    """Installe les dependances d'un projet web."""
    site_dir = Path(dossier).expanduser().resolve()
    if not site_dir.exists():
        return f"Dossier introuvable : {dossier}"
    
    # Verifier le type de projet
    if (site_dir / "package.json").exists():
        try:
            result = subprocess.run(
                ["npm", "install"],
                cwd=str(site_dir),
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                return f"Dependances npm installees dans {dossier}"
            return f"Erreur installation npm : {result.stderr[:200]}"
        except Exception as e:
            return f"Erreur installation npm : {e}"
    
    if (site_dir / "requirements.txt").exists():
        try:
            result = subprocess.run(
                ["pip", "install", "-r", "requirements.txt"],
                cwd=str(site_dir),
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                return f"Dependances Python installees dans {dossier}"
            return f"Erreur installation pip : {result.stderr[:200]}"
        except Exception as e:
            return f"Erreur installation pip : {e}"
    
    return "Aucun fichier package.json ou requirements.txt trouve."


@tool("preview_site",
      "Ouvre le site web dans le navigateur. Parametre : dossier (chemin du site).")
def preview_site(dossier: str = ".") -> str:
    """Ouvre le site web dans le navigateur."""
    site_dir = Path(dossier).expanduser().resolve()
    if not site_dir.exists():
        return f"Dossier introuvable : {dossier}"
    
    index = site_dir / "index.html"
    if not index.exists():
        return f"Aucun fichier index.html trouve dans {dossier}"
    
    try:
        import webbrowser
        webbrowser.open(f"file://{index}")
        return f"Site ouvert dans le navigateur : {dossier}"
    except Exception as e:
        return f"Erreur ouverture navigateur : {e}"


def _portfolio_template():
    return {
        "index.html": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mon Portfolio</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header><nav>
        <h1>Portfolio</h1>
        <ul>
            <li><a href="#accueil">Accueil</a></li>
            <li><a href="#projets">Projets</a></li>
            <li><a href="#contact">Contact</a></li>
        </ul>
    </nav></header>
    <main>
        <section id="accueil" class="hero">
            <h2>Bienvenue !</h2>
            <p>Developpeur web passionne</p>
        </section>
        <section id="projets"><h2>Mes Projets</h2>
            <div class="grid">
                <div class="card"><h3>Projet 1</h3><p>Description</p></div>
                <div class="card"><h3>Projet 2</h3><p>Description</p></div>
            </div>
        </section>
        <section id="contact"><h2>Contact</h2>
            <form>
                <input type="text" placeholder="Nom" required>
                <input type="email" placeholder="Email" required>
                <textarea placeholder="Message" required></textarea>
                <button type="submit">Envoyer</button>
            </form>
        </section>
    </main>
    <footer><p>&copy; 2026</p></footer>
    <script src="script.js"></script>
</body>
</html>""",
        "style.css": """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:system-ui,sans-serif; line-height:1.6; color:#333; }
nav { display:flex; justify-content:space-between; padding:1rem 5%; background:rgba(255,255,255,0.95); position:fixed; width:100%; top:0; }
.hero { height:100vh; display:flex; flex-direction:column; justify-content:center; align-items:center; background:linear-gradient(135deg,#667eea,#764ba2); color:white; text-align:center; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:2rem; padding:2rem 5%; }
.card { background:white; padding:2rem; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1); }
form { display:flex; flex-direction:column; gap:1rem; max-width:500px; margin:0 auto; padding:2rem; }
input,textarea { padding:0.8rem; border:1px solid #ddd; border-radius:8px; }
button { padding:1rem 2rem; background:#667eea; color:white; border:none; border-radius:8px; cursor:pointer; }
footer { text-align:center; padding:2rem; background:#333; color:white; }""",
        "script.js": """document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
        e.preventDefault();
        document.querySelector(a.getAttribute('href')).scrollIntoView({behavior:'smooth'});
    });
});""",
    }


def _blog_template():
    return {
        "index.html": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mon Blog</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header><nav>
        <h1>Mon Blog</h1>
        <ul><li><a href="#articles">Articles</a></li></ul>
    </nav></header>
    <main>
        <section id="articles">
            <article class="post">
                <h2>Premier article</h2>
                <time>1 Janvier 2026</time>
                <p>Contenu de l'article...</p>
            </article>
        </section>
    </main>
    <footer><p>&copy; 2026 Mon Blog</p></footer>
</body>
</html>""",
        "style.css": """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:Georgia,serif; line-height:1.8; color:#333; max-width:800px; margin:0 auto; padding:2rem; }
nav { display:flex; justify-content:space-between; padding:1rem 0; border-bottom:1px solid #eee; }
.post { margin:2rem 0; padding:2rem; background:#f9f9f9; border-radius:8px; }
time { color:#666; font-size:0.9em; }
footer { text-align:center; padding:2rem; color:#666; }""",
    }


def _landing_template():
    return {
        "index.html": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Landing Page</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <section class="hero">
        <h1>Titre Accrocheur</h1>
        <p>Description de votre produit ou service</p>
        <a href="#cta" class="btn">Commencer</a>
    </section>
    <section class="features">
        <div class="feature"><h3>Feature 1</h3><p>Description</p></div>
        <div class="feature"><h3>Feature 2</h3><p>Description</p></div>
        <div class="feature"><h3>Feature 3</h3><p>Description</p></div>
    </section>
    <section id="cta" class="cta">
        <h2>Pret a commencer ?</h2>
        <a href="#" class="btn">S'inscrire</a>
    </section>
</body>
</html>""",
        "style.css": """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:system-ui,sans-serif; }
.hero { min-height:100vh; display:flex; flex-direction:column; justify-content:center; align-items:center; background:linear-gradient(135deg,#667eea,#764ba2); color:white; text-align:center; padding:2rem; }
.btn { display:inline-block; padding:1rem 2rem; background:white; color:#667eea; text-decoration:none; border-radius:8px; font-weight:bold; margin-top:1rem; }
.features { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:2rem; padding:4rem 5%; }
.feature { text-align:center; padding:2rem; }
.cta { text-align:center; padding:4rem 2rem; background:#f5f5f5; }""",
    }


def _app_template():
    return {
        "index.html": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mon App</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>Mon App</h1>
        </header>
        <main id="content">
            <p>Chargement...</p>
        </main>
    </div>
    <script src="app.js"></script>
</body>
</html>""",
        "style.css": """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:system-ui,sans-serif; background:#f0f2f5; }
header { background:#667eea; color:white; padding:1rem 2rem; }
main { max-width:800px; margin:2rem auto; padding:0 1rem; }""",
        "app.js": """document.getElementById('content').innerHTML = '<h2>Bienvenue dans Mon App</h2>';""",
    }
