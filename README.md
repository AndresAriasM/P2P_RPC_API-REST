# P2P - Comunicación entre procesos (REST + gRPC)

Sebastián Muñoz Castañeda
Andres Arias Medina
Argenis Eduardo Omañan


Este repo implementa un sistema P2P **no estructurado** con servicios de **Directorio/Localización** vía **REST** y servicios ECO/DUMMY de **carga/descarga** vía **gRPC**. Cada contenedor representa un *peer* con microservicios separados (REST + gRPC), soporte de concurrencia y lectura dinámica de configuración (JSON).

## Arquitectura (resumen)
- **REST (FastAPI)**: `/register`, `/bootstrap`, `/files`, `/peers`, `/search`
- **gRPC (FileTransfer)**: `DummyDownload`, `DummyUpload`
- **Índice local**: listado de archivos de un directorio configurable.
- **Localización**: búsqueda *best effort* en el peer actual y difusión limitada (fanout) a peers amigos.
- **Concurrencia**: Uvicorn (ASGI) + `grpc.aio` (asyncio).
- **Configuración**: `configs/peer*.json`.
- **Despliegue**: Docker + docker-compose.

## Cómo correr en localhost
```bash
# 1) Construir imágenes
docker compose build

# 2) Levantar 3 peers
docker compose up -d

# 3) Bootstrap (opcional, el sistema auto‑descubre al hacer /bootstrap)
curl -X POST http://localhost:8001/bootstrap

# 4) Listar archivos y buscar
curl http://localhost:8001/files
curl "http://localhost:8001/search?query=.txt&fanout=3"

# 5) Probar gRPC con el cliente
docker exec -it peer1 bash -lc "python client.py --download hello1.txt --grpc-host localhost --grpc-port 50051"
docker exec -it peer2 bash -lc "python client.py --upload-bytes 100000 --grpc-host localhost --grpc-port 50052"

# 6) Script de demo (requiere jq)
bash scripts/demo.sh
```

## Cómo correr en AWS (Academy / EC2)
1. Crear **3 instancias** (t2.micro) con Docker instalado (Amazon Linux 2023 o Ubuntu 22.04).
2. Abrir puertos en el **Security Group** (por VM):
   - REST: `8001|8002|8003` (TCP)
   - gRPC: `50051|50052|50053` (TCP)
3. Copiar el repo a **cada** VM y ajustar `configs/peer*.json` con la IP pública/privada en `self_url` y `friend_*`.
4. `docker compose build && docker compose up -d` en **cada** VM.
5. Verificar:
   - `curl http://<IP-peer1>:8001/peers`
   - `curl "http://<IP-peer1>:8001/search?query=.txt&fanout=2"`

## Notas de evaluación
- **Directorios configurables**, **coexistencia REST+gRPC**, **ECO/DUMMY** implementados, **concurrencia** y **3 peers** en compose.
- Logs de gRPC/REST visibles en `docker logs peerX`.
- Tolerancia a fallos: si un peer no responde, la búsqueda continúa con los accesibles.

## Desarrollo
- `generate_proto.sh` compila el `.proto` a Python.
- Código organizado en `peer/` y cliente CLI en `client.py`.
- Pruebas mínimas en `tests/` (extiéndelas).

## 📄 Informe técnico
El informe completo con objetivos, marco teórico, arquitectura, APIs y resultados se encuentra en [report.md](./report.md).


## Autoevaluación
95/100
