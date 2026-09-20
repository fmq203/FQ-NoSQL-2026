---
name: eventos-service
description: Especificación del Servicio de Eventos
metadata:
  type: specification
  status: draft
---

# Servicio de Eventos

## Responsabilidades

- Crear y gestionar eventos
- Mostrar disponibilidad de entradas
- Gestionar aforo total y entradas vendidas

## Base de Datos

- **BD:** MongoDB (colección `eventos`)
- **Consistency:** Eventual (AP)
- **Actualizaciones críticas:** Coordinadas con Reservas Service (SAGA)

## Endpoints

Ver [[eventos-endpoints]]

## Schema

Ver [[event-schema]]

## Interacciones

- **Con Reservas Service:** GET /eventos/{id} para obtener aforo disponible
- **Actualizaciones:** POST /eventos/{id}/decrement-tickets (reservado para SAGA)

## Notas

- Alto volumen de LECTURAS (cacheable con Redis)
- Escrituras de aforo solo desde SAGA (consistencia garantizada)
- Sharding por región/fecha de evento
