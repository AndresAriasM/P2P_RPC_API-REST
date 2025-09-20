# Informe Técnico – Sistema P2P (REST + gRPC)

## Objetivo y Marco Teórico (breve)
Diseñar e implementar un sistema P2P **no estructurado** que permita **localizar** recursos (archivos) en múltiples *peers* y exponer servicios **ECO/DUMMY** de carga/descarga. Se combinan **API REST** para directorio/localización y **gRPC** para operaciones de transferencia simulada. La red es **descentralizada**, cada *peer* puede servir de punto de acceso para consultas (bootstrap vía amigos).

## Descripción del servicio y problema
- Se comparte **solo el índice** de archivos (nombre, tamaño, mtime) de un directorio local configurable.
- Transferencia **no real**: `DummyDownload` y `DummyUpload` envían/reciben flujos de bytes sin persistencia.
- El *peer* que inicia puede contactar **cualquier otro** para localización; la descarga simulada se hace **entre el dueño y el cliente**.

## Arquitectura del sistema y diagramas
**Componentes por peer**:
- **PServidor-REST** (FastAPI): `/register`, `/bootstrap`, `/files`, `/peers`, `/search`
- **PServidor-gRPC** (`grpc.aio`): `DummyDownload`, `DummyUpload`
- **PCliente** (CLI): búsqueda y pruebas de gRPC
- **Config** (JSON): IP, puertos, directorio compartido, URL amigos (titular/suplente)

**Flujo (texto)**:
1. P2 se inicia → `POST /bootstrap` a P4 (amigo).
2. P2 y P4 se **registran mutuamente**.
3. Cliente pregunta en P2: `/search?q=foo`.
4. P2 busca local y **difunde** a sus amigos (fanout).
5. P2 obtiene lista de *peers* con `foo` → el cliente usa gRPC directo al *peer* dueño para `DummyDownload`.

## Especificación de protocolos y APIs
### REST
- `GET /health` → `{status, peer}`
- `POST /register {url}` → registra *peer* remoto
- `POST /bootstrap` → registra `self` en amigos (titular/suplente)
- `GET /peers` → listado de *peers* conocidos
- `GET /files` → índice local con URLs
- `GET /search?query=txt&fanout=2` → búsqueda distribuida (difusión limitada)

### gRPC
`FileTransfer`:
- `DummyDownload(FileRequest)` → `stream FileChunk`
- `DummyUpload(stream FileChunk)` → `UploadStatus`

## Algoritmos de particionamiento y distribución
- **Índice local**: particionado **por *peer*** (cada uno mantiene su directorio).
- **Localización**: difusión **limitada** (*fanout*, TTL implícito por tamaño de lista).
- **Consistencia**: eventual; índice recalculado por solicitud (simple y robusto).

## Entorno de ejecución nativo o Docker
- **Python 3.11**, FastAPI + `grpc.aio`, Docker y docker-compose.
- Concurrencia: ASGI + IO asíncrono en gRPC.
- `generate_proto.sh` produce los *stubs* gRPC.

## Pruebas y análisis de resultados
- **Local** con 3 peers:
  - `curl /files` en cada peer.
  - `curl /search?query=.txt&fanout=2` devuelve resultados de varios peers.
  - `client.py --download hello1.txt` recibe chunks gRPC.
- **Evidencia de concurrencia**: múltiples `curl`/descargas simultáneas responden sin bloqueo (ASGI + gRPC).

## Manejo de fallas
- Si un amigo no responde, la búsqueda continúa con los otros (excepciones controladas).
- `PeerState.prune()` disponible para limpiar peers inactivos (TTL configurable).

## Despliegue en AWS
- 3 VMs con Docker, abrir puertos y ajustar `self_url`/`friend_*` a IPs reales.
- Compose por peer o imagen única + variables (PEER_CONFIG).

## Resultados
- Localización correcta, transferencia simulada funcional, evidencias de ejecución distribuida (3 peers).
- Logs y *curl* muestran tolerancia básica a fallos.

## Repositorio y Video
- Subir código a GitHub con README y este informe.
- Video (10–15 min): guion sugerido
  1) Objetivo y marco teórico (1–2 min)
  2) Arquitectura y APIs (4–5 min)
  3) Demo en localhost + AWS (4–5 min)
  4) Resultados, fallas, cierre (2–3 min)
