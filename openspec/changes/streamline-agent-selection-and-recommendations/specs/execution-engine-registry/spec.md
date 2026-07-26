## ADDED Requirements

### Requirement: Conversational engine recommendation policy
The registry integration SHALL expose OpenHands, Codex, and Gemini CLI to the conversational creation flow, SHALL recommend Codex for coding work and OpenHands for other work, and SHALL treat an explicit operator choice as authoritative without changing the OpenHands compatibility default for legacy callers.

#### Scenario: New coding conversation omits explicit engine
- **WHEN** a conversational coding draft is generated without an operator engine override
- **THEN** the draft identifies Codex as its recommended engine

#### Scenario: New general conversation omits explicit engine
- **WHEN** a conversational non-coding draft is generated without an operator engine override
- **THEN** the draft identifies OpenHands as its recommended engine

#### Scenario: Legacy API client omits engine
- **WHEN** a legacy non-conversational task, Session, or preset request omits execution-engine selection
- **THEN** the system continues using the OpenHands compatibility default

#### Scenario: Operator explicitly selects Gemini CLI
- **WHEN** Gemini CLI preflight is ready and the operator selects it
- **THEN** the applied roles and runs record Gemini CLI and the worker invokes its existing registered adapter
