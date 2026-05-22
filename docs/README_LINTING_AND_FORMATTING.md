# Linting and Formatting

## Ruff
[Ruff](https://docs.astral.sh/ruff/) is the primary linter and formatter for Python code.

Running:
```shell
# linting
ruff check

# formatting
ruff format

# run specific rule
ruff check --select F .
```

## djLint
[djLint](https://djlint.com/) is a HTML template linter and formatter specifically designed for Django and other template engines.

Running:
```shell
# linting
djlint templates --lint

# formatting
djlint templates --check
```
