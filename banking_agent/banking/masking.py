def mask_reference(reference: str) -> str:
    if len(reference) < 8:
        return "••••"
    return f"••••{reference[-4:]}"
