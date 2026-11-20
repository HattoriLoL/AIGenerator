#!/usr/bin/env python3
"""Procura segredos no que vai subir para o GitHub (usado pelo gancho .githooks/pre-push; só a biblioteca padrão).

    python3 bin/verificar_segredos.py                    # os commits do branch atual que o main não tem
    python3 bin/verificar_segredos.py --base dev         # contra outro branch
    python3 bin/verificar_segredos.py --revs "B --not --remotes=origin"   # os commits que o remoto ainda não tem
Cada commit é lido sozinho (um segredo posto e tirado no mesmo push também aparece).
    python3 bin/verificar_segredos.py --all              # todo arquivo versionado (auditoria)

Código de saída: 0 nada que barre; 1 achou algo que não pode subir; 2 erro de uso. Os avisos (caminhos pessoais,
e-mails) não barram. O valor de um segredo nunca é impresso inteiro. Se o gitleaks estiver instalado, roda também.

Falso positivo numa linha: depois de conferir que não é segredo, ponha o texto `scan-secrets: ok` nessa linha
(num comentário; num .json, dentro de uma string) e refaça o commit que a trouxe (`git commit --amend`, se for o
último; senão, um rebase que edite aquele commit). Um commit novo por cima não basta: cada commit é lido sozinho.
O marcador não vale para um arquivo barrado pelo nome nem para o gitleaks (que tem o seu, `gitleaks:allow`). Nunca
suba com --no-verify.
"""
import argparse
import fnmatch
import os
import re
import shutil
import subprocess
import sys

# Nomes de arquivo que não podem ser versionados (comparados com o nome em minúsculas).
ARQUIVOS_PROIBIDOS = [
    ".env", ".env.*", "*.env", "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore", "*.jks", "*.kdbx",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials", "credentials.json", "credentials.*",
    "secrets.*", "secret.*", "config.local.*", "*.local.ini", "*.local.json", "*.local.toml",
    ".netrc", ".npmrc", ".pypirc", "token", "token.txt", "*.token", "service-account*.json",
    "client_secret*.json", ".htpasswd", ".aigen-proibidos", "claude.local.md",
    # pesos de modelos e o que o AIGenerator gera: nunca vão para o repositório (AGENTS.md, "Public repository")
    "*.safetensors", "*.ckpt", "*.pt", "*.pth", "*.onnx", "*.gguf",
    "*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif", "*.bmp", "*.avif",
    "*.aigen.json", "aigen-web.log",
]
ARQUIVOS_PERMITIDOS = [".env.example", ".env.sample", ".env.template", "example.env"]

# (nome, padrão). O grupo 1, quando existe, é o valor.
BARRA = [
    ("chave privada", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY")),
    ("chave da Anthropic", re.compile(r"\b(sk-ant-[A-Za-z0-9_\-]{20,})")),
    ("chave da OpenAI", re.compile(r"\b(sk-(?!ant-)(?:proj-)?[A-Za-z0-9_\-]{32,})")),
    ("token do GitHub", re.compile(r"\b((?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("token do Hugging Face", re.compile(r"\b(hf_[A-Za-z0-9]{30,})")),
    ("token do Civitai", re.compile(r"(?i)\bcivitai\w*\s*[\"']?\s*[:=]\s*[\"']?([0-9a-f]{32})\b")),
    ("chave da AWS", re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b")),
    ("chave do Google", re.compile(r"\b(AIza[0-9A-Za-z_\-]{35})")),
    ("token do Slack", re.compile(r"\b(xox[abprs]-[A-Za-z0-9\-]{10,})")),
    ("token do Discord", re.compile(r"\b([MN][A-Za-z\d]{23,25}\.[\w-]{6}\.[\w-]{27,})")),
    ("chave do Stripe", re.compile(r"\b((?:sk|rk)_live_[A-Za-z0-9]{20,})")),
    ("JWT", re.compile(r"\b(eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})")),
    ("senha numa URL", re.compile(r"[a-z][a-z0-9+.\-]*://[^\s:/@]+:([^\s:/@]{6,})@")),
    ("segredo atribuído", re.compile(
        r"(?i)\b(?:api[_\-]?key|apikey|secret|token|passwd|password|senha|client[_\-]?secret|access[_\-]?key|"
        r"auth[_\-]?token|private[_\-]?key)\w*\s*[\"']?\s*[:=]\s*[\"']([^\"'\s]{12,})[\"']")),
]
AVISA = [
    ("caminho pessoal", re.compile(r"(?i)(?:[A-Z]:[\\/]+Users[\\/]+|/c/Users/|/(?:home|Users)/)([A-Za-z0-9._\-]+)")),
    ("e-mail", re.compile(r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")),
]
EMAILS_OK = ("noreply", "example.", "@users.noreply", "git@")
USUARIOS_OK = {"user", "usuario", "usuário", "nome", "you", "name", "runner", "username"}
BINARIOS = (".png", ".jpg", ".jpeg", ".webp", ".exr", ".glb", ".gltf", ".bin", ".blend", ".ico", ".svg", ".zip",
            ".npz", ".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".gguf", ".ttf", ".otf", ".woff", ".woff2",
            ".mp3", ".wav", ".ogg", ".mp4", ".pdf", ".exe", ".dll", ".so")
LIBERA = "scan-secrets: ok"  # comentário numa linha: um falso positivo conferido



def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print("ERRO: git %s: %s" % (" ".join(args), r.stderr.strip()), file=sys.stderr)
        sys.exit(2)
    return r.stdout


def mascarar(value):
    value = value.strip()
    return (value[:6] + "…" + value[-2:]) if len(value) > 12 else "…"


def e_marcador(value, line):
    """Um exemplo ou um marcador, não um segredo de verdade."""
    v = value.lower()
    if any(m in value for m in ("…", "...", "<", ">", "${", "{{", "%(", "$(")) or v.startswith("$"):
        return True
    if any(p in v for p in ("xxxx", "example", "exemplo", "your", "sua_", "seu_", "changeme", "placeholder", "dummy",
                            "fake", "os.environ", "getenv", "process.env")):
        return True
    if len(set(value)) < 6:  # aaaaaaaa, 12121212
        return True
    return LIBERA in line


def e_proibido(path):
    name = os.path.basename(path).lower()
    if name in ARQUIVOS_PERMITIDOS:
        return False
    return any(fnmatch.fnmatch(name, p) for p in ARQUIVOS_PROIBIDOS)


GIT_DIFF = ["-c", "core.quotePath=false"]  # nomes com acento como estão (sem aspas nem \\303)
DIFF = ["--no-color", "--unified=0", "--no-ext-diff", "--src-prefix=a/", "--dst-prefix=b/", "--no-renames"]


def commits(revs):
    """Os commits de `revs` (argumentos do git rev-list, por exemplo "A..B" ou "B --not --remotes=origin")."""
    return git("rev-list", *revs.split()).split()


def linhas_acrescentadas(lista):
    """(arquivo, número da linha, texto) das linhas acrescentadas em cada commit (um por um: um segredo posto num
    commit e tirado no seguinte também aparece)."""
    for c in lista:
        path, n, no_trecho = None, 0, False
        for line in git(*GIT_DIFF, "show", "--format=", *DIFF, c).splitlines():
            if line.startswith("diff --git "):
                path, no_trecho = None, False
            elif not no_trecho and line.startswith("+++ "):
                path = line[6:] if line.startswith("+++ b/") else None
            elif line.startswith("@@"):
                no_trecho = True
                m = re.search(r"\+(\d+)", line)
                n = int(m.group(1)) if m else 0
            elif no_trecho and line.startswith("+"):
                if path:
                    yield path, n, line[1:]
                n += 1


def arquivos_acrescentados(lista):
    nomes = set()
    for c in lista:
        nomes.update(git(*GIT_DIFF, "show", "--format=", "--name-only", "--diff-filter=AMR", "--no-renames", c).split("\n"))
    return sorted(x for x in nomes if x)


def todas_as_linhas():
    for path in git("ls-files").splitlines():
        if path.lower().endswith(BINARIOS) or not os.path.isfile(path) or os.path.getsize(path) > 2_000_000:
            continue
        try:
            with open(path, encoding="utf-8", errors="strict") as f:
                for n, line in enumerate(f, 1):
                    yield path, n, line.rstrip("\n")
        except (UnicodeDecodeError, OSError):
            continue


def base_padrao():
    for b in ("origin/main", "origin/master", "main", "master"):
        if subprocess.run(["git", "rev-parse", "--verify", "-q", b], capture_output=True).returncode == 0:
            return b
    print("ERRO: não achei o branch principal; use --base", file=sys.stderr)
    sys.exit(2)


def procurar(arquivos, linhas):
    """(o que barra, avisos)."""
    barrados, avisos = [], {}
    for path in arquivos:
        if e_proibido(path):
            barrados.append("%s: arquivo que não pode ser versionado" % path)
    for path, n, text in linhas:
        if path.lower().endswith(BINARIOS) or len(text) > 500_000:
            continue
        vistos = set()
        for name, rx in BARRA:
            for m in rx.finditer(text):
                value = m.group(1) if m.groups() else m.group(0)
                if value in vistos or e_marcador(value, text):
                    continue
                vistos.add(value)
                barrados.append("%s:%d: %s (%s)" % (path, n, name, mascarar(value)))
        for name, rx in AVISA:
            for m in rx.finditer(text):
                v = m.group(1)
                if name == "e-mail" and any(k in v.lower() for k in EMAILS_OK):
                    continue
                if name == "caminho pessoal" and v.lower() in USUARIOS_OK:
                    continue
                avisos.setdefault((name, v), []).append("%s:%d" % (path, n))
    return barrados, avisos


def main():
    p = argparse.ArgumentParser(description="Procura segredos no que vai subir para o GitHub.")
    p.add_argument("--base", help="o branch de comparação (padrão: origin/main)")
    p.add_argument("--revs", help="os commits a ler, como argumentos do git rev-list (\"A..B\" ou \"B --not --remotes=origin\")")
    p.add_argument("--all", action="store_true", help="todo arquivo versionado, não só o que vai subir")
    a = p.parse_args()
    if subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True).returncode != 0:
        print("ERRO: não é um repositório git", file=sys.stderr)
        sys.exit(2)
    os.chdir(git("rev-parse", "--show-toplevel").strip())
    if a.all:
        intervalo, arquivos, linhas, escopo = None, git("ls-files").splitlines(), todas_as_linhas(), "todos os arquivos"
    else:
        intervalo = a.revs or (a.base or base_padrao()) + "..HEAD"
        lista = commits(intervalo)
        arquivos = arquivos_acrescentados(lista)
        linhas, escopo = linhas_acrescentadas(lista), "%s (%d commits, %d arquivos)" % (intervalo, len(lista), len(arquivos))
    barrados, avisos = procurar(arquivos, linhas)
    if shutil.which("gitleaks"):
        cmd = ["gitleaks", "detect", "--no-banner", "--redact", "--exit-code", "1"]
        if intervalo:
            cmd += ["--log-opts", intervalo]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 1:
            barrados.append("o gitleaks achou segredos:\n" + (r.stdout + r.stderr).strip())
    print("verificar_segredos: " + escopo)
    for (name, v), onde in sorted(avisos.items()):
        print("  aviso: %s '%s' em %d lugar(es): %s%s" % (name, v, len(onde), ", ".join(onde[:3]),
                                                         " ..." if len(onde) > 3 else ""))
    if barrados:
        print("BARRADO: %d achado(s) que não podem subir:" % len(barrados))
        for b in barrados:
            print("  - " + b)
        if any(re.match(r".+:\d+: ", b) for b in barrados):  # achado numa linha (não pelo nome nem do gitleaks)
            print("Falso positivo numa linha (conferido)? Ponha '%s' nela e refaça o commit que a trouxe (git commit"
                  " --amend, se for o último): um commit novo por cima não basta." % LIBERA)
        sys.exit(1)
    print("ok: nenhum segredo" + (" (%d aviso(s))" % len(avisos) if avisos else ""))


if __name__ == "__main__":
    main()
