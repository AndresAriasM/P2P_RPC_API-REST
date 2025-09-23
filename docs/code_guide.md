# Guía de Testing P2P - Sistema Distribuido

Sistema P2P no estructurado con 4 peers, APIs REST, gRPC, health checks, rate limiting y observabilidad completa.

## Inicio del Sistema

### Levantar Docker Compose
```bash
# Construir imágenes
docker-compose build

# Levantar todos los servicios
docker-compose up -d

# Verificar estado
docker-compose ps
```

### Gestión de Peers Individuales
```bash
# Un peer específico
docker-compose up -d peer1

# Múltiples peers
docker-compose up -d peer1 peer2 peer3

# Parar un peer específico
docker-compose stop peer2

# Reiniciar un peer
docker-compose restart peer3

# Ver logs de peer específico
docker logs -f peer1
```

## Testing de Componentes Core

### 1. Health Checks
```bash
# Verificar que todos responden
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health

# En AWS (cambiar IP)
curl http://<IP-AWS>:8001/health
```

### 2. Bootstrap de Red P2P
```bash
# Conectar peers automáticamente
curl -X POST http://localhost:8001/bootstrap
curl -X POST http://localhost:8002/bootstrap
curl -X POST http://localhost:8003/bootstrap
curl -X POST http://localhost:8004/bootstrap

# Verificar peers conocidos
curl http://localhost:8001/peers
```

### 3. Indexado de Archivos
```bash
# Ver archivos en cada peer
curl http://localhost:8001/files  # hello1.txt
curl http://localhost:8002/files  # notes2.txt
curl http://localhost:8003/files  # readme3.txt
curl http://localhost:8004/files  # data4.txt
```

## Testing de Búsqueda P2P

### Búsqueda Distribuida
```bash
# Buscar todos los .txt en la red
curl "http://localhost:8001/search?query=.txt&fanout=3"

# Búsquedas específicas
curl "http://localhost:8001/search?query=hello&fanout=2"
curl "http://localhost:8002/search?query=data&fanout=3"
curl "http://localhost:8003/search?query=notes&fanout=1"

# Con parámetros TTL
curl "http://localhost:8001/search?query=.txt&fanout=2&ttl=2"
```

### Registro Manual de Peers
```bash
# Peer1 registra a Peer4
curl -X POST http://localhost:8001/register \
  -H "Content-Type: application/json" \
  -d '{"url": "http://localhost:8004"}'

# Verificar registro
curl http://localhost:8001/peers
```

## Testing de gRPC (Transferencias)

### Downloads
```bash
# Download desde peer1
docker exec -it peer1 python client.py --download hello1.txt --grpc-host localhost --grpc-port 50051

# Download desde peer2
docker exec -it peer2 python client.py --download notes2.txt --grpc-host localhost --grpc-port 50052

# Download archivo inexistente (test error)
docker exec -it peer3 python client.py --download noexiste.txt --grpc-host localhost --grpc-port 50053
```

### Uploads
```bash
# Upload 1MB a peer1
docker exec -it peer1 python client.py --upload-mb 1 --grpc-host localhost --grpc-port 50051

# Upload 5MB a peer4
docker exec -it peer4 python client.py --upload-mb 5 --grpc-host localhost --grpc-port 50054

# Upload grande (test límites)
docker exec -it peer2 python client.py --upload-mb 10 --grpc-host localhost --grpc-port 50052
```

## Testing de Tolerancia a Fallos

### Simular Caída de Peer
```bash
# 1. Verificar red inicial
curl http://localhost:8001/peers

# 2. Parar peer2
docker-compose stop peer2

# 3. Verificar que otros peers detectan la falla
sleep 35  # Esperar health check
curl http://localhost:8001/peers

# 4. Buscar archivos (debe seguir funcionando)
curl "http://localhost:8001/search?query=.txt&fanout=3"

# 5. Reiniciar peer2
docker-compose start peer2

# 6. Verificar recuperación
sleep 35
curl http://localhost:8001/peers
```

### Cascada de Fallos
```bash
# Parar múltiples peers
docker-compose stop peer2 peer3

# Verificar que peer1 y peer4 siguen funcionando
curl http://localhost:8001/search?query=hello
curl http://localhost:8004/files

# Recuperar red
docker-compose start peer2 peer3
```

## Testing de Concurrencia

### Requests Simultáneos
```bash
# Múltiples búsquedas concurrentes
for i in {1..10}; do
  curl -s "http://localhost:8001/search?query=.txt" &
done
wait

# Múltiples health checks
for i in {1..20}; do
  curl -s "http://localhost:800$((i%4+1))/health" &
done
wait
```

### Rate Limiting
```bash
# Test límites de requests (debería fallar después de 100/min)
for i in {1..25}; do
  curl -s "http://localhost:8001/files" &
done
wait
echo "Rate limiting test completed"
```

## Testing de Microservicios

### APIs REST
```bash
# Status detallado
curl http://localhost:8001/status
curl http://localhost:8002/status

# Métricas
curl http://localhost:8001/metrics | head -20
curl http://localhost:8002/metrics | grep p2p_requests_total

# CORS (si aplicable)
curl -H "Origin: http://example.com" http://localhost:8001/health
```

### Cliente CLI
```bash
# Status usando cliente
docker exec -it peer1 python client.py --status --base http://localhost:8001

# Búsqueda usando cliente
docker exec -it peer2 python client.py --search ".txt" --base http://localhost:8002 --fanout 3
```

## Testing de Observabilidad

### Prometheus
```bash
# Verificar métricas disponibles
curl http://localhost:9090/api/v1/label/__name__/values

# Queries específicas
curl "http://localhost:9090/api/v1/query?query=p2p_requests_total"
curl "http://localhost:9090/api/v1/query?query=p2p_healthy_peers_count"

# Acceso web: http://localhost:9090
# En AWS: http://<IP-AWS>:9090
```

### Grafana
```bash
# Acceso web: http://localhost:3001 (admin/admin)
# En AWS: http://<IP-AWS>:3001

# Queries útiles para dashboards:
# - p2p_requests_total
# - rate(p2p_requests_total[1m])
# - p2p_healthy_peers_count
# - sum by (peer) (p2p_requests_total)
```






