# Contributor Guidelines

- **Code style:** Follow [PEP 8](https://peps.python.org/pep-0008/) conventions.
- **Formatting:** Run `black .` before committing to ensure consistent formatting.
- **Linting:** Use `ruff check .` to validate the code.
- **Testing:** Verify functionality with `pytest`.
- **CI expectations:** Pull requests are expected to pass the same `ruff`, `black`, and `pytest` checks in continuous integration.
- **Local checks:** Prior to committing, run `black .`, `ruff check .`, and `pytest` locally.
- **Feature requirements:** Consult [spec.md](spec.md) for feature scope and requirements.

