---
name: usuarios-service
description: Especificación del Servicio de Usuarios
metadata:
  type: specification
  status: draft
---

# Servicio de Usuarios

## Responsabilidades

- Crear y gestionar perfiles de usuario
- Registrar historial de compras
- Recuperar datos de usuario rápidamente

## Base de Datos

- **BD:** MongoDB (colección `usuarios`)
- **Consistency:** Eventual (AP)

## Endpoints

Ver [[usuarios-endpoints]]

## Schema

Ver [[user-schema]]

## Interacciones

- **Con Reservas Service:** GET /usuarios/{id} para validar usuario

## Notas

- Sin lógica de negocio crítica
- Alto volumen de lecturas (caché con Redis si es necesario)
- Escalabilidad: sharding por usuario_id
