from PySide6.QtWidgets import QApplication


class AdrienApplication(QApplication):
    """
    Main application class for ADRIEN.
    """

    def __init__(self, args):
        super().__init__(args)

        self.setApplicationName("ADRIEN")
        self.setOrganizationName("ADRIEN Technologies")     