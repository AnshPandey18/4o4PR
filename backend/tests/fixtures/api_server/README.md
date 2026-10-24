# API Server - High Complexity Sample

## Overview
REST API server with decorators, inheritance, complex call chains, and state management.

## Features
- Class inheritance
- Decorated methods
- Complex call chains
- Multiple constants and state
- Error handling with custom exceptions
- Cross-module dependencies

## Bugs
1. `@authenticate` decorator applied incorrectly - doesn't properly validate tokens
2. `UserService.update_user()` calls `_validate_user()` but validation is incomplete
3. `_hash_password()` is called multiple times but hash function is wrong
4. `APIServer.start()` calls initialization chain but state is not properly managed
5. Constants like `SECRET_KEY` are used incorrectly

## Learning Goals
- Complex decorator tracking
- Inheritance chain analysis
- Multi-level function call chains
- Cross-module constant references
- Error handling paths
- Circular dependency detection
