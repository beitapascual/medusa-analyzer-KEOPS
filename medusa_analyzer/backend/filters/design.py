def scipy_available() -> bool:
    try:
        import scipy.signal  # noqa: F401
        return True
    except ImportError:
        return False
