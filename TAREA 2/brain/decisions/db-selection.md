---
name: db-selection
description: Justificación de las bases de datos NoSQL seleccionadas (MongoDB y Redis)
metadata:
  type: decision
  status: draft
  last-updated: 2026-09-20
---

# Selección de Bases de Datos NoSQL

## Problema

EventFlow necesita manejar alta concurrencia en lecturas (eventos, usuarios) y garantizar consistencia en escrituras (reservas, pagos). Esto requiere múltiples bases de datos NoSQL optimizadas para diferentes patrones de acceso.

**Requisitos específicos:**
- Lectura de eventos/usuarios: extremadamente rápida, escalable, eventual consistency OK
- Escritura de reservas/pagos: consistencia fuerte, sin dobles ventas

---

## Opciones Consideradas

### Opción 1: Solo MongoDB
✅ Flexible schema  
✅ Escalabilidad horizontal  
❌ No es la más rápida para lecturas masivas  
❌ No es ideal para operaciones transaccionales de pagos  

### Opción 2: MongoDB + Redis
✅ MongoDB para datos estructurados (usuarios, eventos)  
✅ Redis para caché + reservas (consistencia fuerte, in-memory)  
✅ Separación clara de responsabilidades  
✅ Escalabilidad óptima en ambos frentes  
✅ Redis para transacciones atómicas (pagos)  

### Opción 3: MongoDB + PostgreSQL
❌ PostegreSQL no es NoSQL (no entra en requerimientos)  

---

## Decisión

**✅ Seleccionado: MongoDB + Redis + PostgreSQL (3-Database Architecture)**

### MongoDB
- **Responsabilidad:** Usuarios, Eventos, datos maestros
- **Razón:** Escalabilidad horizontal, flexible schema, buena para lecturas de volumen
- **Configuración:** Replica set para HA
- **Consistency:** AP (Eventual)

### Redis
- **Responsabilidad:** Caché de eventos, Reservas (transacciones de pagos)
- **Razón:** In-memory, ultra-rápido, atomic transactions (Lua scripting), ideal para operaciones críticas
- **Configuración:** Persistence (RDB/AOF), Cluster o Sentinel para HA
- **Consistency:** CP (Strong)

### PostgreSQL
- **Responsabilidad:** Event Log (immutable), Auditoría, Compliance
- **Razón:** ACID transactions, ordered timeline, append-only log para debugging y auditoría
- **Configuración:** Replication (standby), backups automáticos
- **Consistency:** CA (ACID logs)

---

## Justificación

1. **Separación de Consistencia:** MongoDB para datos eventuales, Redis para datos críticos ✅
2. **Escalabilidad:** MongoDB sharding para volumen, Redis para throughput ✅
3. **Rendimiento:** Redis en-memory para pagos/reservas críticas ✅
4. **Costo-Beneficio:** Ambas son open-source, amplio soporte ✅
5. **Patrones SAGA/CoR:** Redis Lua scripts para transacciones atómicas, MongoDB para orquestación ✅

---

## Implicaciones

- Necesidad de sincronización eventual entre MongoDB y Redis (caché)
- Invalidación de caché en cambios críticos
- Conexión a dos sistemas de BD (más complejidad operacional)
- Mayor capacidad de escalabilidad que con una sola BD

---

## Artefactos

- [ ] Schema MongoDB (usuarios, eventos)
- [ ] Schema Redis (reservas, caché)
- [ ] Estrategia de invalidación de caché
- [ ] Documentación de failover y recuperación
