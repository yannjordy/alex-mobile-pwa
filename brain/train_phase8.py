"""Phase 8 : Entraînement Alex sur UI/UX Design pro (dashboards, vitrines, animations, effets)."""
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


def make_example(user_msg, assistant_msg, tool_calls, tools_used, context):
    messages = [{"role": "user", "content": user_msg}]
    tc = []
    for name, args in tool_calls:
        tc.append({"type": "function", "function": {"name": name, "arguments": args}})
    assistant_entry = {"role": "assistant", "content": assistant_msg}
    if tc:
        assistant_entry["tool_calls"] = tc
    messages.append(assistant_entry)
    return {"messages": messages, "tools_used": tools_used, "context": context}


DASHBOARD_EXAMPLES = [
    make_example(
        "Crée un dashboard analytics moderne",
        "Je vais créer un dashboard analytics avec graphiques et stats.",
        [
            ("write_code", {
                "path": "dashboard/index.html",
                "old": "",
                "new": "<!DOCTYPE html>\n<html lang=\"fr\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n<title>Dashboard Analytics</title>\n<link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n<div class=\"dashboard\">\n<aside class=\"sidebar\">\n<div class=\"logo\">Analytics</div>\n<nav>\n<a href=\"#\" class=\"active\">Overview</a>\n<a href=\"#\">Users</a>\n<a href=\"#\">Revenue</a>\n<a href=\"#\">Settings</a>\n</nav>\n</aside>\n<main class=\"main\">\n<header class=\"topbar\">\n<h1>Dashboard</h1>\n<div class=\"user-info\">\n<span class=\"avatar\">JD</span>\n</div>\n</header>\n<div class=\"stats-grid\">\n<div class=\"stat-card\">\n<div class=\"stat-label\">Revenue</div>\n<div class=\"stat-value\">$45,231</div>\n<div class=\"stat-change positive\">+20.1%</div>\n</div>\n<div class=\"stat-card\">\n<div class=\"stat-label\">Users</div>\n<div class=\"stat-value\">2,350</div>\n<div class=\"stat-change positive\">+180</div>\n</div>\n<div class=\"stat-card\">\n<div class=\"stat-label\">Orders</div>\n<div class=\"stat-value\">1,247</div>\n<div class=\"stat-change negative\">-5.2%</div>\n</div>\n<div class=\"stat-card\">\n<div class=\"stat-label\">Conversion</div>\n<div class=\"stat-value\">3.24%</div>\n<div class=\"stat-change positive\">+0.4%</div>\n</div>\n</div>\n<div class=\"charts-row\">\n<div class=\"chart-card\">\n<h3>Revenue Overview</h3>\n<div class=\"chart-placeholder\">Chart</div>\n</div>\n<div class=\"chart-card\">\n<h3>Top Products</h3>\n<div class=\"chart-placeholder\">Chart</div>\n</div>\n</div>\n</main>\n</div>\n<script src=\"script.js\"></script>\n</body>\n</html>"
            }),
            ("write_code", {
                "path": "dashboard/style.css",
                "old": "",
                "new": "* { margin:0; padding:0; box-sizing:border-box; }\n:root { --bg:#0f172a; --card:#1e293b; --border:#334155; --text:#f8fafc; --muted:#94a3b8; --accent:#3b82f6; --green:#22c55e; --red:#ef4444; }\nbody { font-family:'Inter',system-ui,sans-serif; background:var(--bg); color:var(--text); }\n.dashboard { display:flex; min-height:100vh; }\n.sidebar { width:240px; background:var(--card); border-right:1px solid var(--border); padding:20px; }\n.logo { font-size:20px; font-weight:700; color:var(--accent); margin-bottom:30px; }\n.sidebar nav a { display:block; padding:10px 15px; color:var(--muted); text-decoration:none; border-radius:8px; margin-bottom:5px; }\n.sidebar nav a:hover, .sidebar nav a.active { background:var(--accent); color:white; }\n.main { flex:1; padding:20px 30px; }\n.topbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:30px; }\n.avatar { width:36px; height:36px; border-radius:50%; background:var(--accent); display:flex; align-items:center; justify-content:center; font-size:14px; }\n.stats-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:20px; margin-bottom:30px; }\n.stat-card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; }\n.stat-label { color:var(--muted); font-size:13px; margin-bottom:5px; }\n.stat-value { font-size:24px; font-weight:700; }\n.stat-change { font-size:13px; margin-top:5px; }\n.stat-change.positive { color:var(--green); }\n.stat-change.negative { color:var(--red); }\n.charts-row { display:grid; grid-template-columns:1fr 1fr; gap:20px; }\n.chart-card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; }\n.chart-card h3 { margin-bottom:15px; font-size:15px; }\n.chart-placeholder { height:200px; background:rgba(59,130,246,0.1); border-radius:8px; display:flex; align-items:center; justify-content:center; color:var(--muted); }"
            }),
        ],
        ["write_code"],
        "Dashboard analytics moderne"
    ),

    make_example(
        "Crée un dashboard admin dark mode",
        "Je vais créer un dashboard admin avec thème sombre pro.",
        [
            ("write_code", {
                "path": "admin/index.html",
                "old": "",
                "new": "<!DOCTYPE html>\n<html lang=\"fr\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n<title>Admin Dashboard</title>\n<link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n<div class=\"admin\">\n<aside class=\"sidebar\">\n<div class=\"sidebar-header\">\n<div class=\"logo-icon\">A</div>\n<span>Admin</span>\n</div>\n<nav>\n<a href=\"#\" class=\"nav-item active\">\n<svg width=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\"><rect x=\"3\" y=\"3\" width=\"7\" height=\"7\"/><rect x=\"14\" y=\"3\" width=\"7\" height=\"7\"/><rect x=\"3\" y=\"14\" width=\"7\" height=\"7\"/><rect x=\"14\" y=\"14\" width=\"7\" height=\"7\"/></svg>\nDashboard\n</a>\n<a href=\"#\" class=\"nav-item\">\n<svg width=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\"><path d=\"M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4-4v2\"/><circle cx=\"9\" cy=\"7\" r=\"4\"/><path d=\"M23 21v-2a4 4 0 00-3-3.87\"/><path d=\"M16 3.13a4 4 0 010 7.75\"/></svg>\nUsers\n</a>\n<a href=\"#\" class=\"nav-item\">\n<svg width=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\"><circle cx=\"12\" cy=\"12\" r=\"3\"/><path d=\"M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z\"/></svg>\nSettings\n</a>\n</nav>\n</aside>\n<main class=\"content\">\n<header class=\"header\">\n<h1>Dashboard</h1>\n<div class=\"header-actions\">\n<button class=\"btn-icon\">🔔</button>\n<button class=\"btn-icon\">JD</button>\n</div>\n</header>\n<div class=\"grid\">\n<div class=\"card\">\n<div class=\"card-header\"><span>Total Revenue</span><span class=\"badge green\">+12%</span></div>\n<div class=\"card-value\">$45,231.89</div>\n<div class=\"card-desc\">+20.1% from last month</div>\n</div>\n<div class=\"card\">\n<div class=\"card-header\"><span>Subscriptions</span><span class=\"badge blue\">+201</span></div>\n<div class=\"card-value\">+2350</div>\n<div class=\"card-desc\">+180.1% from last month</div>\n</div>\n</div>\n</main>\n</div>\n<script src=\"script.js\"></script>\n</body>\n</html>"
            }),
        ],
        ["write_code"],
        "Dashboard admin dark mode"
    ),
]

VITRINE_EXAMPLES = [
    make_example(
        "Crée un site vitrine SaaS moderne",
        "Je vais créer un site vitrine SaaS avec hero et features.",
        [
            ("write_code", {
                "path": "saas/index.html",
                "old": "",
                "new": "<!DOCTYPE html>\n<html lang=\"fr\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n<title>SaaS - Productivité décuplée</title>\n<link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n<nav class=\"navbar\">\n<div class=\"container\">\n<span class=\"logo\">FlowApp</span>\n<div class=\"nav-links\">\n<a href=\"#features\">Features</a>\n<a href=\"#pricing\">Pricing</a>\n<a href=\"#testimonials\">Testimonials</a>\n<a href=\"#cta\" class=\"btn btn-primary\">Get Started</a>\n</div>\n</div>\n</nav>\n<section class=\"hero\">\n<div class=\"container\">\n<div class=\"hero-badge\">New: AI-powered features</div>\n<h1>Build products<br><span class=\"gradient-text\">10x faster</span></h1>\n<p>The all-in-one platform that helps teams ship products faster with AI assistance.</p>\n<div class=\"hero-buttons\">\n<a href=\"#cta\" class=\"btn btn-primary btn-lg\">Start Free Trial</a>\n<a href=\"#demo\" class=\"btn btn-ghost btn-lg\">Watch Demo →</a>\n</div>\n<div class=\"hero-visual\">\n<div class=\"mockup\"></div>\n</div>\n</div>\n</section>\n<section id=\"features\" class=\"features\">\n<div class=\"container\">\n<h2>Everything you need</h2>\n<p class=\"subtitle\">Powerful features to boost your productivity</p>\n<div class=\"features-grid\">\n<div class=\"feature-card\">\n<div class=\"feature-icon\">⚡</div>\n<h3>Lightning Fast</h3>\n<p>Built for speed with modern architecture</p>\n</div>\n<div class=\"feature-card\">\n<div class=\"feature-icon\">🔒</div>\n<h3>Secure</h3>\n<p>Enterprise-grade security by default</p>\n</div>\n<div class=\"feature-card\">\n<div class=\"feature-icon\">🤖</div>\n<h3>AI-Powered</h3>\n<p>Smart suggestions and automation</p>\n</div>\n</div>\n</div>\n</section>\n<section id=\"testimonials\" class=\"testimonials\">\n<div class=\"container\">\n<h2>Loved by teams</h2>\n<div class=\"testimonials-grid\">\n<div class=\"testimonial-card\">\n<p>\"FlowApp changed how we work. Amazing product!\"</p>\n<div class=\"author\">\n<div class=\"avatar\">SK</div>\n<div><strong>Sarah K.</strong><br><span>CTO, TechCorp</span></div>\n</div>\n</div>\n</div>\n</div>\n</section>\n<section id=\"cta\" class=\"cta\">\n<div class=\"container\">\n<h2>Ready to get started?</h2>\n<p>Join 10,000+ teams already using FlowApp</p>\n<a href=\"#\" class=\"btn btn-primary btn-lg\">Start Free Trial</a>\n</div>\n</section>\n<footer class=\"footer\">\n<div class=\"container\">\n<p>© 2026 FlowApp. All rights reserved.</p>\n</div>\n</footer>\n<script src=\"script.js\"></script>\n</body>\n</html>"
            }),
        ],
        ["write_code"],
        "Site vitrine SaaS"
    ),

    make_example(
        "Crée un portfolio créatif avec effets parallax",
        "Je vais créer un portfolio avec effets de parallaxe et animations.",
        [
            ("write_code", {
                "path": "portfolio/index.html",
                "old": "",
                "new": "<!DOCTYPE html>\n<html lang=\"fr\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n<title>Portfolio Creatif</title>\n<link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n<div class=\"cursor\"></div>\n<nav class=\"nav\">\n<a href=\"#\" class=\"logo\">JD</a>\n<div class=\"nav-links\">\n<a href=\"#work\">Work</a>\n<a href=\"#about\">About</a>\n<a href=\"#contact\">Contact</a>\n</div>\n</nav>\n<section class=\"hero\">\n<div class=\"hero-content\">\n<h1 class=\"split-text\">Creative<br>Developer</h1>\n<p class=\"fade-up\">Based in Paris, crafting digital experiences</p>\n</div>\n<div class=\"scroll-indicator\">\n<span>Scroll</span>\n<div class=\"line\"></div>\n</div>\n</section>\n<section id=\"work\" class=\"work\">\n<div class=\"container\">\n<h2 class=\"reveal-text\">Selected Work</h2>\n<div class=\"project-grid\">\n<div class=\"project-card\" data-speed=\"0.8\">\n<div class=\"project-image\"></div>\n<h3>E-Commerce Platform</h3>\n<p>Web Design / Development</p>\n</div>\n<div class=\"project-card\" data-speed=\"1.2\">\n<div class=\"project-image\"></div>\n<h3>Mobile App</h3>\n<p>UI/UX Design</p>\n</div>\n</div>\n</div>\n</section>\n<section id=\"about\" class=\"about\">\n<div class=\"container\">\n<h2 class=\"reveal-text\">About Me</h2>\n<div class=\"about-content\">\n<div class=\"about-text fade-up\">\n<p>I'm a creative developer passionate about building beautiful digital experiences.</p>\n</div>\n</div>\n</div>\n</section>\n<section id=\"contact\" class=\"contact\">\n<div class=\"container\">\n<h2 class=\"reveal-text\">Let's Talk</h2>\n<a href=\"mailto:hello@example.com\" class=\"contact-link fade-up\">hello@example.com</a>\n</div>\n</section>\n<script src=\"script.js\"></script>\n</body>\n</html>"
            }),
        ],
        ["write_code"],
        "Portfolio créatif parallax"
    ),
]

ANIMATION_CSS_EXAMPLES = [
    make_example(
        "Ajoute des animations de scroll révélées",
        "Je vais ajouter des animations qui se déclenchent au scroll.",
        [
            ("write_code", {
                "path": "animations/scroll-reveal.js",
                "old": "",
                "new": "const observerOptions = {\n  root: null,\n  rootMargin: '0px',\n  threshold: 0.1\n};\n\nconst observer = new IntersectionObserver((entries) => {\n  entries.forEach(entry => {\n    if (entry.isIntersecting) {\n      entry.target.classList.add('revealed');\n    }\n  });\n}, observerOptions);\n\ndocument.querySelectorAll('.reveal, .fade-up, .slide-in').forEach(el => {\n  observer.observe(el);\n});"
            }),
            ("write_code", {
                "path": "animations/style.css",
                "old": "",
                "new": ".reveal { opacity: 0; transform: translateY(30px); transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1); }\n.reveal.revealed { opacity: 1; transform: translateY(0); }\n.fade-up { opacity: 0; transform: translateY(40px); transition: all 0.6s ease-out; }\n.fade-up.revealed { opacity: 1; transform: translateY(0); }\n.slide-in { opacity: 0; transform: translateX(-50px); transition: all 0.7s ease-out; }\n.slide-in.revealed { opacity: 1; transform: translateX(0); }\n.stagger-1 { transition-delay: 0.1s; }\n.stagger-2 { transition-delay: 0.2s; }\n.stagger-3 { transition-delay: 0.3s; }"
            }),
        ],
        ["write_code"],
        "Animations scroll reveal"
    ),

    make_example(
        "Crée des animations de hover interactives",
        "Je vais créer des effets de hover modernes.",
        [
            ("write_code", {
                "path": "animations/hover-effects.css",
                "old": "",
                "new": ".card-hover {\n  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);\n}\n.card-hover:hover {\n  transform: translateY(-8px);\n  box-shadow: 0 20px 40px rgba(0,0,0,0.15);\n}\n\n.magnetic-btn {\n  position: relative;\n  transition: transform 0.3s ease;\n}\n.magnetic-btn:hover {\n  transform: scale(1.05);\n}\n\n.text-reveal {\n  position: relative;\n  overflow: hidden;\n}\n.text-reveal::after {\n  content: '';\n  position: absolute;\n  bottom: 0;\n  left: 0;\n  width: 100%;\n  height: 2px;\n  background: currentColor;\n  transform: scaleX(0);\n  transform-origin: right;\n  transition: transform 0.4s ease;\n}\n.text-reveal:hover::after {\n  transform: scaleX(1);\n  transform-origin: left;\n}\n\n.image-zoom {\n  overflow: hidden;\n}\n.image-zoom img {\n  transition: transform 0.6s ease;\n}\n.image-zoom:hover img {\n  transform: scale(1.1);\n}"
            }),
        ],
        ["write_code"],
        "Animations hover CSS"
    ),

    make_example(
        "Crée une animation de loader élégante",
        "Je vais créer un loader animé pour ton site.",
        [
            ("write_code", {
                "path": "animations/loader.html",
                "old": "",
                "new": "<!DOCTYPE html>\n<html lang=\"fr\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n<title>Loader</title>\n<style>\nbody { display:flex; align-items:center; justify-content:center; min-height:100vh; background:#0f172a; margin:0; }\n.loader { display:flex; gap:8px; }\n.loader span {\n  width:12px; height:12px; border-radius:50%; background:#3b82f6;\n  animation: bounce 1.4s infinite ease-in-out both;\n}\n.loader span:nth-child(1) { animation-delay:-0.32s; }\n.loader span:nth-child(2) { animation-delay:-0.16s; }\n.loader span:nth-child(3) { animation-delay:0s; }\n@keyframes bounce { 0%,80%,100% { transform:scale(0); } 40% { transform:scale(1); } }\n</style>\n</head>\n<body>\n<div class=\"loader\"><span></span><span></span><span></span></div>\n</body>\n</html>"
            }),
        ],
        ["write_code"],
        "Loader animé"
    ),

    make_example(
        "Ajoute un effet de typing pour du texte",
        "Je vais créer un effet machine à écrire.",
        [
            ("write_code", {
                "path": "animations/typing.js",
                "old": "",
                "new": "class TypeWriter {\n  constructor(element, words, wait = 100) {\n    this.element = element;\n    this.words = words;\n    this.wait = wait;\n    this.wordIndex = 0;\n    this.txt = '';\n    this.type();\n  }\n\n  type() {\n    const current = this.wordIndex % this.words.length;\n    const fullTxt = this.words[current];\n    this.txt = fullTxt.substring(0, this.txt.length + 1);\n    this.element.innerHTML = this.txt + '<span class=\"cursor\">|</span>';\n\n    let typeSpeed = 100;\n    if (this.txt === fullTxt) {\n      typeSpeed = 2000;\n      this.wordIndex++;\n    }\n\n    setTimeout(() => this.type(), typeSpeed);\n  }\n}\n\nconst el = document.querySelector('.typewriter');\nif (el) new TypeWriter(el, ['Developer', 'Designer', 'Creator']);"
            }),
        ],
        ["write_code"],
        "Effet typing"
    ),
]

EFFETS_VISUELS_EXAMPLES = [
    make_example(
        "Crée un effet glassmorphism pro",
        "Je vais créer des cartes avec effet glassmorphism.",
        [
            ("write_code", {
                "path": "effects/glassmorphism.css",
                "old": "",
                "new": ".glass-card {\n  background: rgba(255, 255, 255, 0.05);\n  backdrop-filter: blur(20px);\n  -webkit-backdrop-filter: blur(20px);\n  border: 1px solid rgba(255, 255, 255, 0.1);\n  border-radius: 20px;\n  padding: 30px;\n  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);\n}\n\n.glass-card::before {\n  content: '';\n  position: absolute;\n  top: 0;\n  left: 0;\n  right: 0;\n  bottom: 0;\n  border-radius: 20px;\n  padding: 1px;\n  background: linear-gradient(\n    135deg,\n    rgba(255,255,255,0.4),\n    rgba(255,255,255,0.1)\n  );\n  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);\n  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);\n  -webkit-mask-composite: xor;\n  mask-composite: exclude;\n}"
            }),
        ],
        ["write_code"],
        "Glassmorphism"
    ),

    make_example(
        "Crée un gradient animé de fond",
        "Je vais créer un fond avec gradient animé.",
        [
            ("write_code", {
                "path": "effects/animated-gradient.css",
                "old": "",
                "new": ".animated-gradient {\n  background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);\n  background-size: 400% 400%;\n  animation: gradientShift 15s ease infinite;\n}\n\n@keyframes gradientShift {\n  0% { background-position: 0% 50%; }\n  50% { background-position: 100% 50%; }\n  100% { background-position: 0% 50%; }\n}\n\n.mesh-gradient {\n  background:\n    radial-gradient(at 40% 20%, hsla(28,100%,74%,1) 0, transparent 50%),\n    radial-gradient(at 80% 0%, hsla(189,100%,56%,1) 0, transparent 50%),\n    radial-gradient(at 0% 50%, hsla(355,100%,93%,1) 0, transparent 50%),\n    radial-gradient(at 80% 50%, hsla(340,100%,76%,1) 0, transparent 50%),\n    radial-gradient(at 0% 100%, hsla(22,100%,77%,1) 0, transparent 50%);\n  background-color: #fff;\n}"
            }),
        ],
        ["write_code"],
        "Gradient animé"
    ),

    make_example(
        "Crée un effet de particules interactif",
        "Je vais créer un canvas avec des particules qui réagissent à la souris.",
        [
            ("write_code", {
                "path": "effects/particles.js",
                "old": "",
                "new": "const canvas = document.getElementById('particles');\nconst ctx = canvas.getContext('2d');\ncanvas.width = window.innerWidth;\ncanvas.height = window.innerHeight;\n\nconst particles = [];\nconst particleCount = 80;\n\nfor (let i = 0; i < particleCount; i++) {\n  particles.push({\n    x: Math.random() * canvas.width,\n    y: Math.random() * canvas.height,\n    vx: (Math.random() - 0.5) * 0.5,\n    vy: (Math.random() - 0.5) * 0.5,\n    size: Math.random() * 2 + 1\n  });\n}\n\nlet mouse = { x: null, y: null };\ncanvas.addEventListener('mousemove', (e) => {\n  mouse.x = e.clientX;\n  mouse.y = e.clientY;\n});\n\nfunction animate() {\n  ctx.clearRect(0, 0, canvas.width, canvas.height);\n  particles.forEach((p, i) => {\n    p.x += p.vx;\n    p.y += p.vy;\n    if (p.x < 0 || p.x > canvas.width) p.vx *= -1;\n    if (p.y < 0 || p.y > canvas.height) p.vy *= -1;\n    ctx.beginPath();\n    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);\n    ctx.fillStyle = 'rgba(59, 130, 246, 0.5)';\n    ctx.fill();\n    particles.forEach((p2, j) => {\n      if (i === j) return;\n      const dist = Math.hypot(p.x - p2.x, p.y - p2.y);\n      if (dist < 100) {\n        ctx.beginPath();\n        ctx.moveTo(p.x, p.y);\n        ctx.lineTo(p2.x, p2.y);\n        ctx.strokeStyle = `rgba(59, 130, 246, ${1 - dist/100})`;\n        ctx.stroke();\n      }\n    });\n  });\n  requestAnimationFrame(animate);\n}\nanimate();"
            }),
        ],
        ["write_code"],
        "Particules interactives"
    ),

    make_example(
        "Crée un effet de morphing de texte",
        "Je vais créer un effet où le texte se transforme en boucle.",
        [
            ("write_code", {
                "path": "effects/morph-text.js",
                "old": "",
                "new": "const words = ['Designer', 'Developer', 'Creator', 'Innovator'];\nlet wordIndex = 0;\nlet charIndex = 0;\nlet isDeleting = false;\nconst element = document.querySelector('.morph-text');\n\nfunction type() {\n  const currentWord = words[wordIndex];\n  \n  if (isDeleting) {\n    element.textContent = currentWord.substring(0, charIndex - 1);\n    charIndex--;\n  } else {\n    element.textContent = currentWord.substring(0, charIndex + 1);\n    charIndex++;\n  }\n\n  let speed = isDeleting ? 50 : 100;\n\n  if (!isDeleting && charIndex === currentWord.length) {\n    speed = 2000;\n    isDeleting = true;\n  } else if (isDeleting && charIndex === 0) {\n    isDeleting = false;\n    wordIndex = (wordIndex + 1) % words.length;\n    speed = 500;\n  }\n\n  setTimeout(type, speed);\n}\n\ntype();"
            }),
        ],
        ["write_code"],
        "Morphing texte"
    ),
]

STYLE_SYSTEM_EXAMPLES = [
    make_example(
        "Crée un système de design tokens",
        "Je vais créer un fichier de design tokens pour unifier le style.",
        [
            ("write_code", {
                "path": "design/tokens.css",
                "old": "",
                "new": ":root {\n  /* Colors */\n  --color-primary: #3b82f6;\n  --color-primary-light: #60a5fa;\n  --color-primary-dark: #2563eb;\n  --color-secondary: #8b5cf6;\n  --color-success: #22c55e;\n  --color-warning: #f59e0b;\n  --color-error: #ef4444;\n  --color-bg: #0f172a;\n  --color-bg-card: #1e293b;\n  --color-bg-hover: #334155;\n  --color-text: #f8fafc;\n  --color-text-muted: #94a3b8;\n  --color-border: #334155;\n\n  /* Typography */\n  --font-sans: 'Inter', system-ui, sans-serif;\n  --font-mono: 'JetBrains Mono', monospace;\n  --text-xs: 0.75rem;\n  --text-sm: 0.875rem;\n  --text-base: 1rem;\n  --text-lg: 1.125rem;\n  --text-xl: 1.25rem;\n  --text-2xl: 1.5rem;\n  --text-3xl: 1.875rem;\n  --text-4xl: 2.25rem;\n\n  /* Spacing */\n  --space-1: 0.25rem;\n  --space-2: 0.5rem;\n  --space-3: 0.75rem;\n  --space-4: 1rem;\n  --space-6: 1.5rem;\n  --space-8: 2rem;\n  --space-12: 3rem;\n  --space-16: 4rem;\n\n  /* Radius */\n  --radius-sm: 0.375rem;\n  --radius-md: 0.5rem;\n  --radius-lg: 0.75rem;\n  --radius-xl: 1rem;\n  --radius-2xl: 1.5rem;\n  --radius-full: 9999px;\n\n  /* Shadows */\n  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);\n  --shadow-md: 0 4px 6px rgba(0,0,0,0.1);\n  --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);\n  --shadow-xl: 0 20px 25px rgba(0,0,0,0.15);\n\n  /* Transitions */\n  --transition-fast: 150ms ease;\n  --transition-base: 300ms ease;\n  --transition-slow: 500ms ease;\n}"
            }),
        ],
        ["write_code"],
        "Design tokens"
    ),

    make_example(
        "Crée une librairie de composants UI",
        "Je vais créer des composants UI réutilisables.",
        [
            ("write_code", {
                "path": "design/components.css",
                "old": "",
                "new": ".btn {\n  display: inline-flex; align-items: center; justify-content: center;\n  padding: 0.625rem 1.25rem; border-radius: var(--radius-lg);\n  font-weight: 500; font-size: var(--text-sm);\n  transition: all var(--transition-fast);\n  cursor: pointer; border: none; outline: none;\n}\n.btn:focus-visible { box-shadow: 0 0 0 3px rgba(59,130,246,0.5); }\n.btn-primary { background: var(--color-primary); color: white; }\n.btn-primary:hover { background: var(--color-primary-dark); transform: translateY(-1px); }\n.btn-secondary { background: var(--color-bg-hover); color: var(--color-text); }\n.btn-ghost { background: transparent; color: var(--color-text); }\n.btn-ghost:hover { background: var(--color-bg-hover); }\n\n.input {\n  width: 100%; padding: 0.625rem 1rem;\n  background: var(--color-bg); border: 1px solid var(--color-border);\n  border-radius: var(--radius-lg); color: var(--color-text);\n  font-size: var(--text-sm); transition: border-color var(--transition-fast);\n}\n.input:focus { border-color: var(--color-primary); outline: none; }\n.input::placeholder { color: var(--color-text-muted); }\n\n.badge {\n  display: inline-flex; align-items: center;\n  padding: 0.25rem 0.75rem; border-radius: var(--radius-full);\n  font-size: var(--text-xs); font-weight: 600;\n}\n.badge-primary { background: rgba(59,130,246,0.2); color: var(--color-primary-light); }\n.badge-success { background: rgba(34,197,94,0.2); color: var(--color-success); }\n.badge-warning { background: rgba(245,158,11,0.2); color: var(--color-warning); }\n.badge-error { background: rgba(239,68,68,0.2); color: var(--color-error); }\n\n.card {\n  background: var(--color-bg-card); border: 1px solid var(--color-border);\n  border-radius: var(--radius-xl); padding: var(--space-6);\n  transition: all var(--transition-base);\n}\n.card:hover { border-color: var(--color-primary); transform: translateY(-2px); }"
            }),
        ],
        ["write_code"],
        "Librairie composants UI"
    ),
]


def train():
    print("Phase 8 : Entrainement UI/UX Design Pro")
    print("=" * 60)

    existing = load_examples()
    print(f"Exemples existants : {len(existing)}")

    new_examples = (
        DASHBOARD_EXAMPLES + VITRINE_EXAMPLES + ANIMATION_CSS_EXAMPLES +
        EFFETS_VISUELS_EXAMPLES + STYLE_SYSTEM_EXAMPLES
    )
    existing.extend(new_examples)
    save_examples(existing)

    print(f"Nouveaux exemples : {len(new_examples)}")
    print(f"Total : {len(existing)}")
    print(f"\nDetail :")
    print(f"  - Dashboards : {len(DASHBOARD_EXAMPLES)} exemples")
    print(f"    - Analytics moderne, Admin dark mode")
    print(f"  - Sites vitrines : {len(VITRINE_EXAMPLES)} exemples")
    print(f"    - SaaS moderne, Portfolio créatif parallax")
    print(f"  - Animations CSS : {len(ANIMATION_CSS_EXAMPLES)} exemples")
    print(f"    - Scroll reveal, Hover effects, Loader, Typing")
    print(f"  - Effets visuels : {len(EFFETS_VISUELS_EXAMPLES)} exemples")
    print(f"    - Glassmorphism, Gradient animé, Particules, Morphing")
    print(f"  - Système de style : {len(STYLE_SYSTEM_EXAMPLES)} exemples")
    print(f"    - Design tokens, Librairie composants")
    print("\nAlex peut maintenant :")
    print("  - Créer des dashboards pro (stats, graphiques, sidebar)")
    print("  - Concevoir des sites vitrines (hero, features, CTA)")
    print("  - Animer avec CSS/JS (scroll, hover, typing, loaders)")
    print("  - Créer des effets visuels (glass, gradients, particules)")
    print("  - Définir un système de design (tokens, composants)")
    print("\nTermine !")


if __name__ == "__main__":
    train()
