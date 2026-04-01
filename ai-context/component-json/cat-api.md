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

This example shows a repo with all three API protocols. In practice, most repos will have only one or two.

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
        "openapi": { "openapi": "3.0.3", "info": { "...": "full raw OpenAPI spec as JSON" } }
      }
    },

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
    },

    "graphql": {
      "queries": [
        {
          "name": "users",
          "return_type": "[User!]!",
          "arguments": [
            { "name": "limit", "type": "Int", "default_value": "10" }
          ],
          "description": "List all users"
        },
        {
          "name": "user",
          "return_type": "User",
          "arguments": [
            { "name": "id", "type": "ID!", "default_value": null }
          ],
          "description": "Get user by ID"
        }
      ],
      "mutations": [
        {
          "name": "createUser",
          "return_type": "User!",
          "arguments": [
            { "name": "input", "type": "CreateUserInput!", "default_value": null }
          ],
          "description": "Create a new user"
        }
      ],
      "subscriptions": [
        {
          "name": "userCreated",
          "return_type": "User!",
          "arguments": [],
          "description": "Subscribe to new user creation events"
        }
      ],
      "types": [
        {
          "name": "User",
          "kind": "OBJECT",
          "field_count": 4,
          "fields": ["id", "email", "name", "createdAt"]
        },
        {
          "name": "CreateUserInput",
          "kind": "INPUT_OBJECT",
          "field_count": 2,
          "fields": ["email", "name"]
        }
      ],
      "native": {
        "sdl": "type User {\n  id: ID!\n  email: String!\n  name: String!\n  createdAt: DateTime!\n}\n..."
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

### gRPC-Specific Normalized (Layer 2 — future)

| Path | Type | Description |
|------|------|-------------|
| `.api.grpc.services[]` | array | gRPC service definitions |
| `.api.grpc.services[].name` | string | Service name (e.g., `"UserService"`) |
| `.api.grpc.services[].rpcs[]` | array | RPC methods in the service |
| `.api.grpc.services[].rpcs[].name` | string | RPC method name |
| `.api.grpc.services[].rpcs[].request_type` | string | Request message type |
| `.api.grpc.services[].rpcs[].response_type` | string | Response message type |
| `.api.grpc.services[].rpcs[].client_streaming` | boolean | Client-side streaming |
| `.api.grpc.services[].rpcs[].server_streaming` | boolean | Server-side streaming |
| `.api.grpc.messages[]` | array | Protobuf message definitions |
| `.api.grpc.messages[].name` | string | Message name |
| `.api.grpc.messages[].field_count` | number | Number of fields |
| `.api.grpc.messages[].fields` | array | List of field names |

### GraphQL-Specific Normalized (Layer 2 — future)

| Path | Type | Description |
|------|------|-------------|
| `.api.graphql.queries[]` | array | GraphQL query operations |
| `.api.graphql.queries[].name` | string | Query name |
| `.api.graphql.queries[].return_type` | string | Return type (e.g., `"[User!]!"`) |
| `.api.graphql.queries[].arguments[]` | array | Query arguments |
| `.api.graphql.queries[].description` | string | Short description |
| `.api.graphql.mutations[]` | array | GraphQL mutation operations |
| `.api.graphql.mutations[].name` | string | Mutation name |
| `.api.graphql.mutations[].return_type` | string | Return type |
| `.api.graphql.mutations[].arguments[]` | array | Mutation arguments |
| `.api.graphql.mutations[].description` | string | Short description |
| `.api.graphql.subscriptions[]` | array | GraphQL subscription operations |
| `.api.graphql.types[]` | array | GraphQL type definitions |
| `.api.graphql.types[].name` | string | Type name |
| `.api.graphql.types[].kind` | string | Type kind (`"OBJECT"`, `"INPUT_OBJECT"`, `"ENUM"`, `"INTERFACE"`, `"UNION"`) |
| `.api.graphql.types[].field_count` | number | Number of fields |
| `.api.graphql.types[].fields` | array | List of field names |

### Native/Raw (Layer 3)

| Path | Type | Description |
|------|------|-------------|
| `.api.rest.native.openapi` | object | Full raw OpenAPI 3.x spec as JSON |
| `.api.rest.native.swagger` | object | Full raw Swagger 2.0 spec as JSON |
| `.api.grpc.native.protobuf` | object | Raw .proto file contents (future) |
| `.api.graphql.native.sdl` | string | Raw GraphQL SDL schema (future) |

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

When a GraphQL collector is added, it will follow the same layered pattern. GraphQL has three operation types (queries, mutations, subscriptions) and a type system — all normalized under `.api.graphql`:

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

    "graphql": {
      "queries": [
        {
          "name": "users",
          "return_type": "[User!]!",
          "arguments": [
            { "name": "limit", "type": "Int", "default_value": "10" },
            { "name": "offset", "type": "Int", "default_value": "0" }
          ],
          "description": "List all users"
        },
        {
          "name": "user",
          "return_type": "User",
          "arguments": [
            { "name": "id", "type": "ID!", "default_value": null }
          ],
          "description": "Get user by ID"
        }
      ],
      "mutations": [
        {
          "name": "createUser",
          "return_type": "User!",
          "arguments": [
            { "name": "input", "type": "CreateUserInput!", "default_value": null }
          ],
          "description": "Create a new user"
        },
        {
          "name": "updateUser",
          "return_type": "User!",
          "arguments": [
            { "name": "id", "type": "ID!", "default_value": null },
            { "name": "input", "type": "UpdateUserInput!", "default_value": null }
          ],
          "description": "Update an existing user"
        }
      ],
      "subscriptions": [
        {
          "name": "userCreated",
          "return_type": "User!",
          "arguments": [],
          "description": "Subscribe to new user creation events"
        }
      ],
      "types": [
        {
          "name": "User",
          "kind": "OBJECT",
          "field_count": 4,
          "fields": ["id", "email", "name", "createdAt"]
        },
        {
          "name": "CreateUserInput",
          "kind": "INPUT_OBJECT",
          "field_count": 2,
          "fields": ["email", "name"]
        },
        {
          "name": "Role",
          "kind": "ENUM",
          "field_count": 3,
          "fields": ["ADMIN", "USER", "GUEST"]
        }
      ],
      "native": {
        "sdl": "type User {\n  id: ID!\n  email: String!\n  name: String!\n  createdAt: DateTime!\n}\n\ninput CreateUserInput {\n  email: String!\n  name: String!\n}\n\nenum Role {\n  ADMIN\n  USER\n  GUEST\n}\n\ntype Query {\n  users(limit: Int = 10, offset: Int = 0): [User!]!\n  user(id: ID!): User\n}\n\ntype Mutation {\n  createUser(input: CreateUserInput!): User!\n  updateUser(id: ID!, input: UpdateUserInput!): User!\n}\n\ntype Subscription {\n  userCreated: User!\n}"
      }
    }
  }
}
```

A `graphql` collector would detect `.graphql` / `.gql` schema files, introspection endpoints, or `schema.graphql` files. It writes to `.api.spec_files[]` (with `protocol: "graphql"`) and `.api.graphql.*`. The existing `api-docs` policy would pick up GraphQL specs for universal checks. GraphQL-specific policies could assert on things like "all queries must have descriptions" or "no unlimited list queries without pagination arguments".

## Design Notes

This category follows the standard collector/policy pattern: each spec format gets its own technology-specific collector, but they all feed the same `.api` category (see [Raw/Native Data convention](conventions.md#rawnative-data) and [collector naming conventions](../collector-reference.md#8-naming-convention-cicd-vs-auto-sub-keys-for-ci-detected-and-auto-run-collectors)):

```
collectors/openapi/  ──writes──┐
                                ├──→  .api.spec_files[]  ←──reads── policies/api-docs/
collectors/swagger/  ──writes──┘        .api.rest.*
```

**Why three layers?**
- **Layer 1** lets policies answer universal questions ("has API docs?", "all specs valid?") with zero knowledge of REST vs gRPC.
- **Layer 2** gives policies the actual API surface (endpoints, schemas, RPCs) in a normalized, tool-agnostic form — no matter if the source was OpenAPI 3.0, Swagger 2.0, or a future AsyncAPI spec.
- **Layer 3** preserves the full raw spec for policies that need deep tool-specific inspection, following the [`.native` convention](conventions.md#rawnative-data).
