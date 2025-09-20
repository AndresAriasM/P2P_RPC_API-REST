from pathlib import Path
from typing import List, Dict

def list_files(shared_dir: str) -> list[dict]:
    p = Path(shared_dir)
    files: List[Dict] = []
    if not p.exists():
        return files
    for f in p.iterdir():
        if f.is_file():
            stat = f.stat()
            files.append({
                "name": f.name,
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
            })
    return files
