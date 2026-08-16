"""Phase 7 : Entraînement Alex sur DevOps (Docker, K8s, CI/CD, Monitoring)."""
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


DOCKER_EXAMPLES = [
    make_example(
        "Installe Docker sur ma machine",
        "Je vais installer Docker Engine.",
        [
            ("executer_commande", {"commande": "sudo apt update && sudo apt install -y docker.io"}),
            ("executer_commande", {"commande": "sudo systemctl start docker && sudo systemctl enable docker"}),
            ("executer_commande", {"commande": "sudo usermod -aG docker $USER"}),
            ("verifier_outils", {"outil": "docker --version"}),
        ],
        ["executer_commande", "verifier_outils"],
        "Installation de Docker"
    ),

    make_example(
        "Lance un conteneur Nginx",
        "Je vais lancer un conteneur Nginx sur le port 8080.",
        [
            ("executer_commande", {"commande": "docker run -d --name nginx -p 8080:80 nginx:latest"}),
            ("executer_commande", {"commande": "docker ps"}),
        ],
        ["executer_commande"],
        "Lancement de conteneur Nginx"
    ),

    make_example(
        "Crée un Dockerfile pour mon app Node.js",
        "Je vais créer un Dockerfile optimisé pour ton application Node.js.",
        [
            ("write_code", {
                "path": "Dockerfile",
                "old": "",
                "new": "FROM node:20-alpine AS builder\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci --only=production\n\nFROM node:20-alpine\nWORKDIR /app\nCOPY --from=builder /app/node_modules ./node_modules\nCOPY . .\nEXPOSE 3000\nCMD [\"node\", \"server.js\"]"
            }),
        ],
        ["write_code"],
        "Création de Dockerfile"
    ),

    make_example(
        "Monte un docker-compose pour PostgreSQL + pgAdmin",
        "Je vais créer un docker-compose avec PostgreSQL et pgAdmin.",
        [
            ("write_code", {
                "path": "docker-compose.yml",
                "old": "",
                "new": "version: '3.8'\nservices:\n  db:\n    image: postgres:16-alpine\n    environment:\n      POSTGRES_USER: admin\n      POSTGRES_PASSWORD: secret\n      POSTGRES_DB: mydb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n    ports:\n      - '5432:5432'\n\n  pgadmin:\n    image: dpage/pgadmin4\n    environment:\n      PGADMIN_DEFAULT_EMAIL: admin@admin.com\n      PGADMIN_DEFAULT_PASSWORD: admin\n    ports:\n      - '5050:80'\n    depends_on:\n      - db\n\nvolumes:\n  pgdata:"
            }),
            ("executer_commande", {"commande": "docker-compose up -d"}),
        ],
        ["write_code", "executer_commande"],
        "Docker Compose PostgreSQL + pgAdmin"
    ),

    make_example(
        "Liste tous les conteneurs Docker",
        "Voici la liste de tes conteneurs Docker.",
        [("executer_commande", {"commande": "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"})],
        ["executer_commande"],
        "Liste des conteneurs Docker"
    ),

    make_example(
        "Arrête et supprime tous les conteneurs",
        "Je vais arrêter et supprimer tous les conteneurs.",
        [
            ("executer_commande", {"commande": "docker stop $(docker ps -q)"}),
            ("executer_commande", {"commande": "docker rm $(docker ps -aq)"}),
        ],
        ["executer_commande"],
        "Nettoyage des conteneurs Docker"
    ),

    make_example(
        "Construit l'image Docker de mon projet",
        "Je vais construire l'image Docker de ton projet.",
        [
            ("executer_commande", {"commande": "docker build -t mon-app:latest ."}),
            ("executer_commande", {"commande": "docker images mon-app"}),
        ],
        ["executer_commande"],
        "Build d'image Docker"
    ),

    make_example(
        "Push l'image sur Docker Hub",
        "Je vais push l'image sur Docker Hub.",
        [
            ("executer_commande", {"commande": "docker login"}),
            ("executer_commande", {"commande": "docker tag mon-app:latest monuser/mon-app:latest"}),
            ("executer_commande", {"commande": "docker push monuser/mon-app:latest"}),
        ],
        ["executer_commande"],
        "Push Docker Hub"
    ),

    make_example(
        "Nettoie les images et volumes inutilisés",
        "Je vais nettoyer les images et volumes orphelins.",
        [
            ("executer_commande", {"commande": "docker system prune -a --volumes -f"}),
            ("executer_commande", {"commande": "docker volume prune -f"}),
        ],
        ["executer_commande"],
        "Nettoyage Docker"
    ),

    make_example(
        "Crée un réseau Docker personnalisé",
        "Je vais créer un réseau bridge pour tes conteneurs.",
        [("executer_commande", {"commande": "docker network create --driver bridge mon-reseau"})],
        ["executer_commande"],
        "Réseau Docker"
    ),
]

K8S_EXAMPLES = [
    make_example(
        "Installe kubectl",
        "Je vais installer kubectl pour gérer Kubernetes.",
        [
            ("executer_commande", {"commande": "curl -LO https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"}),
            ("executer_commande", {"commande": "sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl"}),
            ("verifier_outils", {"outil": "kubectl version --client"}),
        ],
        ["executer_commande", "verifier_outils"],
        "Installation kubectl"
    ),

    make_example(
        "Crée un déploiement Kubernetes pour mon app",
        "Je vais créer un manifest de déploiement K8s.",
        [
            ("write_code", {
                "path": "k8s/deployment.yaml",
                "old": "",
                "new": "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: mon-app\nspec:\n  replicas: 3\n  selector:\n    matchLabels:\n      app: mon-app\n  template:\n    metadata:\n      labels:\n        app: mon-app\n    spec:\n      containers:\n      - name: mon-app\n        image: mon-app:latest\n        ports:\n        - containerPort: 3000\n        resources:\n          requests:\n            memory: \"128Mi\"\n            cpu: \"100m\"\n          limits:\n            memory: \"256Mi\"\n            cpu: \"500m\""
            }),
            ("write_code", {
                "path": "k8s/service.yaml",
                "old": "",
                "new": "apiVersion: v1\nkind: Service\nmetadata:\n  name: mon-app-service\nspec:\n  selector:\n    app: mon-app\n  ports:\n  - port: 80\n    targetPort: 3000\n  type: LoadBalancer"
            }),
        ],
        ["write_code"],
        "Déploiement Kubernetes"
    ),

    make_example(
        "Applique les manifests Kubernetes",
        "Je vais appliquer tes manifests K8s.",
        [
            ("executer_commande", {"commande": "kubectl apply -f k8s/deployment.yaml"}),
            ("executer_commande", {"commande": "kubectl apply -f k8s/service.yaml"}),
            ("executer_commande", {"commande": "kubectl get pods"}),
        ],
        ["executer_commande"],
        "Application manifests K8s"
    ),

    make_example(
        "Monte le status du cluster Kubernetes",
        "Voici l'état de ton cluster K8s.",
        [
            ("executer_commande", {"commande": "kubectl get nodes"}),
            ("executer_commande", {"commande": "kubectl get pods -A"}),
            ("executer_commande", {"commande": "kubectl top nodes"}),
        ],
        ["executer_commande"],
        "Status cluster K8s"
    ),

    make_example(
        "Scale le déploiement à 5 replicas",
        "Je vais scaler le déploiement à 5 replicas.",
        [("executer_commande", {"commande": "kubectl scale deployment mon-app --replicas=5"})],
        ["executer_commande"],
        "Scale K8s"
    ),

    make_example(
        "Regarde les logs du pod mon-app",
        "Voici les logs du pod mon-app.",
        [("executer_commande", {"commande": "kubectl logs -l app=mon-app --tail=50"})],
        ["executer_commande"],
        "Logs K8s"
    ),

    make_example(
        "Supprime le déploiement Kubernetes",
        "Je vais supprimer le déploiement K8s.",
        [
            ("executer_commande", {"commande": "kubectl delete -f k8s/service.yaml"}),
            ("executer_commande", {"commande": "kubectl delete -f k8s/deployment.yaml"}),
        ],
        ["executer_commande"],
        "Suppression déploiement K8s"
    ),
]

CICD_EXAMPLES = [
    make_example(
        "Crée un pipeline GitHub Actions pour mon projet",
        "Je vais créer un workflow CI/CD GitHub Actions.",
        [
            ("executer_commande", {"commande": "mkdir -p .github/workflows"}),
            ("write_code", {
                "path": ".github/workflows/ci.yml",
                "old": "",
                "new": "name: CI/CD\n\non:\n  push:\n    branches: [main]\n  pull_request:\n    branches: [main]\n\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n      - run: npm ci\n      - run: npm test\n\n  deploy:\n    needs: test\n    if: github.ref == 'refs/heads/main'\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - name: Deploy\n        run: echo \"Deploying...\""
            }),
        ],
        ["executer_commande", "write_code"],
        "Pipeline GitHub Actions"
    ),

    make_example(
        "Installe Jenkins",
        "Je vais installer Jenkins via Docker.",
        [
            ("executer_commande", {"commande": "docker run -d --name jenkins -p 8080:8080 -p 50000:50000 -v jenkins_home:/var/jenkins_home jenkins/jenkins:lts"}),
            ("executer_commande", {"commande": "docker logs jenkins 2>&1 | head -20"}),
        ],
        ["executer_commande"],
        "Installation Jenkins"
    ),

    make_example(
        "Crée un Dockerfile avec build multi-stage",
        "Je vais créer un Dockerfile optimisé avec multi-stage build.",
        [
            ("write_code", {
                "path": "Dockerfile.multistage",
                "old": "",
                "new": "# Stage 1: Build\nFROM node:20-alpine AS build\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci\nCOPY . .\nRUN npm run build\n\n# Stage 2: Production\nFROM node:20-alpine\nWORKDIR /app\nCOPY --from=build /app/dist ./dist\nCOPY --from=build /app/node_modules ./node_modules\nCOPY package*.json ./\nEXPOSE 3000\nUSER node\nCMD [\"node\", \"dist/server.js\"]"
            }),
        ],
        ["write_code"],
        "Dockerfile multi-stage"
    ),

    make_example(
        "Configure un registry Docker privé",
        "Je vais configurer un registry Docker privé avec Harbor.",
        [
            ("write_code", {
                "path": "docker-compose.registry.yml",
                "old": "",
                "new": "version: '3.8'\nservices:\n  registry:\n    image: registry:2\n    ports:\n      - '5000:5000'\n    volumes:\n      - registry_data:/var/lib/registry\n\nvolumes:\n  registry_data:"
            }),
            ("executer_commande", {"commande": "docker-compose -f docker-compose.registry.yml up -d"}),
        ],
        ["write_code", "executer_commande"],
        "Registry Docker privé"
    ),
]

MONITORING_EXAMPLES = [
    make_example(
        "Installe Prometheus + Grafana",
        "Je vais installer Prometheus et Grafana pour le monitoring.",
        [
            ("write_code", {
                "path": "docker-compose.monitoring.yml",
                "old": "",
                "new": "version: '3.8'\nservices:\n  prometheus:\n    image: prom/prometheus\n    ports:\n      - '9090:9090'\n    volumes:\n      - ./prometheus.yml:/etc/prometheus/prometheus.yml\n\n  grafana:\n    image: grafana/grafana\n    ports:\n      - '3000:3000'\n    environment:\n      GF_SECURITY_ADMIN_PASSWORD: admin\n    volumes:\n      - grafana_data:/var/lib/grafana\n\nvolumes:\n  grafana_data:"
            }),
            ("write_code", {
                "path": "prometheus.yml",
                "old": "",
                "new": "global:\n  scrape_interval: 15s\n\nscrape_configs:\n  - job_name: 'prometheus'\n    static_configs:\n      - targets: ['localhost:9090']"
            }),
            ("executer_commande", {"commande": "docker-compose -f docker-compose.monitoring.yml up -d"}),
        ],
        ["write_code", "executer_commande"],
        "Monitoring Prometheus + Grafana"
    ),

    make_example(
        "Installe ELK Stack (Elasticsearch + Logstash + Kibana)",
        "Je vais installer ELK pour la gestion des logs.",
        [
            ("write_code", {
                "path": "docker-compose.elk.yml",
                "old": "",
                "new": "version: '3.8'\nservices:\n  elasticsearch:\n    image: elasticsearch:8.12.0\n    environment:\n      - discovery.type=single-node\n      - xpack.security.enabled=false\n    ports:\n      - '9200:9200'\n    volumes:\n      - es_data:/usr/share/elasticsearch/data\n\n  kibana:\n    image: kibana:8.12.0\n    ports:\n      - '5601:5601'\n    depends_on:\n      - elasticsearch\n\nvolumes:\n  es_data:"
            }),
            ("executer_commande", {"commande": "docker-compose -f docker-compose.elk.yml up -d"}),
        ],
        ["write_code", "executer_commande"],
        "ELK Stack"
    ),

    make_example(
        "Configure un health check pour mon conteneur",
        "Je vais ajouter un health check à ton Dockerfile.",
        [
            ("write_code", {
                "path": "Dockerfile",
                "old": "EXPOSE 3000",
                "new": "EXPOSE 3000\nHEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\\n  CMD curl -f http://localhost:3000/health || exit 1"
            }),
        ],
        ["write_code"],
        "Health check Docker"
    ),
]

INFRA_EXAMPLES = [
    make_example(
        "Crée un script d'installation serveur Ubuntu",
        "Je vais créer un script d'automatisation de setup serveur.",
        [
            ("write_code", {
                "path": "setup-server.sh",
                "old": "",
                "new": "#!/bin/bash\nset -euo pipefail\n\n# Mise à jour système\nsudo apt update && sudo apt upgrade -y\n\n# Installation outils de base\nsudo apt install -y curl wget git htop tmux unzip\n\n# Installation Docker\nsudo apt install -y docker.io docker-compose\nsudo systemctl enable docker\n\n# Installation Node.js\ncurl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -\nsudo apt install -y nodejs\n\n# Configuration firewall\nsudo ufw allow 22/tcp\nsudo ufw allow 80/tcp\nsudo ufw allow 443/tcp\nsudo ufw enable\n\necho \"Setup terminé !\""
            }),
            ("executer_commande", {"commande": "chmod +x setup-server.sh"}),
        ],
        ["write_code", "executer_commande"],
        "Script setup serveur"
    ),

    make_example(
        "Configure Nginx comme reverse proxy",
        "Je vais configurer Nginx comme reverse proxy.",
        [
            ("write_code", {
                "path": "nginx.conf",
                "old": "",
                "new": "server {\n    listen 80;\n    server_name monsite.com;\n\n    location / {\n        proxy_pass http://localhost:3000;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n    }\n\n    location /static {\n        alias /var/www/static;\n        expires 30d;\n    }\n}"
            }),
            ("executer_commande", {"commande": "sudo cp nginx.conf /etc/nginx/sites-available/monsite"}),
            ("executer_commande", {"commande": "sudo ln -sf /etc/nginx/sites-available/monsite /etc/nginx/sites-enabled/"}),
            ("executer_commande", {"commande": "sudo nginx -t && sudo systemctl reload nginx"}),
        ],
        ["write_code", "executer_commande"],
        "Configuration Nginx reverse proxy"
    ),

    make_example(
        "Configure SSL/TLS avec Let's Encrypt",
        "Je vais installer certbot et configurer SSL.",
        [
            ("executer_commande", {"commande": "sudo apt install -y certbot python3-certbot-nginx"}),
            ("executer_commande", {"commande": "sudo certbot --nginx -d monsite.com -d www.monsite.com"}),
            ("executer_commande", {"commande": "sudo certbot renew --dry-run"}),
        ],
        ["executer_commande"],
        "SSL Let's Encrypt"
    ),

    make_example(
        "Crée un script de backup automatique",
        "Je vais créer un script de backup de ta base de données.",
        [
            ("write_code", {
                "path": "backup.sh",
                "old": "",
                "new": "#!/bin/bash\nset -euo pipefail\n\nDATE=$(date +%Y%m%d_%H%M%S)\nBACKUP_DIR=\"/backups\"\nDB_NAME=\"mydb\"\n\nmkdir -p $BACKUP_DIR\n\n# Backup PostgreSQL\ndocker exec -t db pg_dump -U admin $DB_NAME | gzip > $BACKUP_DIR/${DB_NAME}_${DATE}.sql.gz\n\n# Supprimer les backups de plus de 30 jours\nfind $BACKUP_DIR -name \"*.sql.gz\" -mtime +30 -delete\n\necho \"Backup terminé : ${DB_NAME}_${DATE}.sql.gz\""
            }),
            ("executer_commande", {"commande": "chmod +x backup.sh"}),
            ("executer_commande", {"commande": "echo '0 2 * * * /home/user/backup.sh' | crontab -"}),
        ],
        ["write_code", "executer_commande"],
        "Script backup automatique"
    ),
]

SECURITY_EXAMPLES = [
    make_example(
        "Scanne les vulnérabilités de mon image Docker",
        "Je vais scanner l'image avec Trivy.",
        [
            ("executer_commande", {"commande": "docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image mon-app:latest"}),
        ],
        ["executer_commande"],
        "Scan sécurité Docker"
    ),

    make_example(
        "Installe Fail2Ban pour sécuriser SSH",
        "Je vais installer et configurer Fail2Ban.",
        [
            ("executer_commande", {"commande": "sudo apt install -y fail2ban"}),
            ("write_code", {
                "path": "/etc/fail2ban/jail.local",
                "old": "",
                "new": "[DEFAULT]\nbantime = 3600\nfindtime = 600\nmaxretry = 5\n\n[sshd]\nenabled = true\nport = ssh\nfilter = sshd\nlogpath = /var/log/auth.log\nmaxretry = 3"
            }),
            ("executer_commande", {"commande": "sudo systemctl restart fail2ban"}),
        ],
        ["executer_commande", "write_code"],
        "Fail2Ban SSH"
    ),
]


def train():
    print("Phase 7 : Entrainement DevOps")
    print("=" * 60)

    existing = load_examples()
    print(f"Exemples existants : {len(existing)}")

    new_examples = (
        DOCKER_EXAMPLES + K8S_EXAMPLES + CICD_EXAMPLES +
        MONITORING_EXAMPLES + INFRA_EXAMPLES + SECURITY_EXAMPLES
    )
    existing.extend(new_examples)
    save_examples(existing)

    print(f"Nouveaux exemples : {len(new_examples)}")
    print(f"Total : {len(existing)}")
    print(f"\nDetail :")
    print(f"  - Docker : {len(DOCKER_EXAMPLES)} exemples")
    print(f"    - Installation, conteneurs, Dockerfile, Compose, reseaux")
    print(f"  - Kubernetes : {len(K8S_EXAMPLES)} exemples")
    print(f"    - kubectl, deployments, services, scaling, logs")
    print(f"  - CI/CD : {len(CICD_EXAMPLES)} exemples")
    print(f"    - GitHub Actions, Jenkins, Dockerfile multi-stage, registry")
    print(f"  - Monitoring : {len(MONITORING_EXAMPLES)} exemples")
    print(f"    - Prometheus, Grafana, ELK, health checks")
    print(f"  - Infrastructure : {len(INFRA_EXAMPLES)} exemples")
    print(f"    - Setup serveur, Nginx, SSL, backups")
    print(f"  - Securite : {len(SECURITY_EXAMPLES)} exemples")
    print(f"    - Scan Docker, Fail2Ban")
    print("\nAlex peut maintenant :")
    print("  - Gerer Docker (conteneurs, images, compose, reseaux)")
    print("  - Deployer sur Kubernetes (manifests, scaling, logs)")
    print("  - Configurer du CI/CD (GitHub Actions, Jenkins)")
    print("  - Mettre en place du monitoring (Prometheus, Grafana, ELK)")
    print("  - Administrer des serveurs (Nginx, SSL, backups)")
    print("  - Securiser les infrastructures (scan, Fail2Ban)")
    print("\nTermine !")


if __name__ == "__main__":
    train()
