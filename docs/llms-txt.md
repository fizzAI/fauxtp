# LLM Agent Documentation

This page provides comprehensive API documentation and guides optimized for LLM agents and AI assistants working with fauxtp.

## Download

The complete documentation is available as a single text file optimized for LLM consumption:

**[Download llms.txt](llms.txt)**

## What's Included

The [`llms.txt`](llms.txt) file contains:

### Quick Start
- Installation instructions
- Basic usage examples
- Quick reference code snippets

### Core Concepts
- **Actors**: Fundamental concurrency primitives with message passing
- **GenServer**: Generic server pattern for stateful actors
- **Supervisors**: Fault-tolerant process supervision

### Complete API Reference
- **Actor API**: Base actor class, lifecycle methods, message handling
- **GenServer API**: Synchronous/asynchronous request handling, task management
- **Supervisor API**: Restart strategies, child specifications
- **Messaging API**: `send`, `call`, `cast` functions
- **Pattern Matching**: Message pattern matching system
- **Registry API**: Global process registration
- **Task API**: Async function wrappers

### Guides & Best Practices
- State immutability patterns
- Supervision tree design
- Lifecycle management
- Common patterns and anti-patterns

## Usage for LLM Agents

This documentation is specifically formatted for LLM agents to:

1. **Understand the library quickly**: Concise explanations with code examples
2. **Generate correct code**: Complete API signatures with type hints
3. **Follow best practices**: Idiomatic patterns and common pitfalls
4. **Build fault-tolerant systems**: Supervision and error handling patterns

## Format

The file uses a simple, structured text format:
- Clear section headers with `#` markdown syntax
- Code examples in fenced code blocks
- API signatures with parameter types
- Inline documentation for all public APIs

## Integration

To use this with an LLM agent or AI coding assistant:

1. Download the [`llms.txt`](llms.txt) file
2. Include it in your agent's context or knowledge base
3. Reference it when working with fauxtp code

The documentation is self-contained and includes everything needed to work with fauxtp without requiring external references.
