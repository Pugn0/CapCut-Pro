import http.server
import socketserver
import json
import os
import re
import webbrowser
import urllib.parse
import shutil
import subprocess
import hashlib
from pathlib import Path

# -----------------------------
# CONFIGURAÇÕES
# -----------------------------
PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPCUT_PATH = r"C:\Users\pugno\Videos\CapCut\CapCut Drafts"
CACHE_DIR = os.path.join(BASE_DIR, ".thumb_cache")
VIDEO_PATTERN = re.compile(r".*(_video|_\d+_\d+)\.mp4$", re.IGNORECASE)

THUMB_PATTERN = re.compile(r".*_cover\.jpg$", re.IGNORECASE)

os.chdir(BASE_DIR)

# Cria pasta de cache
os.makedirs(CACHE_DIR, exist_ok=True)


# -----------------------------
# FUNÇÕES AUXILIARES
# -----------------------------
def gerar_thumbnail(video_path):
    """Gera thumbnail do vídeo usando ffmpeg (se disponível) ou retorna None"""
    # Cria hash do caminho do vídeo para nome único
    hash_name = hashlib.md5(video_path.encode()).hexdigest()
    thumb_path = os.path.join(CACHE_DIR, f"{hash_name}.jpg")
    
    # Se já existe em cache, retorna
    if os.path.exists(thumb_path):
        return thumb_path
    
    # Tenta gerar com ffmpeg
    try:
        # Verifica se ffmpeg está disponível
        subprocess.run(["ffmpeg", "-version"], 
                      capture_output=True, 
                      check=True,
                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        
        # Gera thumbnail do segundo 1
        subprocess.run([
            "ffmpeg",
            "-i", video_path,
            "-ss", "00:00:01",
            "-vframes", "1",
            "-q:v", "2",
            thumb_path
        ], capture_output=True, check=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        
        if os.path.exists(thumb_path):
            return thumb_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        # ffmpeg não disponível ou erro ao gerar
        pass
    
    return None


def listar_videos():
    resultados = []
    pastas_com_video = set()

    if not os.path.exists(CAPCUT_PATH):
        return {"erro": f"Pasta não encontrada: {CAPCUT_PATH}"}

    for subdir in sorted(os.listdir(CAPCUT_PATH)):
        # Caminhos possíveis onde o CapCut salva vídeos
        search_paths = [
            os.path.join(CAPCUT_PATH, subdir, "Resources", "videoAlg"),
            os.path.join(CAPCUT_PATH, subdir, "Resources", "combination")
        ]

        for comb_path in search_paths:
            if not os.path.exists(comb_path):
                continue

            thumb_path = None

            # Procura por _cover.jpg primeiro
            for file in os.listdir(comb_path):
                if THUMB_PATTERN.match(file):
                    thumb_path = os.path.join(comb_path, file)
                    break

            for file in os.listdir(comb_path):
                if VIDEO_PATTERN.match(file):
                    pastas_com_video.add(subdir)
                    video_path = os.path.join(comb_path, file)

                    # Se não tem _cover.jpg, tenta gerar thumbnail
                    if not thumb_path:
                        thumb_path = gerar_thumbnail(video_path)

                    resultados.append({
                        "pasta": subdir,
                        "arquivo": file,
                        "caminho": video_path,
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
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        return super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_video_response(self, video_path):
        """Envia vídeo com suporte a Range Requests"""
        if not os.path.exists(video_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Arquivo nao encontrado")
            return

        file_size = os.path.getsize(video_path)
        range_header = self.headers.get('Range')

        if range_header:
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                start = int(range_match.group(1))
                end = range_match.group(2)
                end = int(end) if end else file_size - 1
                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                with open(video_path, "rb") as f:
                    f.seek(start)
                    self.wfile.write(f.read(length))
                return

        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

        with open(video_path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/videos":
            data = listar_videos()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
            return

        if path == "/api/preview":
            video_path = query.get("path", [""])[0]
            video_path = urllib.parse.unquote(video_path)
            self.send_video_response(video_path)
            return

        if path == "/api/download":
            video_path = query.get("path", [""])[0]
            video_path = urllib.parse.unquote(video_path)
            self.send_video_response(video_path)
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
        print(f"📂 CapCut Drafts: {CAPCUT_PATH}")
        print(f"💾 Cache de thumbnails: {CACHE_DIR}")
        
        # Verifica se ffmpeg está disponível
        try:
            subprocess.run(["ffmpeg", "-version"], 
                          capture_output=True, 
                          check=True,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            print("✅ FFmpeg detectado - thumbnails serão geradas automaticamente")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  FFmpeg não encontrado - usando apenas _cover.jpg existentes")
            print("   Instale FFmpeg para gerar thumbnails: https://ffmpeg.org/download.html")
        
        webbrowser.open(url)
        httpd.serve_forever()