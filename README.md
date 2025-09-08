# solver-director

## Updating dependicies
You can manually update dependicies by:
```toml
pip-compile pyproject.toml -o requirements.txt --strip-extras
pip-compile pyproject.toml --extra dev -o requirements-dev.txt --strip-extras

```