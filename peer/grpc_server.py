from __future__ import annotations
import os
import asyncio
import grpc
import logging
from pathlib import Path

from .config import load_config
from .state import PeerState
from .metrics import get_metrics
from .protos import filetransfer_pb2 as pb2
from .protos import filetransfer_pb2_grpc as pb2_grpc

CFG = load_config(os.environ.get("PEER_CONFIG"))
STATE = PeerState(CFG.self_url)

CHUNK_SIZE = 64 * 1024
logger = logging.getLogger(__name__)

class FileTransferServicer(pb2_grpc.FileTransferServicer):
    
    async def DummyDownload(self, request, context):
        """Enhanced download with rate limiting and better error handling"""
        filename = request.filename
        client_ip = context.peer()
        
        # Rate limiting for downloads
        if not STATE.check_rate_limit(client_ip, "downloads", CFG.rate_limit.downloads_per_minute):
            metrics = get_metrics()
            if metrics:
                metrics.record_rate_limit_hit("downloads")
            await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Download rate limit exceeded")
            return
        
        path = Path(CFG.shared_dir) / filename
        total_bytes = 0
        seq = 0
        
        if not path.exists() or not path.is_file():
            # Return error message as single chunk
            error_msg = f"File {filename} not found on {CFG.name}"
            chunk_data = error_msg.encode("utf-8")
            total_bytes = len(chunk_data)
            yield pb2.FileChunk(data=chunk_data, seq=1)
        else:
            # Real file download simulation
            try:
                file_size = path.stat().st_size
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        seq += 1
                        total_bytes += len(chunk)
                        yield pb2.FileChunk(data=chunk, seq=seq)
                        
                        # Simulate some latency for realism
                        await asyncio.sleep(0.001)
                
                logger.info(f"Downloaded {filename} ({total_bytes} bytes) to {client_ip}")
            except Exception as e:
                logger.error(f"Error downloading {filename}: {e}")
                error_msg = f"Error reading {filename}: {str(e)}"
                chunk_data = error_msg.encode("utf-8")
                yield pb2.FileChunk(data=chunk_data, seq=1)
        
        # Record metrics
        metrics = get_metrics()
        if metrics:
            metrics.record_file_transfer("download", total_bytes)

    async def DummyUpload(self, request_iterator, context):
        """Enhanced upload with validation and progress tracking"""
        client_ip = context.peer()
        
        # Rate limiting for uploads
        if not STATE.check_rate_limit(client_ip, "downloads", CFG.rate_limit.downloads_per_minute):
            metrics = get_metrics()
            if metrics:
                metrics.record_rate_limit_hit("uploads")
            await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Upload rate limit exceeded")
            return
        
        total_bytes = 0
        chunk_count = 0
        last_seq = 0
        
        try:
            async for chunk in request_iterator:
                if chunk.data:
                    chunk_count += 1
                    total_bytes += len(chunk.data)
                    
                    # Validate sequence number (simple check)
                    if chunk.seq < last_seq:
                        logger.warning(f"Out of order chunk from {client_ip}: {chunk.seq} < {last_seq}")
                    last_seq = chunk.seq
                    
                    # Simulate processing time
                    await asyncio.sleep(0.001)
                
                # Limit total upload size to prevent abuse
                if total_bytes > 100 * 1024 * 1024:  # 100MB limit
                    await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Upload size limit exceeded")
                    return
            
            logger.info(f"Received upload ({total_bytes} bytes, {chunk_count} chunks) from {client_ip}")
            
        except Exception as e:
            logger.error(f"Error during upload from {client_ip}: {e}")
            await context.abort(grpc.StatusCode.INTERNAL, f"Upload error: {str(e)}")
            return
        
        # Record metrics
        metrics = get_metrics()
        if metrics:
            metrics.record_file_transfer("upload", total_bytes)
        
        return pb2.UploadStatus(received_bytes=total_bytes, chunks=chunk_count)

async def serve():
    """Start the gRPC server with enhanced configuration"""
    server = grpc.aio.server(
        options=[
            ('grpc.keepalive_time_ms', 30000),
            ('grpc.keepalive_timeout_ms', 5000),
            ('grpc.keepalive_permit_without_calls', True),
            ('grpc.http2.max_pings_without_data', 0),
            ('grpc.http2.min_time_between_pings_ms', 10000),
            ('grpc.http2.min_ping_interval_without_data_ms', 5000)
        ]
    )
    
    pb2_grpc.add_FileTransferServicer_to_server(FileTransferServicer(), server)
    listen_addr = f"[::]:{CFG.grpc_port}"
    server.add_insecure_port(listen_addr)
    
    logger.info(f"Starting gRPC server for {CFG.name} on {listen_addr}")
    await server.start()
    
    logger.info(f"gRPC server for {CFG.name} listening on port {CFG.grpc_port}")
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("gRPC server shutting down...")
        await server.stop(grace=5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())