class ErrorInstalacion(RuntimeError):
    """Error explicable al usuario durante instalación o enrolamiento."""

    def __init__(self, mensaje, codigo=None):
        super().__init__(mensaje)
        self.codigo = codigo
