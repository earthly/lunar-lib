# Category: `.api`

API specifications and documentation. This category uses a **two-layer normalization strategy** to support multiple API protocols (REST, gRPC, GraphQL) under a single, unified hierarchy.

## Normalization Strategy

The `.api` category is organized into two layers:

### Layer 1: Protocol-Agnostic (`.api.*`)

The top level holds data that applies regardless of API protocol. Every API — REST, gRPC, GraphQL — has spec files, and every spec file has a path, format, validity, and operation/schema counts. Policies that need to answer "does this repo have API documentation?" or "are all API specs valid?" operate at this level without caring about the protocol.

### Layer 2: Native/Raw (`.api.native.openapi`, `.api.native.protobuf`, etc.)

The full, unmodified spec as JSON. Policies that need deep inspection of tool-specific fields (e.g., OpenAPI endpoints, security schemes, gRPC service definitions) parse the raw data directly. Each spec lineage gets its own key under `.api.native` — Swagger 2.0 and OpenAPI 3.x share `.api.native.openapi` since Swagger 2.0 is just the earlier version of the same spec (the raw JSON already self-identifies via `"swagger": "2.0"` vs `"openapi": "3.x"`).

## Design Tradeoffs: Two Layers vs Three Layers

An alternative design adds a **third layer** of protocol-specific normalization (`.api.rest.endpoints[]`, `.api.grpc.services[]`, etc.) between the agnostic layer and the native layer.

| | Two layers (chosen) | Three layers (alternative) |
|---|---|---|
| **Structure** | `.api.spec_files[]` + `.api.native.*` | `.api.spec_files[]` + `.api.rest.endpoints[]` + `.api.rest.native.*` |
| **Policy authoring** | Policies parse raw native specs for anything beyond `spec_files` metadata | Policies query structured, normalized data without parsing raw specs |
| **Cross-tool consistency** | Each native format has its own shape; policies handle the differences | OpenAPI and Swagger endpoints normalize to the same `endpoints[]` shape |
| **Design risk** | No premature normalization; native data speaks for itself | Must design the normalized shape upfront per protocol — risky for protocols we haven't built yet |
| **Complexity** | Flatter, simpler, fewer moving parts | Deeper hierarchy, more collector logic to extract and normalize |

**Why two layers was chosen:** The protocol-agnostic `spec_files` array handles the most common policy questions (does documentation exist? is it valid? what version?). For deeper inspection, policies can parse the native spec directly — this avoids designing normalized shapes for gRPC and GraphQL prematurely, keeps the collector simpler, and lets policies access all native fields without waiting for them to be "normalized."

**When to reconsider:** If many policies need the same extracted data from native specs (e.g., multiple policies all parsing OpenAPI paths to get endpoint lists), it may be worth adding a protocol-specific normalized layer for that protocol to avoid duplicated parsing logic.

## Full Structure

This example shows a repo with REST (OpenAPI) and gRPC APIs. In practice, most repos will have only one protocol.

```json
{
  "api": {
    "spec_files": [
      {
        "path": "api/openapi.yaml",
        "format": "openapi",
        "protocol": "rest",
        "valid": true,
        "version": "3.0.3",
        "operation_count": 12,
        "schema_count": 5
      },
      {
        "path": "proto/user.proto",
        "format": "protobuf",
        "protocol": "grpc",
        "valid": true,
        "version": "proto3",
        "operation_count": 4,
        "schema_count": 6
      },
      {
        "path": "schema.graphql",
        "format": "graphql",
        "protocol": "graphql",
        "valid": true,
        "version": null,
        "operation_count": 5,
        "schema_count": 3
      }
    ],

    "native": {
      "openapi": {
        "openapi": "3.0.3",
        "info": { "title": "User API", "version": "1.0.0" },
        "paths": {
          "/users": {
            "get": { "operationId": "listUsers", "summary": "List all users", "tags": ["users"] },
            "post": { "operationId": "createUser", "summary": "Create a new user", "tags": ["users"] }
          },
          "/users/{id}": {
            "get": { "operationId": "getUser", "summary": "Get user by ID", "tags": ["users"] }
          }
        },
        "components": {
          "schemas": {
            "User": { "type": "object", "properties": { "...": "full schema" } },
            "CreateUserRequest": { "type": "object", "properties": { "...": "full schema" } }
          }
        }
      }
    }
  }
}
```

## Key Policy Paths

### Protocol-Agnostic (Layer 1)

| Path | Type | Description |
|------|------|-------------|
| `.api.spec_files[]` | array | All spec files across all protocols (presence = API docs exist) |
| `.api.spec_files[].path` | string | File path relative to repo root |
| `.api.spec_files[].format` | string | Spec format: `"openapi"`, `"swagger"`, `"protobuf"`, `"graphql"` |
| `.api.spec_files[].protocol` | string | API protocol: `"rest"`, `"grpc"`, `"graphql"` |
| `.api.spec_files[].valid` | boolean | Whether the file parses without errors |
| `.api.spec_files[].version` | string | Spec version (e.g., `"3.0.3"`, `"2.0"`, `"proto3"`) |
| `.api.spec_files[].operation_count` | number | Number of operations defined in this spec |
| `.api.spec_files[].schema_count` | number | Number of schema/type definitions in this spec |

### Native/Raw (Layer 2)

| Path | Type | Description |
|------|------|-------------|
| `.api.native.openapi` | object | Full raw OpenAPI/Swagger spec as JSON (both 3.x and 2.0 — self-identifies via top-level key) |
| `.api.native.protobuf` | object | Raw .proto file contents (future, gRPC collector) |
| `.api.native.graphql` | string | Raw GraphQL SDL schema (future, GraphQL collector) |

## Collectors

| Collector | Writes To | Detects |
|-----------|-----------|---------|
| `openapi` | `.api.spec_files[]`, `.api.native.openapi` | OpenAPI 3.x and Swagger 2.0 files |

The `openapi` collector handles both OpenAPI 3.x and Swagger 2.0 specs in a single pass — Swagger IS OpenAPI (2.0 was renamed to 3.0 when the project moved to the OpenAPI Initiative). Both versions store their raw spec under `.api.native.openapi`; the raw JSON self-identifies via the top-level key (`"openapi": "3.0.3"` vs `"swagger": "2.0"`). The `format` field on each `.api.spec_files[]` entry distinguishes the source version (`"openapi"` vs `"swagger"`) for policies that need to check.

## Future: gRPC Support

When a gRPC/protobuf collector is added, it writes to `.api.spec_files[]` (with `protocol: "grpc"`) and `.api.native.protobuf`:

```json
{
  "api": {
    "spec_files": [
      {
        "path": "proto/user.proto",
        "format": "protobuf",
        "protocol": "grpc",
        "valid": true,
        "version": "proto3",
        "operation_count": 4,
        "schema_count": 6
      }
    ],
    "native": {
      "protobuf": {
        "files": [
          { "path": "proto/user.proto", "content": "syntax = \"proto3\"; ..." }
        ]
      }
    }
  }
}
```

Policies that need gRPC-specific data (services, RPCs, message types) parse `.api.native.protobuf` directly. The `api-docs` policy handles universal checks (spec exists, spec valid) via `.api.spec_files[]` without any gRPC-specific logic.

## Future: GraphQL Support

When a GraphQL collector is added, it writes to `.api.spec_files[]` (with `protocol: "graphql"`) and `.api.native.graphql`:

```json
{
  "api": {
    "spec_files": [
      {
        "path": "schema.graphql",
        "format": "graphql",
        "protocol": "graphql",
        "valid": true,
        "version": null,
        "operation_count": 5,
        "schema_count": 3
      }
    ],
    "native": {
      "graphql": "type User {\n  id: ID!\n  email: String!\n  name: String!\n}\n\ntype Query {\n  users(limit: Int = 10): [User!]!\n  user(id: ID!): User\n}\n\ntype Mutation {\n  createUser(input: CreateUserInput!): User!\n}"
    }
  }
}
```

Policies that need GraphQL-specific data (queries, mutations, types) parse `.api.native.graphql` SDL directly.

## Design Notes

This category follows the standard collector/policy pattern: each spec format gets its own technology-specific collector, but they all feed the same `.api` category (see [Raw/Native Data convention](conventions.md#rawnative-data)):

```
collectors/openapi/  ──writes──→  .api.spec_files[]  ←──reads── policies/api-docs/
                                  .api.native.*
```

The `openapi` collector handles both OpenAPI 3.x and Swagger 2.0 file formats (Swagger IS OpenAPI). Both versions share `.api.native.openapi` — no separate swagger key or collector is needed.

**Why two layers?**
- **Layer 1** lets policies answer universal questions ("has API docs?", "all specs valid?") with zero knowledge of REST vs gRPC.
- **Layer 2** preserves the full raw spec for policies that need deep protocol-specific inspection, following the [`.native` convention](conventions.md#rawnative-data).
