# Speech – Apache CouchDB (Tarea 1 NoSQL 2026)

Duración objetivo: **42 min** (40–45). Entre paréntesis, el tiempo de cada bloque. Las frases en *cursiva* son indicaciones para vos, no se leen. Está escrito para decirlo con tus palabras: usalo de guía, no lo memorices.

Reparto: Intro 2 · Fundamentos 9 · Práctica 5 · Distribución 6 · Operación 6 · Adopción 2 · **Demo 11** · Cierre 3.

---

## 00 · Portada (0:30)

Buenas. Soy Felipe Queirolo y les voy a hablar de Apache CouchDB. Es una base de datos documental, y lo que la distingue es que se pensó para trabajar sin conexión y sincronizar después. Eso va a ser el hilo de toda la charla, y al final lo vemos funcionando con una demo.

## 01 · Agenda (1:30)

Voy en cuatro partes. Primero los fundamentos: de dónde viene y cómo está hecha por dentro. Después la práctica, con un ejemplo y las formas de consultar. Después distribución y operación: replicación, escalado, seguridad, backups. Y cierro con dónde se usa, la demo y mi opinión.

La demo está en el medio, después de los casos de uso. Hice un caso ficticio, "OSE Móvil", con inspectores que leen medidores en zonas sin señal, y lo armé con tres nodos reales en Docker.

---

## 02 · Historia (2:30)

CouchDB la empezó en 2005 Damien Katz, que venía de trabajar en Lotus Notes en IBM. Lotus Notes ya tenía esta idea de documentos que se replican, y él la rehizo en Erlang y la autofinanció casi dos años antes de publicarla.

En 2008 entra a la Apache Incubator y pasa a licencia Apache 2.0. En 2010 sale la versión 1.0 y se gradúa como proyecto de primer nivel.

Un dato para no confundir: en 2012 Katz se va y arma Couchbase. Couchbase **no** es CouchDB, es un producto comercial distinto, aunque el nombre engaña.

En 2013 se fusiona BigCouch, que era el clustering de Cloudant, y eso es lo que da el clustering nativo en la 2.0, en 2016. Ahí también aparecen Fauxton, la interfaz web, y Mango, las consultas sin JavaScript. En 2020 la 3.0 elimina el famoso "Admin Party", el modo donde cualquiera entraba sin login. Hoy la estable es la 3.5.

Y mi dato favorito: "Couch" es un acrónimo, *Cluster Of Unreliable Commodity Hardware*. O sea, desde el nombre la idea es que la base siga andando aunque el hardware sea barato y falle.

## 03 · Arquitectura y fundamentos (3:30)

Cuatro decisiones de diseño explican casi todo.

**Una.** Los datos son documentos JSON. No hay tablas ni filas. Cada documento tiene un `_id` único y un `_rev`.

**Dos.** MVCC, control de concurrencia multiversión. Cuando se modifica un documento no se pisa: se crea una versión nueva. Por eso las lecturas nunca bloquean a las escrituras y al revés. El `_rev` tiene la forma `número-hash`, y cambia en **cada escritura**, incluso al borrar, porque el borrado deja una tumba. No cambia al leer ni al replicar: la réplica copia la misma revisión. Y si alguien intenta escribir con un `_rev` viejo, CouchDB responde 409 Conflict. Eso es control optimista de concurrencia.

**Tres.** Está hecha en Erlang, el mismo runtime que se usa en centrales telefónicas, pensado para mucha concurrencia y tolerancia a fallos.

**Cuatro.** Todo es HTTP. No hay un driver propietario: con GET, PUT, POST y DELETE sobre URLs administrás la base completa. Yo armé la demo entera con `curl` y `fetch`.

Y el archivo `.couch` es append-only: solo se agrega al final. Eso protege ante cortes de luz porque nunca se sobrescribe, y el costo es que el archivo crece, por eso existe la compactación, que reescribe el archivo dejando solo lo vigente y sin bloquear.

## 04 · Diseño de esquema (2:00)

CouchDB no impone esquema, pero eso no significa que no haya que diseñar.

La regla es modelar por **agregado de negocio**: un documento tiene todo lo que se lee junto. Si algo se lee siempre con el padre y no crece sin límite, lo embebo, por ejemplo una dirección dentro de un cliente. Si es compartido o puede crecer, lo referencio por `_id`.

Como no hay tablas, uso un campo `type` para saber de qué clase es cada documento. También uso `_id` con significado, por ejemplo zona, fecha y secuencia, así puedo recorrer rangos ordenados sin otro índice.

Y algo importante en multi-master: documentos chicos y de una sola responsabilidad bajan la probabilidad de conflicto.

Por último, los design documents son "el esquema" de la base: ahí viven las vistas y la validación. La función `validate_doc_update` corre en cada escritura. En mi ejemplo rechaza una lectura sin `medidor_id` o una que retroceda, porque un medidor no puede marcar menos que antes. Es el equivalente a un constraint, pero con una advertencia que va a aparecer en replicación: no se aplica a lo que llega replicado.

---

## 05 · Ejemplo: OSE Móvil (1:30)

El caso es ficticio. Inspectores que recorren zonas rurales sin cobertura estable y cargan lecturas de medidores. Cada tablet tiene su copia local de la base, y al volver a tener señal sincroniza contra el central.

Este es un documento de lectura: tiene medidor, zona, inspector, fecha, el valor en metros cúbicos y la geolocalización. Y abajo los dos design documents, con una vista por zona y otra de pendientes de sincronizar.

La idea a retener: el protocolo no distingue "maestro" de "esclavo". Cualquier réplica puede escribir.

## 06 · Lenguaje de consulta (3:30)

Hay tres formas de preguntar.

La primera es la API HTTP cruda: GET por `_id`, PUT para crear o actualizar con el `_rev` vigente, `_bulk_docs` para lotes, DELETE que deja una tumba.

La segunda son las **vistas MapReduce**. Una función `map` recorre los documentos y emite clave y valor. El resultado es un índice B-tree que se actualiza incrementalmente, y opcionalmente un `reduce` agrega con `_sum`, `_count` o `_stats`. Lo que más me gustó: con clave compuesta zona-año-mes, **una sola vista** responde tres niveles de detalle, y el parámetro `group_level` elige cuál. Eso es drill-down sin escribir una vista por nivel. Lo vamos a ver en la demo.

La tercera es **Mango**, desde la 2.0. Es declarativa, por JSON, parecida a MongoDB, sin escribir funciones. Necesita un índice sobre los campos que filtro; si no, recorre toda la base. Con `_explain` veo qué índice eligió el planificador. Y su límite: **no agrega**. No tiene `reduce` ni `group by`. Para "cuántos metros cúbicos por zona" tengo que usar una vista.

¿Y los JOIN? No existen. Lo equivalente es hacer que la vista emita el `_id` de otro documento y consultarla con `include_docs=true`: CouchDB me adjunta ese documento en la misma respuesta. En la demo lo uso para cruzar lecturas con el padrón de medidores.

---

## 07 · Replicación (4:00)

Esta es la característica que distingue a CouchDB.

La replicación es **multi-master** y nativa. Puede ser puntual o continua, push o pull, y puede filtrarse. Corre entre cualquier par de nodos, incluso entre CouchDB y PouchDB, sin jerarquía. Es incremental, usa el feed de `_changes`, y es eventualmente consistente: los nodos pueden diferir un rato y convergen al sincronizar.

Es **offline-first** por diseño. El dispositivo trabaja siempre contra su copia local, y la sincronización es otro proceso que se retoma sola cuando hay red.

Ahora, ¿qué pasa cuando dos réplicas editan el mismo documento sin verse? CouchDB **no pierde nada**. Guarda todas las revisiones en conflicto, marca una ganadora de forma determinística, la misma en todos los nodos, y deja la versión perdedora visible con `_conflicts`. La fusión real la decide la aplicación: se elige el contenido, se escribe sobre la ganadora y se borra la revisión perdedora.

Y la advertencia que dejé pendiente: `validate_doc_update` **no protege** contra esto, porque una rama replicada llega sin `oldDoc` y las reglas que comparan con el valor anterior no se disparan. Validar y resolver conflictos son dos cosas distintas.

Finalmente, PouchDB: es la implementación en JavaScript del mismo protocolo, corre dentro del navegador o la app, guarda en IndexedDB y sincroniza con una línea. Eso hace realista el caso de la tablet: no necesita un servidor, alcanza con la app. En la demo la tablet B es exactamente eso.

## 08 · Almacenamiento y escalamiento (2:00)

En un solo nodo, una base es un archivo `.couch`. Es simple y alcanza para equipos chicos o instalaciones edge.

Desde la 2.0 hay clustering nativo: cada base se parte en **shards**, parámetro `q`, y cada shard se copia en varios nodos, parámetro `n`. Por ejemplo, con 3 shards y 2 réplicas, si un nodo cae los datos siguen en otro. Agregar nodos rebalancea y la aplicación no cambia, porque la API HTTP es la misma.

Para ser honesto con lo que muestro: mi demo **no** es un clúster con shards. Son dos masters independientes que se replican entre sí, con HAProxy adelante. Es otro enfoque de alta disponibilidad, más simple, y me sirve para mostrar el failover.

---

## 09 · Configuración y administración (1:30)

Hay dos archivos: `default.ini` con los valores de fábrica, que no se toca, y `local.ini` con los cambios del sitio. También se puede cambiar casi todo en caliente por HTTP, sin reiniciar.

Fauxton es el panel web de administración: bases, documentos, vistas, usuarios, réplicas y logs. Los usuarios viven en la base `_users`, y cada base tiene su documento `_security` con roles admin y members. Y para desplegar hay imagen oficial de Docker y Helm chart para Kubernetes. Yo usé Docker Compose.

## 10 · Seguridad (1:30)

En tránsito: TLS nativo o terminado en un proxy como Nginx o HAProxy; CORS configurable. Autenticación: básica, por cookie, por proxy o JWT.

Desde la 3.0 es **obligatorio** crear un admin al instalar. Después, autorización por base con `_security` y por documento con `validate_doc_update`.

El límite importante: CouchDB **no cifra** el archivo en disco. El cifrado en reposo se resuelve con cifrado del disco o del filesystem, o lo da el proveedor en la nube.

## 11 · Backups (1:15)

Hay tres estrategias. Copiar los archivos, que es seguro en caliente por ser append-only. Backup lógico con `couchbackup` y `couchrestore`, que exporta a JSON lines. Y replicar continuamente a otro nodo, que es un backup caliente siempre al día.

Y una regla simple: un backup que nunca se restauró no está verificado.

## 12 · Performance (1:45)

La lectura por `_id` es muy rápida porque es una búsqueda directa en el B-tree. Las vistas pueden ser lentas la primera vez, mientras se construye el índice, y después son incrementales, así que conviene calentarlas tras cada despliegue. La compactación reduce disco y mejora I/O, y conviene programarla en horarios tranquilos. Agrupar operaciones con `_bulk_docs` reduce muchísimo los viajes HTTP. Y Mango sin índice recorre todo, así que el `_index` importa tanto como en SQL.

Contra un relacional: mejor throughput de escritura para documentos independientes porque no hay locks de fila; peor para joins y agregaciones complejas, que no resuelve de forma nativa.

---

## 13 · Cloud (1:00)

El camino gestionado es **IBM Cloudant**, un DBaaS construido sobre CouchDB; de hecho, su clustering terminó fusionado de vuelta al proyecto Apache. Tiene SLA de 99,99% y cifrado con Key Protect. Si no, corre como cualquier carga contenerizada en AWS, GCP, Azure o Kubernetes. Fuera de Cloudant hay poca oferta gestionada, y esto lo vuelvo a mencionar en mi opinión.

## 14 · Casos empresariales y de gobierno (1:00)

Casi todos eligieron CouchDB por lo mismo: datos que viajan y no siempre están conectados. El CERN para datos del LHC. La Cruz Roja con una app de campo en zonas de desastre. La BBC como CMS. npm, con una réplica pública del registro de paquetes. United Airlines, con entretenimiento a bordo en más de 3.000 aviones, que sincroniza en tierra. E IBM, con Cloudant.

---

## 15 · DEMO EN VIVO (11:00)

*Antes de arrancar: monitor en :8084 con los 3 nodos verdes, tablet B con "reiniciar datos locales" hecho.*

**Intro (1 min)** — "Este es el mismo caso de OSE Móvil, pero ejecutándose. Tres nodos CouchDB en Docker: dos masters, central A y central B, que se replican entre sí; y la tablet A, otro nodo CouchDB. La tablet B es PouchDB en el navegador. Adelante de los masters hay un HAProxy, que es el único endpoint que conocen las interfaces." *Señalá el diagrama de la slide.*

**01 – Escritura sin conexión (1 min)** — *Tablet A, apagá "en línea", cargá una lectura.* "Guardó localmente aunque el central no está alcanzable. Fíjense en el `_rev`: empieza con 1, es la primera revisión."

**02 y 03 – Dos clientes y replicación filtrada (1,5 min)** — *Mostrá tablet B.* "Esta tablet es PouchDB, no tiene servidor. Solo baja las lecturas de su inspector, `mgonzalez`; el consolidado de todos está en el central."

**04 – Drill-down (1,5 min)** — *Central, botones 1/2/3.* "Una sola vista con clave zona-año-mes. Con nivel 1 veo por zona; con 2, por año; con 3, por mes. Miren la URL: lo único que cambia es `group_level`."

**05 – Mango (1,5 min)** — *`_explain`, después el botón sin índice.* "Mango me dice qué índice usó. Si filtro por un campo sin índice, cae a `_all_docs`: recorre toda la base."

**06 – Conflicto (1,5 min)** — *Sincronizar ambas tablets.* "Dos inspectores midieron el mismo medidor sin verse. Al sincronizar, no se pierde ninguna. Acá en el central veo las dos revisiones con sus `_rev`, y CouchDB eligió una como ganadora."

**07 – Se cae un master (1,5 min)** — *Monitor: apagar central A. Cargar y sincronizar desde una tablet.* "Bajo un master en vivo. HAProxy lo detecta en un par de segundos y manda todo al otro. Nadie elige nada a mano. Cuando lo vuelvo a encender, se pone al día solo." *Mientras espera, hablá del health check a `/_up`.*

**08 – Resolución (1,5 min)** — *Elegir la ganadora en el central.* "La aplicación decide cuál vale: escribe ese contenido y borra la revisión perdedora. Ahí se cierra el conflicto, y el `_rev` nuevo es el que queda."

*Si algo falla: monitor → Reset total → Encender todo (~1 min), o pasá a mostrar la slide y explicá lo que iba a pasar.*

---

## 16 · Cuándo sí, cuándo no (1:00)

Encaja bien en apps móviles u offline-first con varios dispositivos, catálogos y gestión de contenidos, captura de datos IoT que se genera desconectada, y sistemas donde importa auditar el historial de revisiones.

Conviene evitarla para reportes analíticos pesados, transacciones fuertes entre varios documentos, como en banca, y datos muy relacionales con muchos joins. La pregunta no es si es buena, sino si el problema es el que ella resuelve mejor.

## 17 · Opinión personal (1:30)

Lo que más me gustó es que hace una cosa sola y la hace bien. La replicación multi-maestro y el trabajo offline no se los agregaron después: es para lo que nació en 2005 y se nota. Armando la demo me sorprendió lo poco que hay que pelearse con la herramienta. No instalé ningún driver, hice todo con `curl` y `fetch`.

Lo que no me cerró tanto: la comunidad es bastante más chica que la de MongoDB y fuera de Cloudant hay pocas opciones de nube gestionada. Las vistas MapReduce me costaron más de lo esperado, porque hay que pensar la consulta antes del modelo y viniendo de SQL se siente raro. Y lo de shards y quórum es una curva que un proyecto chico capaz nunca necesita subir.

¿La usaría? Para un CRM o una app de ventas común, no, me iría a algo más convencional. Pero para el caso de la demo, gente en la calle cargando datos sin señal y sincronizando cuando puede, no encontré nada que lo resuelva tan directo. Ahí CouchDB casi no tiene competencia.

## 18 · Cierre (0:30)

Con esto cierro. Las fuentes están en pantalla: la documentación oficial, el repositorio y *CouchDB: The Definitive Guide*. Gracias, y quedo a disposición para las preguntas.

---

## Ensayo y tiempos

| Bloque | Min | Acumulado |
|---|---|---|
| Portada + Agenda | 2:00 | 2:00 |
| Historia + Arquitectura + Esquema | 8:00 | 10:00 |
| Ejemplo + Consulta | 5:00 | 15:00 |
| Replicación + Almacenamiento | 6:00 | 21:00 |
| Config + Seguridad + Backups + Performance | 6:00 | 27:00 |
| Cloud + Casos | 2:00 | 29:00 |
| **Demo** | **11:00** | **40:00** |
| Cuándo + Opinión + Cierre | 3:00 | 43:00 |

Si vas largo, recortá en este orden: Config y Backups (se pueden decir en 1 min cada una), luego Historia. Si vas corto, ampliá conflictos y la comparación con MongoDB.

## Preguntas probables

- **¿Por qué no MongoDB?** MongoDB tiene un primario que acepta escrituras y mejor analítica; CouchDB es multi-master y sincroniza offline sobre HTTP. Para este caso, el offline pesa más.
- **¿Qué pasa si se cae un master?** HAProxy lo detecta con `/_up` en ~1–2 s y manda al otro; al volver, la replicación continua lo pone al día.
- **¿HAProxy no es un punto único de falla?** Sí. En producción se duplica con dos balanceadores e IP virtual (keepalived/VRRP) o un balanceador de la nube. En la demo lo dejé simple.
- **¿Es un clúster?** No, son dos masters independientes que se replican. El clustering con shards (`n`, `q`) es otra opción que la presentación explica.
- **¿Cómo se resuelve un conflicto?** La app elige el contenido, hace PUT sobre la ganadora y DELETE de la perdedora.
