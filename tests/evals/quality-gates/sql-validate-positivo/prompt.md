---
name: sql-validate-positivo
plugins: [quality-gates]
max_turns: 4
allowed_tools: [Read, Glob, Grep, Skill]
---

Valida este SQL antes de que lo corra a mano en SQL Server: SELECT TOP 10 * FROM ventas ORDER BY fecha DESC LIMIT 5;
