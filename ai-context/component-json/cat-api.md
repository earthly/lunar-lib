# Category: `.api`

API specifications and documentation. This category uses a **layered normalization strategy** to support multiple API protocols (REST, gRPC, GraphQL) under a single, unified hierarchy.

## Normalization Strategy

The `.api` category is organized into three layers:

### Layer 1: Protocol-Agnostic (`.api.*`)

The top level holds data that applies regardless of API protocol. Every API — REST, gRPC, GraphQL — has spec files, and every spec file has a path, format, validity, and operation/schema counts. Policies that just need to answer "does this repo have API documentation?" or "are all API specs valid?" operate at this level without caring about the protocol.

### Layer 2: Protocol-Specific Normalized (`.api.rest.*`, `.api.grpc.*`, etc.)

Each protocol gets its own sub-object with **normalized, tool-agnostic** data. For REST, this means actual endpoints (path + method), schemas, and operations — regardless of whether the source was OpenAPI or Swagger. For gRPC, this would mean services, RPCs, and message types. Policies that need to validate specific API design rules (e.g., "all endpoints must have descriptions") operate at this level.

### Layer 3: Native/Raw (`.api.rest.native.openapi`, `.api.rest.native.swagger`, etc.)

The full, unmodified spec as JSON. Policies that need deep inspection of tool-specific fields (e.g., OpenAPI `x-` extensions, security schemes) can reach into the raw data. Each format gets its own key under `.native`.

## Full Structure

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
        "path": "swagger.json",
        "format": "swagger",
        "protocol": "rest",
        "valid": true,
        "version": "2.0",
        "operation_count": 8,
        "schema_count": 3
      }
    ],

    "rest": {
      "endpoints": [
        {
          "path": "/users",
          "method": "GET",
          "operation_id": "listUsers",
          "summary": "List all users",
          "tags": ["users"]
        },
        {
          "path": "/users",
          "method": "POST",
          "operation_id": "createUser",
          "summary": "Create a new user",
          "tags": ["users"],
          "request_body": "CreateUserRequest"
        },
        {
          "path": "/users/{id}",
          "method": "GET",
          "operation_id": "getUser",
          "summary": "Get user by ID",
          "tags": ["users"],
          "parameters": [
            { "name": "id", "in": "path", "type": "string", "required": true }
          ]
        }
      ],
      "schemas": [
        {
          "name": "User",
          "type": "object",
          "property_count": 4,
          "required_count": 2,
          "properties": ["id", "email", "name", "created_at"]
        },
        {
          "name": "CreateUserRequest",
          "type": "object",
          "property_count": 2,
          "required_count": 2,
          "properties": ["email", "name"]
        },
        {
          "name": "Error",
          "type": "object",
          "property_count": 2,
          "required_count": 2,
          "properties": ["code", "message"]
        }
      ],
      "native": {
        "openapi": { "openapi": "3.0.3", "info": { "...": "full raw OpenAPI spec as JSON" } },
        "swagger": { "swagger": "2.0", "info": { "...": "full raw Swagger spec as JSON" } }
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

### REST-Specific Normalized (Layer 2)

| Path | Type | Description |
|------|------|-------------|
| `.api.rest.endpoints[]` | array | All REST endpoints, normalized from any source |
| `.api.rest.endpoints[].path` | string | URL path (e.g., `"/users/{id}"`) |
| `.api.rest.endpoints[].method` | string | HTTP method (`"GET"`, `"POST"`, etc.) |
| `.api.rest.endpoints[].operation_id` | string | Operation identifier |
| `.api.rest.endpoints[].summary` | string | Short description |
| `.api.rest.endpoints[].tags` | array | Grouping tags |
| `.api.rest.endpoints[].parameters[]` | array | Path/query/header parameters |
| `.api.rest.endpoints[].request_body` | string | Request body schema name (if applicable) |
| `.api.rest.schemas[]` | array | All schema definitions, normalized from any source |
| `.api.rest.schemas[].name` | string | Schema name (e.g., `"User"`) |
| `.api.rest.schemas[].type` | string | Schema type (`"object"`, `"array"`, `"string"`, etc.) |
| `.api.rest.schemas[].property_count` | number | Number of properties |
| `.api.rest.schemas[].required_count` | number | Number of required properties |
| `.api.rest.schemas[].properties` | array | List of property names |

### Native/Raw (Layer 3)

| Path | Type | Description |
|------|------|-------------|
| `.api.rest.native.openapi` | object | Full raw OpenAPI 3.x spec as JSON |
| `.api.rest.native.swagger` | object | Full raw Swagger 2.0 spec as JSON |

## Collectors

| Collector | Writes To | Detects |
|-----------|-----------|---------|
| `openapi` | `.api.spec_files[]`, `.api.rest.endpoints[]`, `.api.rest.schemas[]`, `.api.rest.native.openapi` | OpenAPI 3.x files |
| `swagger` | `.api.spec_files[]`, `.api.rest.endpoints[]`, `.api.rest.schemas[]`, `.api.rest.native.swagger` | Swagger 2.0 files |

Both collectors write to the same arrays (`.api.spec_files[]`, `.api.rest.endpoints[]`, `.api.rest.schemas[]`). Lunar auto-merges them. The `format` field on each entry distinguishes the source.

## Future: gRPC Support

When a gRPC/protobuf collector is added, it will follow the same layered pattern:

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

    "grpc": {
      "services": [
        {
          "name": "UserService",
          "rpcs": [
            {
              "name": "GetUser",
              "request_type": "GetUserRequest",
              "response_type": "User",
              "client_streaming": false,
              "server_streaming": false
            },
            {
              "name": "ListUsers",
              "request_type": "ListUsersRequest",
              "response_type": "ListUsersResponse",
              "client_streaming": false,
              "server_streaming": true
            }
          ]
        }
      ],
      "messages": [
        {
          "name": "User",
          "field_count": 4,
          "fields": ["id", "email", "name", "created_at"]
        },
        {
          "name": "GetUserRequest",
          "field_count": 1,
          "fields": ["id"]
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
}
```

A `protobuf` collector would write to `.api.spec_files[]` (with `protocol: "grpc"`) and `.api.grpc.*`. The existing `api-docs` policy would automatically pick up gRPC specs via `.api.spec_files[]` for protocol-agnostic checks (spec exists, spec valid). gRPC-specific policies could assert on `.api.grpc.services[]` and `.api.grpc.messages[]`.

## Future: GraphQL Support

GraphQL would follow the same pattern with `.api.graphql.queries[]`, `.api.graphql.mutations[]`, `.api.graphql.types[]`, and `.api.graphql.native.sdl` for the raw schema definition.

## Design Notes

This category uses **[Strategy 17: Multi-Collector Category Aggregation](../strategies.md#strategy-17-multi-collector-category-aggregation)**. Each spec format gets its own technology-specific collector, but they all feed the same `.api` category:

```
collectors/openapi/  ──writes──┐
                                ├──→  .api.spec_files[]  ←──reads── policies/api-docs/
collectors/swagger/  ──writes──┘        .api.rest.*
```

**Why three layers?**
- **Layer 1** lets policies answer universal questions ("has API docs?", "all specs valid?") with zero knowledge of REST vs gRPC.
- **Layer 2** gives policies the actual API surface (endpoints, schemas, RPCs) in a normalized, tool-agnostic form — no matter if the source was OpenAPI 3.0, Swagger 2.0, or a future AsyncAPI spec.
- **Layer 3** preserves the full raw spec for policies that need deep tool-specific inspection, following the [`.native` convention](conventions.md#rawnative-data).
