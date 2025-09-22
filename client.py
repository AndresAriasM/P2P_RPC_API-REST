from __future__ import annotations
import argparse
import asyncio
import time
import httpx
import grpc
import sys
import os

# Add current directory to path for imports
sys.path.append('/app')

try:
    from peer.protos import filetransfer_pb2 as pb2
    from peer.protos import filetransfer_pb2_grpc as pb2_grpc
except ImportError as e:
    print(f"Warning: gRPC imports failed: {e}")
    print("gRPC functionality will not be available")
    pb2 = None
    pb2_grpc = None

async def do_search(base_url: str, query: str, fanout: int = 3):
    """Enhanced search with timing and better output"""
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(
                f"{base_url}/search",
                params={"query": query, "fanout": fanout}
            )
            response.raise_for_status()
            data = response.json()
            
            duration = time.time() - start_time
            print(f"Search completed in {duration:.2f}s")
            print(f"Query: {data.get('query', 'N/A')}")
            print(f"Fanout used: {data.get('fanout_used', 'N/A')}")
            print()
            
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
                        print(f"  - {file['name']} ({size_mb:.2f}MB, {file_type}, {checksum})")
                        total_files += 1
                else:
                    print("  No matching files")
                print()
            
            print(f"Total files found: {total_files}")
            
        except httpx.HTTPError as e:
            print(f"HTTP error: {e}")
        except Exception as e:
            print(f"Error: {e}")

async def do_download(host: str, port: int, filename: str):
    """Enhanced download with progress tracking"""
    if not pb2 or not pb2_grpc:
        print("Error: gRPC modules not available")
        return
        
    start_time = time.time()
    
    try:
        channel = grpc.aio.insecure_channel(f"{host}:{port}")
        stub = pb2_grpc.FileTransferStub(channel)
        
        chunks_received = 0
        total_bytes = 0
        
        print(f"Downloading {filename} from {host}:{port}...")
        
        async for chunk in stub.DummyDownload(pb2.FileRequest(filename=filename)):
            chunks_received += 1
            total_bytes += len(chunk.data)
            
            # Progress indicator for large files
            if chunks_received % 100 == 0:
                print(f"  Received {chunks_received} chunks, {total_bytes / 1024 / 1024:.2f}MB")
        
        duration = time.time() - start_time
        speed_mbps = (total_bytes / 1024 / 1024) / duration if duration > 0 else 0
        
        print(f"Download completed:")
        print(f"  Chunks: {chunks_received}")
        print(f"  Size: {total_bytes / 1024 / 1024:.2f}MB")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Speed: {speed_mbps:.2f}MB/s")
        
        await channel.close()
        
    except grpc.RpcError as e:
        print(f"gRPC error: {e.code()} - {e.details()}")
    except Exception as e:
        print(f"Error: {e}")

async def do_upload(host: str, port: int, size_bytes: int):
    """Enhanced upload with progress tracking"""
    if not pb2 or not pb2_grpc:
        print("Error: gRPC modules not available")
        return
        
    start_time = time.time()
    
    try:
        channel = grpc.aio.insecure_channel(f"{host}:{port}")
        stub = pb2_grpc.FileTransferStub(channel)
        
        print(f"Uploading {size_bytes / 1024 / 1024:.2f}MB to {host}:{port}...")
        
        async def chunk_generator():
            sent_bytes = 0
            seq = 0
            chunk_size = 65536  # 64KB chunks
            payload = b"x" * chunk_size
            
            while sent_bytes < size_bytes:
                seq += 1
                remaining = size_bytes - sent_bytes
                chunk_data = payload[:min(chunk_size, remaining)]
                sent_bytes += len(chunk_data)
                
                # Progress indicator
                if seq % 100 == 0:
                    progress = (sent_bytes / size_bytes) * 100
                    print(f"  Progress: {progress:.1f}% ({sent_bytes / 1024 / 1024:.2f}MB)")
                
                yield pb2.FileChunk(data=chunk_data, seq=seq)
        
        response = await stub.DummyUpload(chunk_generator())
        
        duration = time.time() - start_time
        speed_mbps = (response.received_bytes / 1024 / 1024) / duration if duration > 0 else 0
        
        print(f"Upload completed:")
        print(f"  Chunks sent: {response.chunks}")
        print(f"  Bytes received by server: {response.received_bytes / 1024 / 1024:.2f}MB")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Speed: {speed_mbps:.2f}MB/s")
        
        await channel.close()
        
    except grpc.RpcError as e:
        print(f"gRPC error: {e.code()} - {e.details()}")
    except Exception as e:
        print(f"Error: {e}")

async def do_status(base_url: str):
    """Get detailed peer status"""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(f"{base_url}/status")
            response.raise_for_status()
            data = response.json()
            
            print(f"Peer Status: {data.get('peer', 'unknown')}")
            print(f"URL: {data.get('url', 'unknown')}")
            print()
            
            config = data.get('config', {})
            print("Configuration:")
            for key, value in config.items():
                print(f"  {key}: {value}")
            print()
            
            stats = data.get('stats', {})
            print("Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
            print()
            
            healthy_peers = data.get('healthy_peers', [])
            print(f"Healthy peers ({len(healthy_peers)}):")
            for peer in healthy_peers:
                print(f"  - {peer}")
            
        except httpx.HTTPError as e:
            print(f"HTTP error: {e}")
        except Exception as e:
            print(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Enhanced P2P Client")
    parser.add_argument("--search", help="Search query")
    parser.add_argument("--download", help="Filename to download via gRPC")
    parser.add_argument("--upload-mb", type=float, help="Upload N MB via gRPC")
    parser.add_argument("--status", action="store_true", help="Get peer status")
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