# solver-director

## Updating dependencies
You can manually update dependencies by:
```toml
pip-compile pyproject.toml -o requirements.txt --strip-extras
pip-compile pyproject.toml --extra dev -o requirements-dev.txt --strip-extras

```