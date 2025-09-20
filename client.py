from __future__ import annotations
import argparse
import asyncio
import httpx
import grpc
from peer.config import load_config
from peer.protos import filetransfer_pb2 as pb2
from peer.protos import filetransfer_pb2_grpc as pb2_grpc

async def do_search(base_url: str, q: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{base_url}/search", params={"query": q, "fanout": 3})
        r.raise_for_status()
        print(r.json())

async def do_download(host: str, port: int, filename: str):
    ch = grpc.aio.insecure_channel(f"{host}:{port}")
    stub = pb2_grpc.FileTransferStub(ch)
    chunks = 0
    total = 0
    async for c in stub.DummyDownload(pb2.FileRequest(filename=filename)):
        chunks += 1
        total += len(c.data)
    print(f"Received {chunks} chunks totaling {total} bytes")

async def do_upload(host: str, port: int, size: int):
    ch = grpc.aio.insecure_channel(f"{host}:{port}")
    stub = pb2_grpc.FileTransferStub(ch)

    async def gen():
        sent = 0
        payload = b"x" * 65536
        while sent < size:
            to_send = payload[:min(len(payload), size - sent)]
            sent += len(to_send)
            yield pb2.FileChunk(data=to_send, seq=1)

    resp = await stub.DummyUpload(gen())
    print(f"Uploaded {resp.chunks} chunks totaling {resp.received_bytes} bytes")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", help="query to search via REST")
    ap.add_argument("--download", help="filename to download via gRPC")
    ap.add_argument("--upload-bytes", type=int, help="send N dummy bytes via gRPC")
    ap.add_argument("--base", default="http://localhost:8001")
    ap.add_argument("--grpc-host", default="localhost")
    ap.add_argument("--grpc-port", type=int, default=50051)
    args = ap.parse_args()

    if args.search:
        asyncio.run(do_search(args.base, args.search))
    elif args.download:
        asyncio.run(do_download(args.grpc_host, args.grpc_port, args.download))
    elif args.upload_bytes:
        asyncio.run(do_upload(args.grpc_host, args.grpc_port, args.upload_bytes))
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
