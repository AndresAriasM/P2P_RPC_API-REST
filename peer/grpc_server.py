from __future__ import annotations
import os
import asyncio
import grpc
from pathlib import Path

from .config import load_config
from .protos import filetransfer_pb2 as pb2
from .protos import filetransfer_pb2_grpc as pb2_grpc

CFG = load_config(os.environ.get("PEER_CONFIG"))

CHUNK = 64 * 1024

class FileTransferServicer(pb2_grpc.FileTransferServicer):
    async def DummyDownload(self, request, context):
        filename = request.filename
        path = Path(CFG.shared_dir) / filename
        if not path.exists() or not path.is_file():
            # ECO: return a single small chunk echoing the request
            data = f"ECHO: {filename} not found on {CFG.name}".encode("utf-8")
            yield pb2.FileChunk(data=data, seq=1)
            return
        seq = 0
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK)
                if not chunk:
                    break
                seq += 1
                yield pb2.FileChunk(data=chunk, seq=seq)

    async def DummyUpload(self, request_iterator, context):
        total = 0
        chunks = 0
        async for chunk in request_iterator:
            if chunk.data:
                total += len(chunk.data)
                chunks += 1
        return pb2.UploadStatus(received_bytes=total, chunks=chunks)

async def serve():
    server = grpc.aio.server()
    pb2_grpc.add_FileTransferServicer_to_server(FileTransferServicer(), server)
    server.add_insecure_port(f"[::]:{CFG.grpc_port}")
    await server.start()
    print(f"gRPC server for {CFG.name} listening on {CFG.grpc_port}")
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
