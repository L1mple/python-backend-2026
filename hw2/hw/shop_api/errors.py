class ResourceNotFoundError(LookupError):
    """The requested item or cart does not exist."""


class CartTotalOverflowError(ValueError):
    """A cart total cannot be represented as a finite number."""
