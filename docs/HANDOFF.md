# HANDOFF.md — template

Every handoff artifact from every agent includes:

```
# Handoff: <agent> -> <next-agent> (phase P)

## Outputs
- <path 1>  (<one line what it is>)
- <path 2>  ...

## Acceptance evidence
- <test run URL or log path>
- <screenshot or rendered artifact if frontend>
- <openapi lint output if contract>

## Corrections applied
- R-xx: <how it was applied, file/line>

## Assumptions
- <thing the next agent must know that is not obvious from the spec>

## Questions
- <open question, if any, with default taken>
```
