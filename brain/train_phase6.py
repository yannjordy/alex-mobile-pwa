"""Phase 6 : Training Alex on website creation and light app installation."""
import json
import os

TRAINING_DATA_PATH = os.path.join(os.path.dirname(__file__), "finetune", "alex_training_data.jsonl")


def load_examples():
    examples = []
    if os.path.exists(TRAINING_DATA_PATH):
        with open(TRAINING_DATA_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        examples.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return examples


def save_examples(examples):
    os.makedirs(os.path.dirname(TRAINING_DATA_PATH), exist_ok=True)
    with open(TRAINING_DATA_PATH, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")


HTML_PAGE = (
    '<!DOCTYPE html>\n<html lang="fr">\n<head>\n'
    '    <meta charset="UTF-8">\n'
    '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    '    <title>Mon Portfolio</title>\n'
    '    <link rel="stylesheet" href="style.css">\n'
    '</head>\n<body>\n'
    '    <header><nav>\n'
    '        <h1>Mon Portfolio</h1>\n'
    '        <ul>\n'
    '            <li><a href="#accueil">Accueil</a></li>\n'
    '            <li><a href="#projets">Projets</a></li>\n'
    '            <li><a href="#contact">Contact</a></li>\n'
    '        </ul>\n'
    '    </nav></header>\n'
    '    <main>\n'
    '        <section id="accueil" class="hero">\n'
    '            <h2>Bienvenue !</h2>\n'
    '            <p>Developpeur web passionne</p>\n'
    '        </section>\n'
    '        <section id="projets"><h2>Mes Projets</h2>\n'
    '            <div class="projets-grid">\n'
    '                <div class="projet-card"><h3>Projet 1</h3><p>Description</p></div>\n'
    '            </div>\n'
    '        </section>\n'
    '        <section id="contact"><h2>Contact</h2>\n'
    '            <form>\n'
    '                <input type="text" placeholder="Nom" required>\n'
    '                <input type="email" placeholder="Email" required>\n'
    '                <textarea placeholder="Message" required></textarea>\n'
    '                <button type="submit">Envoyer</button>\n'
    '            </form>\n'
    '        </section>\n'
    '    </main>\n'
    '    <footer><p>&copy; 2026 Mon Portfolio</p></footer>\n'
    '</body>\n</html>'
)

CSS_PAGE = (
    '* { margin:0; padding:0; box-sizing:border-box; }\n'
    'body { font-family:system-ui,sans-serif; line-height:1.6; color:#333; }\n'
    'nav { display:flex; justify-content:space-between; align-items:center; padding:1rem 5%; '
    'background:rgba(255,255,255,0.95); backdrop-filter:blur(10px); position:fixed; width:100%; top:0; z-index:100; }\n'
    '.hero { height:100vh; display:flex; flex-direction:column; justify-content:center; '
    'align-items:center; background:linear-gradient(135deg,#667eea,#764ba2); color:white; text-align:center; }\n'
    '.projets-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:2rem; padding:2rem 5%; }\n'
    '.projet-card { background:white; padding:2rem; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1); '
    'transition:transform 0.3s; }\n'
    '.projet-card:hover { transform:translateY(-5px); }\n'
    'form { display:flex; flex-direction:column; gap:1rem; max-width:500px; margin:0 auto; padding:2rem; }\n'
    'input,textarea { padding:0.8rem; border:1px solid #ddd; border-radius:8px; font-size:1rem; }\n'
    'button { padding:1rem 2rem; background:#667eea; color:white; border:none; border-radius:8px; cursor:pointer; }\n'
    'footer { text-align:center; padding:2rem; background:#333; color:white; }'
)

REACT_APP = (
    "import { useState } from 'react'\n"
    "import './App.css'\n\n"
    "function App() {\n"
    "  const [todos, setTodos] = useState([])\n"
    "  const [input, setInput] = useState('')\n\n"
    "  const addTodo = (e) => {\n"
    "    e.preventDefault()\n"
    "    if (input.trim()) {\n"
    "      setTodos([...todos, { id: Date.now(), text: input, done: false }])\n"
    "      setInput('')\n"
    "    }\n"
    "  }\n\n"
    "  const toggleTodo = (id) => {\n"
    "    setTodos(todos.map(t => t.id === id ? {...t, done: !t.done} : t))\n"
    "  }\n\n"
    "  return (\n"
    "    <div className=\"app\">\n"
    "      <h1>Ma Liste de Taches</h1>\n"
    "      <form onSubmit={addTodo}>\n"
    "        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder=\"Nouvelle tache...\" />\n"
    "        <button type=\"submit\">Ajouter</button>\n"
    "      </form>\n"
    "      <ul>{todos.map(todo => (\n"
    "        <li key={todo.id} onClick={() => toggleTodo(todo.id)} className={todo.done ? 'done' : ''}>\n"
    "          {todo.text}\n"
    "        </li>\n"
    "      ))}</ul>\n"
    "    </div>\n"
    "  )\n"
    "}\n\nexport default App"
)

HUGO_TOML = (
    "baseURL = 'http://example.org/'\n"
    "languageCode = 'fr'\n"
    "title = 'Mon Blog'\n"
    "theme = 'PaperMod'\n\n"
    "[params]\n"
    "  author = 'Moi'\n"
    "  description = 'Mon blog personnel'\n"
    "  defaultTheme = 'auto'"
)

JS_SMOOTH_SCROLL = (
    "<script>\n"
    "document.querySelectorAll('a[href^=\"#\"]').forEach(anchor => {\n"
    "    anchor.addEventListener('click', function (e) {\n"
    "        e.preventDefault();\n"
    "        document.querySelector(this.getAttribute('href')).scrollIntoView({ behavior: 'smooth' });\n"
    "    });\n"
    "});\n"
    "</script>\n</body>"
)


def make_example(user_msg, assistant_msg, tool_calls, tools_used, context):
    """Helper to build a training example."""
    messages = [{"role": "user", "content": user_msg}]
    tc = []
    for name, args in tool_calls:
        tc.append({"type": "function", "function": {"name": name, "arguments": args}})
    assistant_entry = {"role": "assistant", "content": assistant_msg}
    if tc:
        assistant_entry["tool_calls"] = tc
    messages.append(assistant_entry)
    return {"messages": messages, "tools_used": tools_used, "context": context}


def get_new_examples():
    examples = []

    # --- Site creation ---

    examples.append(make_example(
        "Cree-moi un site web simple pour mon portfolio",
        "Je vais creer un site portfolio one-page moderne et epure.",
        [
            ("creer_dossier", {"path": "~/portfolio"}),
            ("write_code", {"path": "portfolio/index.html", "old": "", "new": HTML_PAGE}),
            ("write_code", {"path": "portfolio/style.css", "old": "", "new": CSS_PAGE}),
        ],
        ["creer_dossier", "write_code"],
        "Creation de site web portfolio"
    ))

    examples.append(make_example(
        "Ajoute un effet de defilement fluide sur mon site",
        "Je vais ajouter un smooth scroll avec JavaScript.",
        [("write_code", {"path": "portfolio/index.html", "old": "</body>", "new": JS_SMOOTH_SCROLL})],
        ["write_code"],
        "Ajout d'interactivite JavaScript"
    ))

    examples.append(make_example(
        "Cree un projet React avec Vite pour une app de taches",
        "Je vais initialiser un projet React avec Vite.",
        [
            ("executer_commande", {"commande": "cd ~ && npm create vite@latest todo-app -- --template react"}),
            ("executer_commande", {"commande": "cd ~/todo-app && npm install"}),
            ("write_code", {"path": "todo-app/src/App.jsx", "old": "import { useState } from 'react'", "new": REACT_APP}),
        ],
        ["executer_commande", "write_code"],
        "Creation d'application React avec Vite"
    ))

    examples.append(make_example(
        "Cree un blog avec Hugo",
        "Je vais installer Hugo et creer un nouveau blog.",
        [
            ("executer_commande", {"commande": "sudo apt install -y hugo"}),
            ("executer_commande", {"commande": "cd ~ && hugo new site mon-blog"}),
            ("executer_commande", {"commande": "cd ~/mon-blog && git init"}),
            ("write_code", {"path": "mon-blog/hugo.toml", "old": "", "new": HUGO_TOML}),
        ],
        ["executer_commande", "write_code"],
        "Installation + creation de site Hugo"
    ))

    # --- Light installs ---

    examples.append(make_example(
        "Installe-moi TypeScript et ts-node",
        "Je vais installer TypeScript et ts-node globalement.",
        [
            ("executer_commande", {"commande": "npm install -g typescript ts-node"}),
            ("verifier_outils", {"outil": "tsc --version"}),
        ],
        ["executer_commande", "verifier_outils"],
        "Installation de packages npm globaux"
    ))

    examples.append(make_example(
        "Installe curl et htop",
        "Je vais installer curl et htop pour toi.",
        [
            ("executer_commande", {"commande": "sudo apt update && sudo apt install -y curl htop"}),
            ("verifier_outils", {"outil": "curl --version"}),
        ],
        ["executer_commande", "verifier_outils"],
        "Installation de paquets systeme"
    ))

    examples.append(make_example(
        "Installe requests et beautifulsoup4",
        "Je vais installer ces bibliotheques Python.",
        [
            ("executer_commande", {"commande": "pip install requests beautifulsoup4"}),
            ("verifier_outils", {"outil": "python3 -c \"import requests; print(requests.__version__)\""}),
        ],
        ["executer_commande", "verifier_outils"],
        "Installation de packages Python"
    ))

    examples.append(make_example(
        "Installe ripgrep pour chercher dans les fichiers",
        "Je vais installer ripgrep, un outil de recherche ultra-rapide.",
        [
            ("executer_commande", {"commande": "sudo apt install -y ripgrep"}),
            ("verifier_outils", {"outil": "rg --version"}),
        ],
        ["executer_commande", "verifier_outils"],
        "Installation d'outil CLI"
    ))

    examples.append(make_example(
        "Installe VS Code",
        "Je vais installer Visual Studio Code.",
        [
            ("executer_commande", {"commande": "sudo snap install code --classic"}),
            ("verifier_outils", {"outil": "code --version"}),
        ],
        ["executer_commande", "verifier_outils"],
        "Installation via snap"
    ))

    examples.append(make_example(
        "Installe Node.js et npm",
        "Je vais installer Node.js LTS et npm.",
        [
            ("executer_commande", {"commande": "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -"}),
            ("executer_commande", {"commande": "sudo apt install -y nodejs"}),
            ("verifier_outils", {"outil": "node --version && npm --version"}),
        ],
        ["executer_commande", "verifier_outils"],
        "Installation de Node.js"
    ))

    # --- Combined ---

    examples.append(make_example(
        "Prepare un environnement pour developper en Node.js",
        "Je vais configurer un environnement Node.js complet.",
        [
            ("executer_commande", {"commande": "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -"}),
            ("executer_commande", {"commande": "sudo apt install -y nodejs"}),
            ("executer_commande", {"commande": "npm install -g yarn pnpm typescript ts-node nodemon"}),
            ("verifier_outils", {"outil": "node --version"}),
        ],
        ["executer_commande", "verifier_outils"],
        "Setup complet d'environnement Node.js"
    ))

    examples.append(make_example(
        "Cree un site WordPress local",
        "Je vais installer WordPress avec Docker.",
        [
            ("executer_commande", {"commande": "sudo apt install -y docker.io docker-compose"}),
            ("executer_commande", {"commande": "sudo systemctl start docker"}),
            ("write_code", {
                "path": "wordpress/docker-compose.yml",
                "old": "",
                "new": "version: '3'\nservices:\n  db:\n    image: mysql:5.7\n    environment:\n      MYSQL_ROOT_PASSWORD: root\n      MYSQL_DATABASE: wordpress\n    volumes:\n      - db_data:/var/lib/mysql\n  wordpress:\n    image: wordpress:latest\n    ports:\n      - '8080:80'\n    depends_on:\n      - db\n    environment:\n      WORDPRESS_DB_HOST: db:3306\n      WORDPRESS_DB_USER: root\n      WORDPRESS_DB_PASSWORD: root\nvolumes:\n  db_data:"
            }),
            ("executer_commande", {"commande": "cd ~/wordpress && sudo docker-compose up -d"}),
        ],
        ["executer_commande", "write_code"],
        "Installation WordPress avec Docker"
    ))

    examples.append(make_example(
        "Installe un serveur web nginx",
        "Je vais installer et configurer nginx.",
        [
            ("executer_commande", {"commande": "sudo apt update && sudo apt install -y nginx"}),
            ("executer_commande", {"commande": "sudo systemctl start nginx"}),
            ("executer_commande", {"commande": "sudo systemctl enable nginx"}),
            ("verifier_outils", {"outil": "nginx -v"}),
        ],
        ["executer_commande", "verifier_outils"],
        "Installation de nginx"
    ))

    examples.append(make_example(
        "Installe Python et les outils de dev",
        "Je vais installer Python 3 et les outils de developpement.",
        [
            ("executer_commande", {"commande": "sudo apt update && sudo apt install -y python3 python3-pip python3-venv"}),
            ("executer_commande", {"commande": "pip install --upgrade pip setuptools wheel"}),
            ("verifier_outils", {"outil": "python3 --version"}),
        ],
        ["executer_commande", "verifier_outils"],
        "Installation de Python et outils dev"
    ))

    return examples


def train():
    print("Phase 6 : Entrainement Creation Web & Installation Legere")
    print("=" * 60)

    existing = load_examples()
    print(f"Exemples existants : {len(existing)}")

    new_examples = get_new_examples()
    existing.extend(new_examples)
    save_examples(existing)

    print(f"Nouveaux exemples : {len(new_examples)}")
    print(f"Total : {len(existing)}")
    print("\nAlex peut maintenant :")
    print("  - Creer des sites web (HTML, CSS, JS, React, Hugo, WordPress)")
    print("  - Installer des apps legeres (npm, apt, pip, snap, docker)")
    print("  - Utiliser les modaux de progression et de code")
    print("  - Combiner installation et creation")
    print("\nTermine !")


if __name__ == "__main__":
    train()
