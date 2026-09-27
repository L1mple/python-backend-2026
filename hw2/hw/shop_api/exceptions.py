class AppError(RuntimeError):
    pass


class NotFoundError(AppError):
    status_code = 404
    detail = 'Object not Found'
