from fastapi import HTTPException, status


class HTTPItemNotFoundError(HTTPException):
    '''HTTPException for Item Not Found error.'''

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )


class HTTPCartNotFoundError(HTTPException):
    '''HTTPException for Cart Not Found error.'''

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found"
        )
