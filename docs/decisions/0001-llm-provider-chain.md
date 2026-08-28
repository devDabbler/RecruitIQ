# ADR 0001: Three-tier LLM provider chain, local-first

**Date:** 2026-08-27 · **Status:** Accepted (Phase 2)

## Context

The previous AI layer accumulated five providers (Nebius, Cohere, Gemini,
Meta Llama, OpenRouter) with per-provider branching in a 914-line service.
The primary provider's key was dead (HTTP 401), so every AI path failed, and
its connection test dominated a 27-second cold start. Separately, the GPU
that could serve local inference also runs a trading system whose
money-touching paths are deliberately pinned to cloud — demo traffic must
never contend with it.

## Decision

One chain, three tiers, in order:

1. **Ollama `qwen3:8b`** over the existing Cloudflare tunnel — $0,
   best-effort only: hard 20 s timeout, zero retries, fall through on any
   failure. The model is already resident in VRAM for the other project, so
   there is no thrash and keeping it warm is mutually beneficial.
2. **OpenRouter** — the real fallback. One `OpenAICompatProvider` class
   covers any OpenAI-compatible vendor via base-URL swap.
3. **Claude (`claude-haiku-4-5`)** — benchmark reference and final fallback;
   costs cents and guarantees schema conformance via `messages.parse`.

Structured outputs are schema-enforced where the provider supports it
(Ollama's `format` parameter, Claude's `messages.parse`) and the legacy
JSON-repair layer survives — but scoped to only the OpenAI-compatible tier,
where conformance is genuinely not guaranteed.

Chain order is configuration (`LLM_PROVIDER_ORDER`), so per-task routing can
be changed from eval results without code changes.

## Consequences

- All ~40 call sites keep the same `LLMService` interface; the chain is
  invisible to them.
- A demo visitor's worst case is one 20 s local timeout before cloud serves
  them; the GPU's other tenant is never queued behind demo traffic.
- Browsing the demo costs $0 (pre-embedded seed data, local tier); only the
  eval harness and explicit Claude-tier calls cost money, in cents.
- Nebius, Cohere, and Gemini code paths are deleted rather than disabled —
  resurrecting a provider means writing a provider class, not flipping a
  flag through dead branches.
