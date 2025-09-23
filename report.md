# Informe Técnico – Proyecto P2P (REST + gRPC)

## 1. Objetivo
El objetivo de este proyecto es diseñar e implementar un sistema **peer-to-peer (P2P) no estructurado**, en el cual múltiples nodos (peers) puedan:
- Compartir información sobre archivos de manera **distribuida y descentralizada**.
- **Buscar archivos** en otros peers a través de consultas con difusión controlada (fanout y TTL).
- Simular la **transferencia de archivos** mediante servicios ECO/DUMMY de subida y descarga con **gRPC**.
- Garantizar **concurrencia, tolerancia a fallos y monitoreo** a través de métricas expuestas a Prometheus.

---

## 2. Marco Teórico Breve
- **Redes P2P**: Arquitectura distribuida donde cada nodo puede actuar como cliente y servidor, eliminando la dependencia de un servidor central y favoreciendo la escalabilidad.
- **REST API**: Interfaz basada en HTTP para la comunicación entre procesos. En este proyecto se usa para directorio, localización y búsqueda de archivos.
- **gRPC**: Framework de llamadas a procedimientos remotos de alto rendimiento, ideal para simular transferencia de archivos en chunks, con eficiencia y soporte de streaming.
- **Concurrencia**: Uso de `asyncio`, FastAPI (ASGI) y `grpc.aio` para manejar múltiples clientes de forma simultánea sin bloqueos.
- **Métricas y tolerancia a fallos**: Con Prometheus y health checks, el sistema evalúa el estado de peers y continúa funcionando incluso si algunos fallan.

---

## 3. Arquitectura del Sistema
Cada **peer** contiene dos servidores:

- **Servidor REST (FastAPI)**  
  Endpoints principales:  
  - `/register`, `/bootstrap`: registro y descubrimiento de peers amigos.  
  - `/files`: listado de archivos locales indexados.  
  - `/search`: búsqueda distribuida con fanout y TTL.  
  - `/peers`: lista de peers conocidos.  
  - `/status`: configuración y estadísticas del peer.  
  - `/metrics`: métricas para Prometheus.  

- **Servidor gRPC (`grpc.aio`)**  
  - `DummyDownload(FileRequest)`: simula descarga en chunks (64KB) de un archivo.  
  - `DummyUpload(FileChunk stream)`: simula subida de archivos y devuelve un resumen de bytes recibidos y chunks procesados.  

- **Componentes internos**:  
  - `indexer.py`: indexa archivos del directorio local con metadatos (nombre, tamaño, checksum, extensión).  
  - `health.py`: verifica periódicamente el estado de peers vecinos.  
  - `state.py`: gestiona la lista de peers, cache de búsquedas, rate limiting y persistencia ligera.  
  - `metrics.py`: recolecta métricas de requests, búsquedas, transferencias y peers saludables.  
  - `config.py`: lee configuración dinámica desde `configs/peer*.json`.

---

## 4. Configuración de Peers
Se configuraron **4 peers**, cada uno con su archivo JSON (`peer1.json` a `peer4.json`).  

Ejemplo (`peer1.json`):
```json
{
  "name": "peer1",
  "rest_port": 8001,
  "grpc_port": 50051,
  "metrics_port": 9001,
  "shared_dir": "/data",
  "friend_primary": "http://peer2:8002",
  "friend_secondary": "http://peer3:8003",
  "self_url": "http://peer1:8001",
  "search_ttl": 3,
  "max_fanout": 3
}
```

---

## 5. Protocolos y APIs
- **REST**: JSON sobre HTTP, usado para registro, búsqueda, directorio y estado.  
- **gRPC**: protocolo binario eficiente sobre HTTP/2, usado para la transferencia ECO/DUMMY de archivos.  
- **Prometheus**: expone métricas en `/metrics` para monitoreo del sistema.  

---

## 6. Entorno de Ejecución
- **Lenguaje**: Python 3.11  
- **Frameworks**: FastAPI, Uvicorn, gRPC (`grpc.aio`), Prometheus-client  
- **Contenedores**: Docker y docker-compose para levantar múltiples peers.  
- **Despliegue**:  
  - **Localhost**: varios peers en contenedores distintos.  
  - **AWS Academy/EC2**: un peer por instancia, con puertos REST y gRPC expuestos.  

---

## 7. Pruebas y Resultados
- **Búsquedas distribuidas**: desde un peer con fanout=3, lograron alcanzar todos los nodos de la red.  
- **Transferencias simuladas**: descargas y subidas exitosas con gRPC, mostrando progreso, velocidad y tiempo total.  
- **Concurrencia**: múltiples clientes consultaron y transfirieron simultáneamente sin errores.  
- **Manejo de fallos**: al desconectar un peer, las búsquedas siguieron resolviendo gracias a peers alternativos.  
- **Métricas observadas**: número de requests, peers saludables, resultados de búsqueda y bytes transferidos.  

---

## 8. Conclusiones
- Se implementó un sistema **P2P no estructurado** con **REST + gRPC**, cumpliendo los objetivos académicos.  
- La configuración dinámica por JSON hace el sistema **escalable y flexible**: basta añadir un archivo `peerN.json` para incluir un nuevo nodo.  
- El sistema demostró **tolerancia a fallos** y buena capacidad de concurrencia en las pruebas.  
- Es **modular y extensible**, permitiendo agregar nuevas funcionalidades como transferencia real de archivos o seguridad.  
