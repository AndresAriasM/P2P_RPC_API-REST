import hashlib
from pathlib import Path
from typing import List, Dict

def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file"""
    try:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()[:16]  # First 16 chars for brevity
    except Exception:
        return ""

def list_files(shared_dir: str) -> List[Dict]:
    """List files with enhanced metadata including checksums"""
    p = Path(shared_dir)
    files: List[Dict] = []
    
    if not p.exists():
        return files
    
    for f in p.iterdir():
        if f.is_file():
            try:
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime),
                    "checksum": calculate_checksum(f),
                    "extension": f.suffix.lower(),
                    "type": _get_file_type(f.suffix.lower())
                })
            except Exception:
                # Skip files that can't be read
                continue
    
    return sorted(files, key=lambda x: x["name"])

def _get_file_type(extension: str) -> str:
    """Categorize file by extension"""
    text_ext = {".txt", ".md", ".log", ".json", ".xml", ".csv"}
    image_ext = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg"}
    video_ext = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"}
    audio_ext = {".mp3", ".wav", ".flac", ".aac", ".ogg"}
    doc_ext = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}
    code_ext = {".py", ".js", ".java", ".cpp", ".c", ".h", ".go", ".rs"}
    
    if extension in text_ext:
        return "text"
    elif extension in image_ext:
        return "image"
    elif extension in video_ext:
        return "video"
    elif extension in audio_ext:
        return "audio"
    elif extension in doc_ext:
        return "document"
    elif extension in code_ext:
        return "code"
    else:
        return "other"