"""P2P Client CLI — REST (FastAPI) + gRPC

Este cliente de línea de comandos permite:
  - Buscar archivos en la red P2P vía REST (`/search`) con fanout.
  - Descargar archivos simulados (ECO/DUMMY) vía gRPC (stream de chunks).
  - Subir carga simulada vía gRPC (stream de chunks).
  - Consultar el estado detallado de un peer (`/status`).

Uso típico:
  python client.py --search ".txt" --fanout 3 --base http://localhost:8001
  python client.py --download hello1.txt --grpc-host localhost --grpc-port 50051
  python client.py --upload-mb 10 --grpc-host localhost --grpc-port 50051
  python client.py --status --base http://localhost:8001

Requisitos:
  - El peer de destino debe tener su API REST y servidor gRPC corriendo.
  - Los stubs gRPC generados desde filetransfer.proto deben estar en `peer/protos/`.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import AsyncGenerator, Optional

import httpx
import grpc
import sys
import os

# Asegura que /app esté en sys.path cuando se ejecuta dentro del contenedor
sys.path.append("/app")

# Stubs gRPC: se intentan importar; si fallan, se deshabilita funcionalidad gRPC
try:
    from peer.protos import filetransfer_pb2 as pb2
    from peer.protos import filetransfer_pb2_grpc as pb2_grpc
except ImportError as e:  # pragma: no cover - entorno sin stubs compilados
    print(f"[WARN] gRPC imports failed: {e}")
    print("[WARN] gRPC functionality will not be available. "
          "Ejecuta `bash generate_proto.sh` para generar los stubs.")
    pb2 = None
    pb2_grpc = None


async def do_search(base_url: str, query: str, fanout: int = 3) -> None:
    """Realiza una búsqueda distribuida vía REST y muestra resultados.

    Args:
        base_url: URL base del peer (ej. "http://localhost:8001").
        query: Patrón de búsqueda (nombre, extensión, etc.).
        fanout: Número máximo de peers a contactar desde el peer inicial.

    Efectos:
        Imprime tiempos, parámetros usados y el listado de archivos por peer,
        incluyendo tamaño, tipo y prefijo del checksum.

    Notas:
        - Usa timeout de 30s para la llamada HTTP.
        - Requiere que el peer implemente `GET /search?query&fanout`.
    """
    start_time = time.time()

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(
                f"{base_url}/search", params={"query": query, "fanout": fanout}
            )
            response.raise_for_status()
            data = response.json()

            duration = time.time() - start_time
            print(f"Search completed in {duration:.2f}s")
            print(f"Query: {data.get('query', 'N/A')}")
            print(f"Fanout used: {data.get('fanout_used', 'N/A')}\n")

            total_files = 0
            for result in data.get("results", []):
                peer = result.get("peer", "unknown")
                files = result.get("files", [])
                cached = " (cached)" if result.get("cached") else ""
                print(f"Peer: {peer}{cached}")
                if files:
                    for file in files:
                        size_mb = file.get("size", 0) / 1024 / 1024
                        file_type = file.get("type", "unknown")
                        checksum = file.get("checksum", "")[:8]
                        print(
                            f"  - {file['name']} "
                            f"({size_mb:.2f}MB, {file_type}, {checksum})"
                        )
                        total_files += 1
                else:
                    print("  No matching files")
                print()

            print(f"Total files found: {total_files}")

        except httpx.HTTPError as e:
            print(f"[HTTP] error: {e}")
        except Exception as e:  # pragma: no cover - fallback genérico
            print(f"[ERROR] {e}")


async def do_download(host: str, port: int, filename: str) -> None:
    """Descarga simulada (ECO/DUMMY) vía gRPC con seguimiento de progreso.

    Args:
        host: Host/IP del servidor gRPC.
        port: Puerto gRPC (ej. 50051).
        filename: Nombre del archivo a solicitar.

    Efectos:
        Imprime # de chunks, tamaño recibido, duración y velocidad estimada.

    Requisitos:
        - Stubs gRPC disponibles (`pb2`, `pb2_grpc`).
        - El servidor gRPC implementa `DummyDownload`.
    """
    if not pb2 or not pb2_grpc:
        print("[ERROR] gRPC modules not available. Genera stubs con `generate_proto.sh`.")
        return

    start_time = time.time()

    try:
        channel = grpc.aio.insecure_channel(f"{host}:{port}")
        stub = pb2_grpc.FileTransferStub(channel)

        chunks_received = 0
        total_bytes = 0

        print(f"Downloading {filename} from {host}:{port}...")

        # Descarga por streaming; cada `chunk` contiene bytes del archivo
        async for chunk in stub.DummyDownload(pb2.FileRequest(filename=filename)):
            chunks_received += 1
            total_bytes += len(chunk.data)

            # Indicador de progreso para archivos grandes
            if chunks_received % 100 == 0:
                print(
                    f"  Received {chunks_received} chunks, "
                    f"{total_bytes / 1024 / 1024:.2f}MB"
                )

        duration = time.time() - start_time
        speed_mbps = (total_bytes / 1024 / 1024) / duration if duration > 0 else 0.0

        print("Download completed:")
        print(f"  Chunks: {chunks_received}")
        print(f"  Size: {total_bytes / 1024 / 1024:.2f}MB")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Speed: {speed_mbps:.2f}MB/s")

        await channel.close()

    except grpc.RpcError as e:
        print(f"[gRPC] {e.code()} - {e.details()}")
    except Exception as e:  # pragma: no cover - fallback genérico
        print(f"[ERROR] {e}")


async def do_upload(host: str, port: int, size_bytes: int) -> None:
    """Subida simulada (ECO/DUMMY) vía gRPC con seguimiento de progreso.

    Args:
        host: Host/IP del servidor gRPC.
        port: Puerto gRPC (ej. 50051).
        size_bytes: Tamaño total a subir en bytes (se generan datos dummy).

    Efectos:
        Imprime # de chunks enviados, bytes recibidos por el servidor, duración y velocidad.

    Requisitos:
        - Stubs gRPC disponibles (`pb2`, `pb2_grpc`).
        - El servidor gRPC implementa `DummyUpload` (stream de entrada).
    """
    if not pb2 or not pb2_grpc:
        print("[ERROR] gRPC modules not available. Genera stubs con `generate_proto.sh`.")
        return

    start_time = time.time()

    try:
        channel = grpc.aio.insecure_channel(f"{host}:{port}")
        stub = pb2_grpc.FileTransferStub(channel)

        print(f"Uploading {size_bytes / 1024 / 1024:.2f}MB to {host}:{port}...")

        async def chunk_generator() -> AsyncGenerator[pb2.FileChunk, None]:
            """Genera chunks de 64KB hasta alcanzar `size_bytes`.

            Yields:
                FileChunk: Secuencias numeradas con payload dummy (bytes "x").
            """
            sent_bytes = 0
            seq = 0
            chunk_size = 65536  # 64KB
            payload = b"x" * chunk_size

            while sent_bytes < size_bytes:
                seq += 1
                remaining = size_bytes - sent_bytes
                chunk_data = payload[: min(chunk_size, remaining)]
                sent_bytes += len(chunk_data)

                if seq % 100 == 0:
                    progress = (sent_bytes / size_bytes) * 100
                    print(
                        f"  Progress: {progress:.1f}% "
                        f"({sent_bytes / 1024 / 1024:.2f}MB)"
                    )

                yield pb2.FileChunk(data=chunk_data, seq=seq)

        response = await stub.DummyUpload(chunk_generator())

        duration = time.time() - start_time
        speed_mbps = (
            (response.received_bytes / 1024 / 1024) / duration if duration > 0 else 0.0
        )

        print("Upload completed:")
        print(f"  Chunks sent: {response.chunks}")
        print(f"  Bytes received by server: {response.received_bytes / 1024 / 1024:.2f}MB")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Speed: {speed_mbps:.2f}MB/s")

        await channel.close()

    except grpc.RpcError as e:
        print(f"[gRPC] {e.code()} - {e.details()}")
    except Exception as e:  # pragma: no cover - fallback genérico
        print(f"[ERROR] {e}")


async def do_status(base_url: str) -> None:
    """Consulta `/status` en el peer y muestra configuración, estadísticas y peers saludables.

    Args:
        base_url: URL base del peer (ej. "http://localhost:8001").

    Efectos:
        Imprime configuración cargada, métricas básicas y lista de peers saludables.

    Notas:
        - Útil para verificar bootstrap, health-checks y topología actual.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(f"{base_url}/status")
            response.raise_for_status()
            data = response.json()

            print(f"Peer Status: {data.get('peer', 'unknown')}")
            print(f"URL: {data.get('url', 'unknown')}\n")

            config = data.get("config", {})
            print("Configuration:")
            for key, value in config.items():
                print(f"  {key}: {value}")
            print()

            stats = data.get("stats", {})
            print("Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
            print()

            healthy_peers = data.get("healthy_peers", [])
            print(f"Healthy peers ({len(healthy_peers)}):")
            for peer in healthy_peers:
                print(f"  - {peer}")

        except httpx.HTTPError as e:
            print(f"[HTTP] error: {e}")
        except Exception as e:  # pragma: no cover - fallback genérico
            print(f"[ERROR] {e}")


def main() -> None:
    """Punto de entrada del CLI.

    Parsea argumentos y delega en la rutina correspondiente. Si no se especifica
    ninguna acción, imprime `--help`.

    Flags:
        --search: Búsqueda vía REST (`/search`).
        --download: Descarga simulada vía gRPC.
        --upload-mb: Subida simulada (en MB) vía gRPC.
        --status: Consulta `/status` vía REST.
        --base: URL base REST (por defecto http://localhost:8001).
        --grpc-host/--grpc-port: Host/puerto del servidor gRPC.
        --fanout: Límite de difusión en la búsqueda.

    Ejemplos:
        python client.py --search ".txt" --fanout 2
        python client.py --download hello.txt --grpc-host 127.0.0.1 --grpc-port 50051
        python client.py --upload-mb 5 --grpc-host 127.0.0.1 --grpc-port 50051
        python client.py --status
    """
    parser = argparse.ArgumentParser(
        description="Enhanced P2P Client (REST + gRPC)",
        epilog=(
            "Examples:\n"
            "  python client.py --search \".txt\" --fanout 3 --base http://localhost:8001\n"
            "  python client.py --download hello1.txt --grpc-host localhost --grpc-port 50051\n"
            "  python client.py --upload-mb 10 --grpc-host localhost --grpc-port 50051\n"
            "  python client.py --status --base http://localhost:8001\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--search", help="Search query (REST /search)")
    parser.add_argument("--download", help="Filename to download via gRPC")
    parser.add_argument("--upload-mb", type=float, help="Upload N MB via gRPC")
    parser.add_argument("--status", action="store_true", help="Get peer status (REST)")
    parser.add_argument("--base", default="http://localhost:8001", help="Base REST URL")
    parser.add_argument("--grpc-host", default="localhost", help="gRPC host")
    parser.add_argument("--grpc-port", type=int, default=50051, help="gRPC port")
    parser.add_argument("--fanout", type=int, default=3, help="Search fanout")

    args = parser.parse_args()

    if args.search:
        asyncio.run(do_search(args.base, args.search, args.fanout))
    elif args.download:
        asyncio.run(do_download(args.grpc_host, args.grpc_port, args.download))
    elif args.upload_mb:
        size_bytes = int(args.upload_mb * 1024 * 1024)
        asyncio.run(do_upload(args.grpc_host, args.grpc_port, size_bytes))
    elif args.status:
        asyncio.run(do_status(args.base))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
