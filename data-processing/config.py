import os


def get_edgar_identity() -> str:
    identity = os.environ.get("EDGAR_IDENTITY", "").strip()
    if not identity:
        raise RuntimeError(
            "EDGAR_IDENTITY is not set. SEC EDGAR requires a name and email.\n"
            'Example: export EDGAR_IDENTITY="Your Name your.email@example.com"'
        )
    return identity
