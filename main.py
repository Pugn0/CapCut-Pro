import http.server
import socketserver
import json
import os
import re
import webbrowser
import urllib.parse
import shutil

# -----------------------------
# CONFIGURAÇÕES
# -----------------------------
PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPCUT_PATH = r"C:\Users\pugno\Videos\CapCut\CapCut Drafts"
VIDEO_PATTERN = re.compile(r".*_video\.mp4$", re.IGNORECASE)
THUMB_PATTERN = re.compile(r".*_cover\.jpg$", re.IGNORECASE)

os.chdir(BASE_DIR)


# -----------------------------
# FUNÇÕES AUXILIARES
# -----------------------------
def listar_videos():
    resultados = []
    pastas_com_video = set()

    if not os.path.exists(CAPCUT_PATH):
        return {"erro": f"Pasta não encontrada: {CAPCUT_PATH}"}

    for subdir in sorted(os.listdir(CAPCUT_PATH)):
        comb_path = os.path.join(CAPCUT_PATH, subdir, "Resources", "combination")
        if os.path.exists(comb_path):
            thumb_path = None
            for file in os.listdir(comb_path):
                if THUMB_PATTERN.match(file):
                    thumb_path = os.path.join(comb_path, file)
                    break  # usa a primeira arte encontrada

            for file in os.listdir(comb_path):
                if VIDEO_PATTERN.match(file):
                    pastas_com_video.add(subdir)
                    resultados.append({
                        "pasta": subdir,
                        "arquivo": file,
                        "caminho": os.path.join(comb_path, file),
                        "thumb": thumb_path
                    })
    return {
        "videos": resultados,
        "total": len(resultados),
        "pastas": len(pastas_com_video)
    }


def excluir_pasta(pasta_nome):
    pasta_completa = os.path.join(CAPCUT_PATH, pasta_nome)
    if os.path.exists(pasta_completa):
        shutil.rmtree(pasta_completa, ignore_errors=True)
        return {"ok": True, "mensagem": f"Pasta {pasta_nome} excluída com sucesso."}
    else:
        return {"ok": False, "erro": f"Pasta {pasta_nome} não encontrada."}


# -----------------------------
# HANDLER DO SERVIDOR
# -----------------------------
class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        return super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/videos":
            data = listar_videos()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
            return

        if path == "/api/download":
            video_path = query.get("path", [""])[0]
            video_path = urllib.parse.unquote(video_path)

            if not os.path.exists(video_path):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Arquivo nao encontrado")
                return

            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(video_path)}"')
            self.end_headers()
            with open(video_path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return

        if path == "/api/thumb":
            thumb_path = query.get("path", [""])[0]
            thumb_path = urllib.parse.unquote(thumb_path)
            if not os.path.exists(thumb_path):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Thumbnail nao encontrada")
                return

            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            with open(thumb_path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return

        if path == "/" or path == "/index.html":
            self.path = "/index.html"

        return super().do_GET()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/delete":
            query = urllib.parse.parse_qs(parsed.query)
            pasta = query.get("folder", [""])[0]
            pasta = urllib.parse.unquote(pasta)

            result = excluir_pasta(pasta)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


# -----------------------------
# EXECUÇÃO DO SERVIDOR
# -----------------------------
if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}/index.html"
        print(f"🚀 Servidor rodando em {url}")
        print(f"📁 CapCut Drafts: {CAPCUT_PATH}")
        webbrowser.open(url)
        httpd.serve_forever()
