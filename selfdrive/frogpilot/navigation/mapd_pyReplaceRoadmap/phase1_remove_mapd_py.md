# Phase 1: Remove `mapd_py` and Protobuf Infrastructure

This phase entails purging the experimental Python mapd implementation and any associated protobuf messaging from the codebase:

## 1. Delete the `mapd_py` module
Remove the entire directory `selfdrive/frogpilot/navigation/mapd_py` (and its contents) from the repository. This includes all Python files (e.g. any `__init__.py`, logic files) and any `.proto` definition files related to mapd. By removing this, we eliminate the experimental Go-based reimplementation that we no longer plan to use.

## 2. Remove build and dependency entries
If `mapd_py` introduced any build rules or was referenced in a build configuration (e.g. Bazel or custom build scripts), delete those references. Also remove any installation of protobuf libraries if they were added solely for `mapd_py`. For example, if a `requirements.txt` or pip installation added `protobuf` or if protoc compiler steps were added, they should be excised.

## 3. Purge proto-generated code
Delete any Python files auto-generated from `.proto` (for instance, files named like `*_pb2.py` if present). These are no longer needed once we drop protobuf messaging.

## 4. Update imports and references
Search the entire codebase for any references to `mapd_py` or its data structures. This includes places where MTSC or other modules may import `mapd_py` or use its outputs. Remove or update those references. After this, no part of the code should be trying to use `mapd_py` or protobuf messages. For instance, if MTSC was reading a proto message (like `MapData`), that logic should be removed or replaced with reading the data from the restored `mapd` (addressed in Phase 3). The goal is that the code compiles/runs with no mention of `mapd_py` remaining.

## 5. Clean up parameters and settings
If any persistent parameters or toggles were specific to `mapd_py` (for example, a param enabling the experimental mapd or controlling proto logging), remove those. This prevents unused settings from lingering. We want a clean slate where only the original mapd approach remains.

## Success Criteria
By the end of Phase 1, the codebase should have no `mapd_py` code or protobuf dependencies. It should be as if that experimental feature never existed, setting the stage for reintroducing the original mapd system.